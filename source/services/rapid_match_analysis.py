"""Rapid, evidence-first analysis pipeline for match videos.

The fast pass samples video sparsely instead of decoding every frame. Automatic
Vision/OCR/audio outputs remain candidate evidence and are never silently promoted
to player or ball facts.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import copy
import json

from models import (
    AnalysisJob, VisionAnalysis, VisionSample,
    AutonomousAnalysis, AutonomousEventCandidate,
)
from services.vision_baseline import scan_local_video, VisionBaselineError
from services.scoreboard_ocr import sample_scoreboard_observations, tesseract_available
from services.autonomous_engine import infer_periods, infer_candidates, build_auto_summary, AutoCandidate, confidence_label
from services.audio_whistle import detect_whistle_candidates, ffmpeg_available as audio_ffmpeg_available


class RapidAnalysisError(RuntimeError):
    pass


_TIME_KEYS = {
    "second", "start", "end", "start_second", "end_second",
    "bracket_start_second", "bracket_end_second", "visual_focus_second",
    "previous_focus_second",
}


def _shift_times(value, offset: float):
    """Shift absolute source-time fields in a JSON-like structure."""
    if not offset:
        return value
    if isinstance(value, list):
        return [_shift_times(item, offset) for item in value]
    if isinstance(value, tuple):
        return tuple(_shift_times(item, offset) for item in value)
    if isinstance(value, dict):
        shifted = {}
        for key, item in value.items():
            if key in _TIME_KEYS and isinstance(item, (int, float)):
                shifted[key] = float(item) + offset
            else:
                shifted[key] = _shift_times(item, offset)
        return shifted
    return value


def run_rapid_analysis(
    db,
    match,
    source_path: Path,
    evidence_dir: Path,
    *,
    include_audio: bool = False,
    visual_samples: int = 180,
    ocr_samples: int = 48,
    source_kind: str = "upload",
    persist_visual_artifacts: bool = True,
    time_offset_seconds: float = 0.0,
):
    source_path = Path(source_path)
    if not source_path.exists():
        raise RapidAnalysisError("Video source file is missing.")
    try:
        time_offset = max(0.0, float(time_offset_seconds or 0.0))
    except (TypeError, ValueError):
        time_offset = 0.0

    job = AnalysisJob(
        match_id=match.id,
        stage="rapid_long_video",
        progress=5,
        status="running",
        message="Fast sparse scan started: visual sampling → scoreboard OCR → evidence candidates.",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        result = scan_local_video(source_path, Path(evidence_dir), target_samples=max(48, min(360, int(visual_samples))))
    except VisionBaselineError as exc:
        job.status = "failed"
        job.message = str(exc)
        match.status = "rapid_analysis_failed"
        db.commit()
        raise RapidAnalysisError(str(exc)) from exc

    active_windows = _shift_times(copy.deepcopy(result.active_windows), time_offset)
    interesting_moments = _shift_times(copy.deepcopy(result.interesting_moments), time_offset)

    vision = VisionAnalysis(
        match_id=match.id,
        status="complete",
        engine_version="rapid-visual-v1",
        source_kind=(source_kind or "upload")[:32],
        duration_seconds=result.duration_seconds,
        fps=result.fps,
        width=result.width,
        height=result.height,
        sample_interval_seconds=result.sample_interval_seconds,
        sample_count=len(result.samples),
        video_type=result.video_type,
        confidence=result.video_type_confidence,
        avg_pool_ratio=result.avg_pool_ratio,
        avg_motion_score=result.avg_motion_score,
        scene_cut_rate=result.scene_cut_rate,
        active_seconds_estimate=result.active_seconds_estimate,
        active_windows_json=json.dumps(active_windows),
        interesting_moments_json=json.dumps(interesting_moments),
        scoreboard_candidates_json=json.dumps([asdict(c) for c in result.scoreboard_candidates]),
        # Third-party sources may be decoded transiently for derived measurements,
        # but AquaMetric does not persist or expose their contact-sheet imagery.
        contact_sheet_file=result.contact_sheet_file if persist_visual_artifacts else "",
        limitations_json=json.dumps(result.limitations, ensure_ascii=False),
    )
    db.add(vision)
    db.flush()
    for sample in result.samples:
        db.add(VisionSample(
            analysis_id=vision.id,
            second=float(sample.second) + time_offset,
            pool_ratio=sample.pool_ratio,
            motion_score=sample.motion_score,
            scene_change=sample.scene_change,
            active_score=sample.active_score,
            action_score=sample.action_score,
        ))

    job.progress = 58
    job.message = f"Visual sparse scan complete: {len(result.samples)} samples over {result.duration_seconds/60:.1f} min."
    db.commit()

    rois = [asdict(c) for c in result.scoreboard_candidates]
    observations = [
        obs.to_dict()
        for obs in sample_scoreboard_observations(
            source_path,
            rois,
            result.duration_seconds,
            max_samples=max(12, min(96, int(ocr_samples))),
        )
    ]
    periods = infer_periods(observations, result.duration_seconds)
    candidates = infer_candidates(observations, result.interesting_moments)

    whistle_rows = []
    audio_state = "skipped_fast_mode"
    if include_audio:
        if audio_ffmpeg_available():
            whistle_rows = detect_whistle_candidates(source_path)
            audio_state = "complete"
            for whistle in whistle_rows:
                conf = min(0.78, max(0.35, whistle.score * 0.82))
                candidates.append(AutoCandidate(
                    whistle.second,
                    "whistle_candidate",
                    conf,
                    confidence_label(conf),
                    f"Referee-whistle-like audio burst near {whistle.peak_hz:.0f} Hz.",
                    {
                        "signal": "audio_spectrum",
                        "peak_hz": whistle.peak_hz,
                        "audio_score": whistle.score,
                        "duration_hint": whistle.duration_hint,
                    },
                ))
        else:
            audio_state = "ffmpeg_unavailable"
    candidates.sort(key=lambda item: item.second)

    if time_offset:
        observations = _shift_times(observations, time_offset)
        periods = _shift_times(periods, time_offset)
        shifted_candidates = []
        for candidate in candidates:
            shifted_candidates.append(AutoCandidate(
                float(candidate.second) + time_offset,
                candidate.event_type,
                candidate.confidence,
                candidate.confidence_label,
                candidate.summary,
                _shift_times(copy.deepcopy(candidate.evidence), time_offset),
            ))
        candidates = shifted_candidates

    summary = build_auto_summary(observations, periods, candidates)
    summary.update({
        "pipeline": "rapid-long-video-v1",
        "source_kind": source_kind,
        "duration_minutes": round(result.duration_seconds / 60.0, 1),
        "source_time_offset_seconds": round(time_offset, 3),
        "visual_samples": len(result.samples),
        "ocr_samples_cap": max(12, min(96, int(ocr_samples))),
        "scoreboard_observations": len(observations),
        "whistle_candidates": len(whistle_rows),
        "audio_scan": audio_state,
        "speed_strategy": "sparse visual sampling + bounded scoreboard OCR; no frame-by-frame full decode",
    })
    limitations = [
        "Automatic output is candidate evidence until cross-validated; it never replaces official truth.",
        "The fast pass does not yet visually resolve every player number/face or track the ball continuously.",
        "Player-level passes, shot attribution, possessions, exclusions and tactical shapes require verified tagging or dedicated models.",
        "A cap number is not a player identity: opposing teams and even players on the same friendly-match roster may share a number; individual attribution requires side + visual track/player resolution.",
        "All unavailable match statistics stay visibly unavailable instead of being filled with synthetic values.",
    ]
    if source_kind != "upload":
        limitations.append("Third-party source pixels are transient: derived measurements are stored, source frames/clips/contact sheets are not persisted.")
    autonomy = AutonomousAnalysis(
        match_id=match.id,
        status="complete",
        engine_version="rapid-autonomy-v1",
        ocr_available=tesseract_available(),
        observations_json=json.dumps(observations, ensure_ascii=False),
        periods_json=json.dumps(periods, ensure_ascii=False),
        summary_json=json.dumps(summary, ensure_ascii=False),
        limitations_json=json.dumps(limitations, ensure_ascii=False),
    )
    db.add(autonomy)
    db.flush()
    for candidate in candidates:
        db.add(AutonomousEventCandidate(
            analysis_id=autonomy.id,
            match_id=match.id,
            second=candidate.second,
            event_type=candidate.event_type,
            confidence_score=candidate.confidence,
            confidence_label=candidate.confidence_label,
            summary=candidate.summary,
            evidence_json=json.dumps(candidate.evidence, ensure_ascii=False),
            source="rapid-autonomy-v1",
        ))

    job.progress = 100
    job.status = "rapid_analysis_complete"
    job.message = (
        f"Analyse rapide terminée: {len(result.samples)} échantillons visuels, "
        f"{len(observations)} observations scoreboard, {len(candidates)} moments candidats. "
        "Les statistiques joueuses restent alimentées uniquement par des événements prouvés/validés."
    )
    match.status = "rapid_analysis_complete"
    db.commit()
    return {
        "job": job,
        "vision": vision,
        "autonomy": autonomy,
        "summary": summary,
        "candidates": candidates,
    }
