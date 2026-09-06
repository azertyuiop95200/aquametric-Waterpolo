"""Fast analysis for a browser capture containing four parallel YouTube segments.

The browser plays four chronological quarters of the same replay at 2× in a 2×2
mosaic. This module samples the mosaic once, crops each quadrant, and maps every
measurement back to the original source timeline. It avoids serialising/re-encoding
four videos and is designed to keep a deep first-pass report inside a ~15 minute
product budget on ordinary match lengths.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import copy
import json
import math

import cv2
import numpy as np

from models import AnalysisJob, VisionAnalysis, VisionSample, AutonomousAnalysis, AutonomousEventCandidate
from services.autonomous_engine import infer_periods, infer_candidates, build_auto_summary
from services.scoreboard_ocr import ScoreboardObservation, ocr_image, parse_scoreboard_text, tesseract_available, _roi
from services.vision_baseline import (
    FrameSignal,
    VisionBaselineError,
    _classify_video_type,
    _group_windows,
    _histogram,
    _interesting_moments,
    _motion,
    _pool_ratio,
    _scene_change,
    _scoreboard_candidates,
)
from services.rapid_match_analysis import RapidAnalysisError, _map_times


def _pane(frame: np.ndarray, index: int, segments: int) -> np.ndarray:
    if segments <= 1:
        return frame
    h, w = frame.shape[:2]
    if segments == 2:
        half = w // 2
        return frame[:, :half] if index == 0 else frame[:, half:]
    # 4-segment turbo: TL, TR, BL, BR.
    half_w, half_h = w // 2, h // 2
    boxes = (
        (0, 0, half_w, half_h),
        (half_w, 0, w, half_h),
        (0, half_h, half_w, h),
        (half_w, half_h, w, h),
    )
    x1, y1, x2, y2 = boxes[index]
    return frame[y1:y2, x1:x2]


def _signal(frame: np.ndarray, second: float, prev_gray, prev_hist):
    analysis = frame
    if analysis.shape[1] > 960:
        scale = 960.0 / analysis.shape[1]
        analysis = cv2.resize(analysis, (960, max(1, int(analysis.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(analysis, cv2.COLOR_BGR2GRAY)
    hist = _histogram(analysis)
    pool = _pool_ratio(analysis)
    motion = _motion(prev_gray, gray)
    scene = _scene_change(prev_hist, hist)
    water_component = max(0.0, min(1.0, (pool - 0.12) / 0.58))
    active = max(0.0, min(1.0, 0.58 * water_component + 0.32 * motion + 0.10 * (1.0 - scene)))
    action = max(0.0, min(1.0, 0.46 * motion + 0.34 * active + 0.20 * scene))
    row = FrameSignal(round(second, 3), round(pool, 4), round(motion, 4), round(scene, 4), round(active, 4), round(action, 4))
    return row, gray, hist, analysis


def _probe(video_path: Path):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VisionBaselineError("OpenCV cannot open the parallel browser capture.")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = (frames / fps) if fps > 0 and frames > 0 else 0.0
    cap.release()
    if duration <= 0:
        raise VisionBaselineError("Parallel capture duration could not be determined.")
    return fps, frames, width, height, duration


def _read_at(cap, second: float):
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(second)) * 1000.0)
    ok, frame = cap.read()
    return frame if ok else None


def _ocr_observations(video_path: Path, rois, *, capture_duration: float, source_start: float,
                      source_duration: float, playback_rate: float, segments: int, max_samples: int):
    if not tesseract_available() or not rois:
        return []
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []
    try:
        count = max(16, min(int(max_samples), 128))
        targets = np.linspace(0.0, max(0.0, source_duration - 0.25), count)
        segment_span = source_duration / segments
        observations = []
        for rel_second in targets:
            seg = min(segments - 1, int(rel_second / max(segment_span, 0.001)))
            seg_rel = rel_second - seg * segment_span
            capture_second = min(max(0.0, capture_duration - 0.2), seg_rel / playback_rate)
            frame = _read_at(cap, capture_second)
            if frame is None:
                continue
            pane = _pane(frame, seg, segments)
            best = None
            for roi_info in rois[:2]:
                rect = tuple(float(getattr(roi_info, key)) for key in ("x", "y", "w", "h"))
                text, confidence = ocr_image(_roi(pane, rect))
                parsed = parse_scoreboard_text(text)
                useful = parsed["clock_seconds"] is not None or parsed["period"] is not None or parsed["home_score"] is not None
                if not useful:
                    continue
                obs = ScoreboardObservation(
                    second=round(float(rel_second), 2),
                    roi_name=str(getattr(roi_info, "name", "candidate")),
                    raw_text=text,
                    normalized_text=parsed["normalized_text"],
                    ocr_confidence=round(confidence, 3),
                    period=parsed["period"],
                    clock_seconds=parsed["clock_seconds"],
                    numbers=parsed["numbers"],
                    home_score=parsed["home_score"],
                    away_score=parsed["away_score"],
                )
                if best is None or obs.ocr_confidence > best.ocr_confidence:
                    best = obs
                if confidence >= 0.45 and parsed["clock_seconds"] is not None:
                    break
            if best:
                observations.append(best.to_dict())
        return observations
    finally:
        cap.release()


def run_mosaic_analysis(
    db,
    match,
    source_path: Path,
    *,
    source_start_second: float,
    source_duration_seconds: float,
    playback_rate: float = 2.0,
    parallel_segments: int = 4,
    visual_samples: int = 360,
    ocr_samples: int = 96,
):
    source_path = Path(source_path)
    if not source_path.exists():
        raise RapidAnalysisError("Parallel capture source is missing.")
    segments = 4 if int(parallel_segments or 1) >= 4 else (2 if int(parallel_segments or 1) >= 2 else 1)
    rate = max(1.0, min(4.0, float(playback_rate or 1.0)))
    source_start = max(0.0, float(source_start_second or 0.0))
    total_duration = max(source_start + 1.0, float(source_duration_seconds or 0.0))
    source_duration = max(1.0, total_duration - source_start)

    job = AnalysisJob(
        match_id=match.id,
        stage="parallel_mosaic_analysis",
        progress=5,
        status="running",
        message=f"Turbo analysis: {segments} chronological segments × {rate:g} playback.",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        fps, frame_count, width, height, capture_duration = _probe(source_path)
        cap = cv2.VideoCapture(str(source_path))
        sample_instants = max(24, min(120, math.ceil(int(visual_samples) / segments)))
        times = np.linspace(0.0, max(0.0, capture_duration - 0.25), sample_instants)
        segment_span = source_duration / segments
        signals = []
        raw_frames = []
        prev_gray = [None] * segments
        prev_hist = [None] * segments
        for capture_second in times:
            frame = _read_at(cap, float(capture_second))
            if frame is None:
                continue
            for seg in range(segments):
                rel_second = seg * segment_span + float(capture_second) * rate
                if rel_second >= min(source_duration, (seg + 1) * segment_span):
                    continue
                pane = _pane(frame, seg, segments)
                row, gray, hist, normalized = _signal(pane, rel_second, prev_gray[seg], prev_hist[seg])
                signals.append(row)
                prev_gray[seg], prev_hist[seg] = gray, hist
                if len(raw_frames) < 48:
                    raw_frames.append(normalized.copy())
        cap.release()
        if not signals:
            raise VisionBaselineError("No readable frames were sampled from the parallel capture.")
        signals.sort(key=lambda row: row.second)
        interval = source_duration / max(1, len(signals))
        windows_rel = _group_windows(signals, interval)
        moments_rel = _interesting_moments(signals, limit=24, separation=5.0)
        rois = _scoreboard_candidates(raw_frames)
        observations_rel = _ocr_observations(
            source_path,
            rois,
            capture_duration=capture_duration,
            source_start=source_start,
            source_duration=source_duration,
            playback_rate=rate,
            segments=segments,
            max_samples=ocr_samples,
        )
        periods_rel = infer_periods(observations_rel, source_duration)
        candidates_rel = infer_candidates(observations_rel, moments_rel)

        windows = _map_times(copy.deepcopy(windows_rel), source_start, 1.0)
        moments = _map_times(copy.deepcopy(moments_rel), source_start, 1.0)
        observations = _map_times(copy.deepcopy(observations_rel), source_start, 1.0)
        periods = _map_times(copy.deepcopy(periods_rel), source_start, 1.0)
        candidates = []
        for candidate in candidates_rel:
            candidate.second = float(candidate.second) + source_start
            candidate.evidence = _map_times(copy.deepcopy(candidate.evidence), source_start, 1.0)
            candidates.append(candidate)

        avg_pool = float(np.mean([row.pool_ratio for row in signals]))
        avg_motion = float(np.mean([row.motion_score for row in signals]))
        scene_cut_rate = float(np.mean([1.0 if row.scene_change >= 0.35 else 0.0 for row in signals]))
        active_seconds = min(source_duration, float(sum(float(w.get("duration", 0.0)) for w in windows_rel)))
        video_type, type_conf = _classify_video_type(source_duration, scene_cut_rate, active_seconds)

        vision = VisionAnalysis(
            match_id=match.id,
            status="complete",
            engine_version="parallel-mosaic-vision-v1",
            source_kind="browser_capture",
            duration_seconds=source_duration,
            fps=fps,
            width=max(1, width // 2) if segments >= 4 else width,
            height=max(1, height // 2) if segments >= 4 else height,
            sample_interval_seconds=interval,
            sample_count=len(signals),
            video_type=video_type,
            confidence=type_conf,
            avg_pool_ratio=avg_pool,
            avg_motion_score=avg_motion,
            scene_cut_rate=scene_cut_rate,
            active_seconds_estimate=active_seconds,
            active_windows_json=json.dumps(windows),
            interesting_moments_json=json.dumps(moments),
            scoreboard_candidates_json=json.dumps([asdict(c) for c in rois]),
            contact_sheet_file="",
            limitations_json=json.dumps([
                "Parallel browser capture: four chronological source segments were analysed from one 2×2 mosaic.",
                "Automatic output remains candidate evidence until cross-validated.",
                "Player identity requires side + visual track; duplicated cap numbers are never merged automatically.",
            ], ensure_ascii=False),
        )
        db.add(vision)
        db.flush()
        for row in signals:
            db.add(VisionSample(
                analysis_id=vision.id,
                second=float(row.second) + source_start,
                pool_ratio=row.pool_ratio,
                motion_score=row.motion_score,
                scene_change=row.scene_change,
                active_score=row.active_score,
                action_score=row.action_score,
            ))

        job.progress = 72
        job.message = f"Parallel visual pass complete: {len(signals)} source-timeline samples."
        db.commit()

        summary = build_auto_summary(observations, periods, candidates)
        summary.update({
            "pipeline": "parallel-mosaic-v1",
            "source_kind": "browser_capture",
            "source_time_offset_seconds": round(source_start, 3),
            "source_time_scale": round(rate, 3),
            "parallel_segments": segments,
            "duration_minutes": round(source_duration / 60.0, 1),
            "capture_duration_minutes": round(capture_duration / 60.0, 1),
            "visual_samples": len(signals),
            "scoreboard_observations": len(observations),
            "ocr_samples_cap": int(ocr_samples),
            "speed_strategy": f"{segments} parallel chronological segments × {rate:g} playback; direct mosaic sampling",
        })
        autonomy = AutonomousAnalysis(
            match_id=match.id,
            status="complete",
            engine_version="parallel-mosaic-autonomy-v1",
            ocr_available=tesseract_available(),
            observations_json=json.dumps(observations, ensure_ascii=False),
            periods_json=json.dumps(periods, ensure_ascii=False),
            summary_json=json.dumps(summary, ensure_ascii=False),
            limitations_json=json.dumps([
                "Turbo mode accelerates acquisition by analysing chronological segments in parallel.",
                "Score, periods and event candidates remain confidence-labelled evidence, not fabricated official truth.",
                "A final detailed player/tactical layer must only use identities supported by the visual track and roster evidence.",
            ], ensure_ascii=False),
        )
        db.add(autonomy)
        db.flush()
        for candidate in candidates:
            db.add(AutonomousEventCandidate(
                analysis_id=autonomy.id,
                match_id=match.id,
                second=float(candidate.second),
                event_type=candidate.event_type,
                confidence_score=candidate.confidence,
                confidence_label=candidate.confidence_label,
                summary=candidate.summary,
                evidence_json=json.dumps(candidate.evidence, ensure_ascii=False),
                source="parallel-mosaic-v1",
            ))

        job.progress = 100
        job.status = "rapid_analysis_complete"
        job.message = (
            f"Turbo analysis complete: {len(signals)} visual samples, {len(observations)} scoreboard observations, "
            f"{len(candidates)} candidate moments over {source_duration/60:.1f} source minutes."
        )
        match.status = "browser_capture_analyzed"
        db.commit()
        return {"job": job, "vision": vision, "autonomy": autonomy, "summary": summary, "candidates": candidates}
    except (VisionBaselineError, Exception) as exc:
        # Keep the public exception stable for the route; database state remains explicit.
        job.status = "failed"
        job.message = str(exc)
        match.status = "browser_capture_failed"
        db.commit()
        if isinstance(exc, RapidAnalysisError):
            raise
        raise RapidAnalysisError(str(exc)) from exc
