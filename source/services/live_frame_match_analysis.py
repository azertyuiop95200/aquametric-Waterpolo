"""Fast final match analysis from JPEG frames already processed during capture.

The browser capture pipeline sends decoded JPEG frames throughout playback.  The
old finalizer rescanned the full WebM after the live pass, which duplicated work
and made the AI bar appear stuck near the end.  This module reuses those retained
frames as the primary canonical evidence source and performs only a very small,
hard-budget scoreboard OCR verification pass.

No measurement is invented: missing/uncertain OCR stays missing, player identity
is not inferred from cap number alone, and every timestamp is reconstructed from
the recorded active wall-clock time plus the known parallel-segment mapping.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import asdict
from pathlib import Path
import copy
import json
import math
import time

import cv2
import numpy as np

from models import AnalysisJob, VisionAnalysis, VisionSample, AutonomousAnalysis, AutonomousEventCandidate
from services.autonomous_engine import infer_periods, infer_candidates, build_auto_summary
from services.mosaic_match_analysis import _pane, _signal
from services.rapid_match_analysis import RapidAnalysisError, _map_times
from services.scoreboard_ocr import ScoreboardObservation, ocr_image, parse_scoreboard_text, tesseract_available, _roi
from services.vision_baseline import (
    VisionBaselineError,
    _classify_video_type,
    _group_windows,
    _interesting_moments,
    _scoreboard_candidates,
)


def _timeline_records(root: Path, state: dict) -> list[dict]:
    folder = Path(root) / "live_frames"
    timeline = list(state.get("v13_live_frame_timeline") or [])
    out: list[dict] = []
    seen: set[int] = set()
    for row in timeline:
        try:
            idx = int(row.get("index"))
            wall = max(0.0, float(row.get("wall_second") or 0.0))
        except (TypeError, ValueError):
            continue
        path = folder / f"frame-{idx:04d}.jpg"
        if idx in seen or not path.exists() or path.stat().st_size < 1024:
            continue
        seen.add(idx)
        out.append({"index": idx, "wall_second": wall, "path": path})
    out.sort(key=lambda row: (float(row["wall_second"]), int(row["index"])))
    return out


def live_frame_coverage(root: Path, state: dict) -> dict:
    """Return truthful eligibility/coverage metadata for the fast path."""
    records = _timeline_records(root, state)
    expected = max(0.0, float(state.get("expected_capture_seconds") or 0.0))
    last_wall = max([float(row["wall_second"]) for row in records], default=0.0)
    ratio = min(1.0, last_wall / expected) if expected > 0 else 0.0
    # Eight retained composite frames already represent 32 source-time panes in
    # Turbo mode.  We still require near-complete read coverage to avoid turning
    # a partial capture into a full-match report.
    eligible = bool(len(records) >= 8 and (ratio >= 0.94 or float(state.get("read_percent") or 0.0) >= 95.0))
    return {
        "eligible": eligible,
        "records": len(records),
        "last_wall_second": round(last_wall, 3),
        "expected_capture_seconds": round(expected, 3),
        "coverage_ratio": round(ratio, 4),
    }


def _even_records(records: list[dict], limit: int) -> list[dict]:
    if len(records) <= limit:
        return records
    picks = np.linspace(0, len(records) - 1, max(2, int(limit)))
    indices = sorted({int(round(float(x))) for x in picks})
    return [records[i] for i in indices]


def _nearest_record(records: list[dict], target_wall: float) -> dict | None:
    if not records:
        return None
    walls = [float(row["wall_second"]) for row in records]
    pos = bisect_left(walls, max(0.0, float(target_wall)))
    candidates = []
    if pos < len(records):
        candidates.append(records[pos])
    if pos > 0:
        candidates.append(records[pos - 1])
    return min(candidates, key=lambda row: abs(float(row["wall_second"]) - target_wall)) if candidates else None


def _ocr_plan(source_duration: float, moments: list[dict], max_samples: int) -> list[float]:
    cap = max(4, min(12, int(max_samples or 0)))
    end = max(0.0, float(source_duration) - 0.25)
    raw = [float(x) for x in np.linspace(0.0, end, max(4, min(8, cap)))]
    for moment in list(moments or [])[:8]:
        center = max(0.0, min(end, float(moment.get("second") or 0.0)))
        raw.extend([center - 0.75, center, center + 0.75])
    selected: list[float] = []
    for second in sorted(max(0.0, min(end, x)) for x in raw):
        if selected and min(abs(second - old) for old in selected) < 1.2:
            continue
        selected.append(second)
        if len(selected) >= cap:
            break
    return selected


def _focused_ocr_from_live_frames(
    records: list[dict],
    rois,
    *,
    source_duration: float,
    playback_rate: float,
    segments: int,
    moments: list[dict],
    max_samples: int,
    budget_seconds: float = 8.0,
) -> tuple[list[dict], dict]:
    if not tesseract_available() or not rois or not records:
        return [], {"targets": 0, "elapsed_seconds": 0.0, "budget_seconds": 0.0, "budget_exhausted": False}
    targets = _ocr_plan(source_duration, moments, max_samples)
    started = time.monotonic()
    deadline = started + max(3.0, min(10.0, float(budget_seconds)))
    segment_span = source_duration / max(1, segments)
    cache: dict[int, np.ndarray] = {}
    observations: list[dict] = []
    exhausted = False

    for rel_second in targets:
        if time.monotonic() >= deadline:
            exhausted = True
            break
        seg = min(segments - 1, max(0, int(rel_second / max(segment_span, 0.001))))
        seg_rel = rel_second - seg * segment_span
        target_wall = seg_rel / max(1.0, playback_rate)
        record = _nearest_record(records, target_wall)
        if not record:
            continue
        idx = int(record["index"])
        image = cache.get(idx)
        if image is None:
            image = cv2.imread(str(record["path"]), cv2.IMREAD_COLOR)
            if image is None:
                continue
            cache[idx] = image
        pane = _pane(image, seg, segments)
        if pane.size == 0:
            continue
        best = None
        for roi_info in list(rois)[:2]:
            if time.monotonic() >= deadline:
                exhausted = True
                break
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
                ocr_confidence=round(float(confidence), 3),
                period=parsed["period"],
                clock_seconds=parsed["clock_seconds"],
                numbers=parsed["numbers"],
                home_score=parsed["home_score"],
                away_score=parsed["away_score"],
                is_replay=bool(parsed.get("is_replay")),
                is_break=bool(parsed.get("is_break")),
                is_final=bool(parsed.get("is_final")),
            )
            if best is None or obs.ocr_confidence > best.ocr_confidence:
                best = obs
            if confidence >= 0.45 and parsed["clock_seconds"] is not None:
                break
        if best:
            observations.append(best.to_dict())

    return observations, {
        "targets": len(targets),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "budget_seconds": round(max(3.0, min(10.0, float(budget_seconds))), 2),
        "budget_exhausted": exhausted,
    }


def run_live_frame_analysis(
    db,
    match,
    root: Path,
    *,
    source_start_second: float,
    source_duration_seconds: float,
    playback_rate: float = 2.0,
    parallel_segments: int = 4,
    visual_samples: int = 96,
    ocr_samples: int = 10,
):
    root = Path(root)
    state_path = root / "progress.json"
    if not state_path.exists():
        raise RapidAnalysisError("Live-frame session state is missing.")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RapidAnalysisError(f"Live-frame session state cannot be read: {exc}") from exc

    coverage = live_frame_coverage(root, state)
    records = _timeline_records(root, state)
    if not coverage["eligible"]:
        raise RapidAnalysisError("Retained live frames do not have enough near-complete coverage for fast finalization.")

    segments = 4 if int(parallel_segments or 1) >= 4 else (2 if int(parallel_segments or 1) >= 2 else 1)
    rate = max(1.0, min(4.0, float(playback_rate or 1.0)))
    source_start = max(0.0, float(source_start_second or 0.0))
    total_duration = max(source_start + 1.0, float(source_duration_seconds or 0.0))
    source_duration = max(1.0, total_duration - source_start)
    segment_span = source_duration / segments

    job = AnalysisJob(
        match_id=match.id,
        stage="live_frame_final_analysis",
        progress=8,
        status="running",
        message=f"Fast finalization from {len(records)} retained live frames.",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        composite_limit = max(8, min(36, math.ceil(int(visual_samples or 96) / segments)))
        selected = _even_records(records, composite_limit)
        signals = []
        raw_frames = []
        prev_gray = [None] * segments
        prev_hist = [None] * segments
        pane_width = pane_height = 0

        for record in selected:
            image = cv2.imread(str(record["path"]), cv2.IMREAD_COLOR)
            if image is None:
                continue
            wall = float(record["wall_second"])
            for seg in range(segments):
                rel_second = seg * segment_span + wall * rate
                if rel_second >= min(source_duration, (seg + 1) * segment_span):
                    continue
                pane = _pane(image, seg, segments)
                if pane.size == 0:
                    continue
                row, gray, hist, normalized = _signal(pane, rel_second, prev_gray[seg], prev_hist[seg])
                signals.append(row)
                prev_gray[seg], prev_hist[seg] = gray, hist
                pane_height, pane_width = pane.shape[:2]
                if len(raw_frames) < 32:
                    raw_frames.append(normalized.copy())

        if not signals:
            raise VisionBaselineError("No retained live frame could be decoded.")
        signals.sort(key=lambda row: row.second)
        interval = source_duration / max(1, len(signals))
        windows_rel = _group_windows(signals, interval)
        moments_rel = _interesting_moments(signals, limit=24, separation=4.0)
        rois = _scoreboard_candidates(raw_frames)

        job.progress = 62
        job.message = f"Live-frame visual pass complete: {len(signals)} source-timeline samples."
        db.commit()

        observations_rel, ocr_meta = _focused_ocr_from_live_frames(
            records,
            rois,
            source_duration=source_duration,
            playback_rate=rate,
            segments=segments,
            moments=moments_rel,
            max_samples=ocr_samples,
            budget_seconds=8.0,
        )
        periods_rel = infer_periods(observations_rel, source_duration)
        candidates_rel = infer_candidates(observations_rel, moments_rel)

        job.progress = 84
        job.message = (
            f"Targeted OCR verification complete: {len(observations_rel)} useful observations; "
            f"{ocr_meta.get('elapsed_seconds', 0)} s OCR."
        )
        db.commit()

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
            engine_version="live-frame-vision-v1",
            source_kind="browser_capture_live_frames",
            duration_seconds=source_duration,
            fps=0.0,
            width=max(1, pane_width),
            height=max(1, pane_height),
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
                "Final report reused decoded JPEG frames already analysed during browser playback instead of rescanning the full capture.",
                "Scoreboard OCR is a bounded verification pass over retained evidence; uncertain values stay unmeasured.",
                "Player identity requires side plus visual track; duplicate cap numbers are never merged automatically.",
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

        summary = build_auto_summary(observations, periods, candidates)
        summary.update({
            "pipeline": "live-frame-final-v1",
            "source_kind": "browser_capture_live_frames",
            "source_time_offset_seconds": round(source_start, 3),
            "source_time_scale": round(rate, 3),
            "parallel_segments": segments,
            "duration_minutes": round(source_duration / 60.0, 1),
            "visual_samples": len(signals),
            "scoreboard_observations": len(observations),
            "retained_live_frames": len(records),
            "live_frame_coverage_ratio": coverage["coverage_ratio"],
            "ocr_targets_used": int(ocr_meta.get("targets") or 0),
            "ocr_elapsed_seconds": float(ocr_meta.get("elapsed_seconds") or 0.0),
            "ocr_budget_seconds": float(ocr_meta.get("budget_seconds") or 0.0),
            "ocr_budget_exhausted": bool(ocr_meta.get("budget_exhausted")),
            "measurement_strategy": "reuse decoded live frames + targeted OCR verification + confidence-labelled candidate extraction",
            "speed_strategy": "no full WebM rescan when retained live-frame coverage is sufficient",
        })
        autonomy = AutonomousAnalysis(
            match_id=match.id,
            status="complete",
            engine_version="live-frame-autonomy-v1",
            ocr_available=tesseract_available(),
            observations_json=json.dumps(observations, ensure_ascii=False),
            periods_json=json.dumps(periods, ensure_ascii=False),
            summary_json=json.dumps(summary, ensure_ascii=False),
            limitations_json=json.dumps([
                "Fast finalization reuses actual retained browser pixels and does not synthesize missing events.",
                "Score, periods and event candidates remain confidence-labelled evidence, not fabricated official truth.",
                "Unsupported fields remain unmeasured rather than being silently set to zero.",
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
                source="live-frame-final-v1",
            ))

        job.progress = 100
        job.status = "rapid_analysis_complete"
        job.message = (
            f"Fast final report ready from {len(records)} retained frames: {len(signals)} visual samples, "
            f"{len(observations)} scoreboard observations."
        )
        match.status = "browser_capture_analyzed"
        db.commit()
        return {"job": job, "vision": vision, "autonomy": autonomy, "summary": summary, "candidates": candidates}
    except Exception as exc:
        job.status = "failed"
        job.message = str(exc)
        match.status = "browser_capture_failed"
        db.commit()
        if isinstance(exc, RapidAnalysisError):
            raise
        raise RapidAnalysisError(str(exc)) from exc
