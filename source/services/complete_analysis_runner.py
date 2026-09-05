from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from models import AutonomousEventCandidate, VisionSample
from services.analysis_product import build_exact_evidence_pack
from services.autonomous_engine import confidence_label
from services.rapid_match_analysis import RapidAnalysisError, run_rapid_analysis
from services.remote_video import RemoteVideoError, cleanup_remote_video, materialize_remote_video


def _refine_score_change_focus(db, vision, autonomy) -> int:
    """Move score-change review focus to the best dense vision sample inside its OCR bracket."""
    if not vision or not autonomy:
        return 0
    samples = db.scalars(
        select(VisionSample)
        .where(VisionSample.analysis_id == vision.id)
        .order_by(VisionSample.second)
    ).all()
    candidates = db.scalars(
        select(AutonomousEventCandidate)
        .where(AutonomousEventCandidate.analysis_id == autonomy.id)
        .order_by(AutonomousEventCandidate.second)
    ).all()
    refined = 0
    for candidate in candidates:
        if not (
            candidate.event_type.startswith("goal_candidate")
            or candidate.event_type.startswith("score_change_window")
        ):
            continue
        try:
            evidence = json.loads(candidate.evidence_json or "{}")
        except Exception:
            evidence = {}
        start = evidence.get("bracket_start_second")
        end = evidence.get("bracket_end_second")
        if start is None or end is None:
            continue
        inside = [s for s in samples if float(start) <= float(s.second or 0) <= float(end)]
        if not inside:
            continue
        best = max(inside, key=lambda s: (float(s.action_score or 0), float(s.active_score or 0)))
        score = max(float(best.action_score or 0), float(best.active_score or 0))
        previous_focus = float(candidate.second or 0)
        candidate.second = float(best.second or 0)
        candidate.confidence_score = min(0.9, float(candidate.confidence_score or 0) + min(0.05, score * 0.05))
        candidate.confidence_label = confidence_label(candidate.confidence_score)
        evidence.update({
            "visual_focus_second": round(float(best.second or 0), 2),
            "visual_activity_score": round(score, 3),
            "dense_visual_samples_in_bracket": len(inside),
            "previous_focus_second": round(previous_focus, 2),
            "time_precision": "best_of_dense_vision_samples_inside_score_bracket",
        })
        candidate.evidence_json = json.dumps(evidence, ensure_ascii=False)
        candidate.summary = (
            candidate.summary.split(" Dense vision refinement:")[0]
            + f" Dense vision refinement: focus={float(best.second or 0):.1f}s from {len(inside)} sampled frames inside the OCR bracket."
        )
        refined += 1
    if refined:
        db.commit()
    return refined


def _run_remote_analysis(db, match, upload_dir: Path, evidence_dir: Path, *, include_audio: bool):
    """Analyze an accessible remote video through a transient local copy."""
    source_path = None
    try:
        source_path = materialize_remote_video(match.video_url, Path(upload_dir))
        result = run_rapid_analysis(
            db,
            match,
            source_path,
            Path(evidence_dir),
            include_audio=include_audio,
            visual_samples=240,
            ocr_samples=72,
        )
        refined = _refine_score_change_focus(db, result.get("vision"), result.get("autonomy"))
        if refined:
            result.setdefault("summary", {})["score_change_timestamps_refined"] = refined
        build_exact_evidence_pack(
            db,
            match,
            Path(upload_dir),
            Path(evidence_dir),
            max_verified_events=32,
            max_candidates=28,
        )
        match.status = "url_video_analyzed"
        db.commit()
        return result
    finally:
        cleanup_remote_video(source_path)


def run_complete_analysis(db, match, upload_dir: Path, evidence_dir: Path, *, include_audio: bool = True):
    """Run actual Vision/OCR analysis for uploaded or remotely accessible video.

    Remote extraction failures are surfaced to the caller instead of silently
    returning an empty 0%-coverage report.
    """
    if match.video_source != "upload" or not match.video_path:
        if not match.video_url:
            raise RapidAnalysisError("Aucune source vidéo exploitable n'est associée à ce match.")
        try:
            return _run_remote_analysis(
                db,
                match,
                Path(upload_dir),
                Path(evidence_dir),
                include_audio=include_audio,
            )
        except RemoteVideoError as exc:
            match.status = "url_video_extraction_failed"
            db.commit()
            raise RapidAnalysisError(f"Impossible d'extraire la vidéo URL pour l'analyse: {exc}") from exc
        except RapidAnalysisError:
            raise
        except Exception as exc:
            match.status = "url_video_analysis_failed"
            db.commit()
            raise RapidAnalysisError(f"L'analyse vidéo URL a échoué: {exc}") from exc

    source_path = Path(upload_dir) / Path(match.video_path).name
    result = run_rapid_analysis(
        db,
        match,
        source_path,
        Path(evidence_dir),
        include_audio=include_audio,
        visual_samples=360,
        ocr_samples=96,
    )
    refined = _refine_score_change_focus(db, result.get("vision"), result.get("autonomy"))
    if refined:
        result.setdefault("summary", {})["score_change_timestamps_refined"] = refined
    build_exact_evidence_pack(
        db,
        match,
        Path(upload_dir),
        Path(evidence_dir),
        max_verified_events=32,
        max_candidates=28,
    )
    return result
