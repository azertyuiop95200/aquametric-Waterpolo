"""V14 browser capture: fast, bounded and always-terminal finalization.

The preferred path reuses JPEG evidence decoded during playback. If those live
frames are missing, V14 performs only a sparse, explicitly budgeted video pass
instead of V10's larger verification scan. Any decoder/OCR/finalizer failure is
converted into a truthful evidence-limited terminal report. Processing reaching
100% means the lifecycle is finished; evidence confidence remains separate.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import time

from fastapi import BackgroundTasks, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import capture_turbo_routes_v11 as v11
import capture_turbo_routes_v13 as v13
from analysis_product_routes import _capture_session_dir, _owned_match
from capture_turbo_routes import _FAST_CAPTURE_SENTINEL, _read_state, _write_state
from db import SessionLocal, get_db
from models import AutonomousAnalysis, Match, VisionAnalysis
from services.live_frame_match_analysis import live_frame_coverage, run_live_frame_analysis
from services.scoreboard_ocr import tesseract_available

log = logging.getLogger("aquametric.browser_capture.v14")

V14_FINALIZATION_WATCHDOG_SECONDS = 35.0
V14_LIVE_VISUAL_SAMPLES = 56
V14_LIVE_OCR_SAMPLES = 4
V14_VIDEO_VISUAL_SAMPLES = 32
V14_VIDEO_OCR_SAMPLES = 4
V14_MOSAIC_VISUAL_SAMPLES = 84
V14_MOSAIC_OCR_SAMPLES = 8

# Keep the proven V13 capture/read path. V14 changes final publication only.
turbo_browser_capture_page = v13.turbo_browser_capture_page
turbo_create_session = v13.turbo_create_session
turbo_append_chunk = v13.turbo_append_chunk
turbo_progress_frame = v13.turbo_progress_frame


def _body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def _should_rescue(status: str, started_at: float, now: float | None = None) -> bool:
    if str(status or "") not in {"queued_finalization", "finalizing"}:
        return False
    started = float(started_at or 0.0)
    if started <= 0:
        return False
    current = float(time.time() if now is None else now)
    return current - started >= V14_FINALIZATION_WATCHDOG_SECONDS


def _terminal(state: dict) -> bool:
    return str(state.get("status") or "") in {"complete", "partial"} and float(state.get("analysis_percent") or 0.0) >= 100.0


def _publish_fallback_report(match_id: int, root_value: str, reason: str) -> dict:
    """Publish all real live evidence and leave unmeasured fields unmeasured."""
    root = Path(root_value)
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if not match or not root.is_dir():
            return {}
        state = _read_state(root)
        if _terminal(state):
            return state

        start = max(0.0, float(state.get("source_start_second") or 0.0))
        total = max(start, float(state.get("source_duration_seconds") or 0.0))
        duration = max(0.0, total - start)
        coverage = live_frame_coverage(root, state)
        progressive_samples = max(0, int(state.get("progressive_samples") or 0))
        retained_frames = max(0, int(coverage.get("records") or state.get("saved_live_frames") or 0))
        ocr_hits = max(0, int(state.get("progressive_ocr_hits") or 0))
        avg_pool = max(0.0, min(1.0, float(state.get("avg_live_pool_ratio") or 0.0)))
        client_read = max(0.0, min(100.0, float(state.get("client_finish_read_percent") or state.get("read_percent") or 0.0)))
        evidence_ratio = max(float(coverage.get("coverage_ratio") or 0.0), client_read / 100.0 if progressive_samples > 0 else 0.0)
        evidence_ratio = max(0.0, min(1.0, evidence_ratio))
        confidence = "MEDIUM" if progressive_samples >= 24 and evidence_ratio >= 0.75 else "LOW"
        latest_ocr = [str(x)[:160] for x in list(state.get("latest_live_ocr") or [])[:4]]
        limitations = [
            "Publication de secours V14: uniquement les preuves réellement traitées sont conservées.",
            "Les métriques non observées restent non mesurées; aucun score, événement ou joueur n'est inventé.",
            f"Motif de repli: {str(reason or 'budget_finalisation')[:180]}",
        ]

        vision = VisionAnalysis(
            match_id=match.id,
            status="partial",
            engine_version="live-frame-resilient-v14",
            source_kind="browser_capture_live_state",
            duration_seconds=duration,
            fps=0.0,
            width=0,
            height=0,
            sample_interval_seconds=(duration / progressive_samples) if progressive_samples > 0 and duration > 0 else 0.0,
            sample_count=progressive_samples,
            video_type="water_polo_capture",
            confidence=confidence,
            avg_pool_ratio=avg_pool,
            avg_motion_score=0.0,
            scene_cut_rate=0.0,
            active_seconds_estimate=0.0,
            active_windows_json="[]",
            interesting_moments_json="[]",
            scoreboard_candidates_json="[]",
            contact_sheet_file="",
            limitations_json=json.dumps(limitations, ensure_ascii=False),
        )
        db.add(vision)
        summary = {
            "pipeline": "live-frame-resilient-v14",
            "processing_completion_percent": 100.0,
            "report_quality": "evidence_limited",
            "evidence_confidence": confidence,
            "evidence_coverage_ratio": round(evidence_ratio, 4),
            "duration_minutes": round(duration / 60.0, 1) if duration > 0 else 0.0,
            "visual_samples": progressive_samples,
            "retained_live_frames": retained_frames,
            "scoreboard_observations": ocr_hits,
            "latest_scoreboard_text": latest_ocr,
            "source_time_offset_seconds": round(start, 3),
            "conclusion": "Rapport publié avec toutes les preuves disponibles; les champs non prouvés restent explicitement non mesurés.",
        }
        db.add(AutonomousAnalysis(
            match_id=match.id,
            status="partial",
            engine_version="live-frame-autonomy-resilient-v14",
            ocr_available=tesseract_available(),
            observations_json="[]",
            periods_json="[]",
            summary_json=json.dumps(summary, ensure_ascii=False),
            limitations_json=json.dumps(limitations, ensure_ascii=False),
        ))
        match.status = "browser_capture_analyzed"
        db.commit()

        state.update({
            "status": "partial",
            "analysis_percent": 100.0,
            "read_percent": max(float(state.get("read_percent") or 0.0), client_read),
            "phase": "rapport prêt · traitement terminé à 100% avec niveau de preuve indiqué",
            "redirect": f"/matches/{match_id}/analysis/result",
            "finalization_engine": "live-frame-resilient-v14",
            "report_quality": "evidence_limited",
            "evidence_confidence": confidence,
            "evidence_coverage_ratio": round(evidence_ratio, 4),
            "retained_live_frames": retained_frames,
            "visual_samples": progressive_samples,
            "scoreboard_observations": ocr_hits,
            "fallback_reason": str(reason or "bounded_finalization")[:240],
            "retry_available": False,
        })
        _write_state(root, state)
        log.warning("V14 terminal fallback match=%s samples=%s reason=%s", match_id, progressive_samples, reason)
        return state
    except Exception:
        db.rollback()
        log.exception("V14 fallback publication failed match=%s", match_id)
        return {}
    finally:
        db.close()


def _bounded_video_pass(db, match: Match, root: Path, start: float, total_duration: float, rate: float, segments: int) -> dict:
    """Sparse seek-based fallback for captures without enough retained JPEGs."""
    source_path = root / "capture.webm"
    derived_dir = root / "derived_v14"
    derived_dir.mkdir(parents=True, exist_ok=True)
    mosaic = segments >= 4 and total_duration > start + 30.0
    visual_samples = V14_MOSAIC_VISUAL_SAMPLES if mosaic else V14_VIDEO_VISUAL_SAMPLES
    ocr_samples = V14_MOSAIC_OCR_SAMPLES if mosaic else V14_VIDEO_OCR_SAMPLES
    state = _read_state(root)
    state.update({
        "phase": f"fallback vidéo sparse V14 · {visual_samples} images max · {ocr_samples} OCR max",
        "analysis_percent": max(95.0, float(state.get("analysis_percent") or 0.0)),
        "v14_video_fallback": True,
        "final_visual_budget": visual_samples,
        "final_ocr_budget": ocr_samples,
    })
    _write_state(root, state)

    analysis_source, media_info = v13.v10.v7.normalize_browser_capture(source_path, derived_dir, fast_analysis=True)
    state = _read_state(root)
    if _terminal(state):
        return {"terminal_already": True}
    state["media_normalization"] = media_info.get("normalization", "unknown")
    _write_state(root, state)

    if mosaic:
        return v13.v10.v7.run_mosaic_analysis(
            db,
            match,
            analysis_source,
            source_start_second=start,
            source_duration_seconds=total_duration,
            playback_rate=rate,
            parallel_segments=segments,
            visual_samples=visual_samples,
            ocr_samples=ocr_samples,
        )
    encoded_offset = (_FAST_CAPTURE_SENTINEL + start) if rate >= 1.75 else start
    return v13.v10.v7.run_rapid_analysis(
        db,
        match,
        analysis_source,
        derived_dir,
        include_audio=False,
        visual_samples=visual_samples,
        ocr_samples=ocr_samples,
        source_kind="browser_capture",
        persist_visual_artifacts=False,
        time_offset_seconds=encoded_offset,
    )


def _core_finalize_job_v14(match_id: int, root_value: str, start: float, total_duration: float, rate: float, segments: int) -> None:
    root = Path(root_value)
    db = SessionLocal()
    started = time.monotonic()
    try:
        match = db.get(Match, match_id)
        if not match or not root.is_dir():
            return
        state = _read_state(root)
        coverage = live_frame_coverage(root, state)
        state.update({
            "status": "finalizing",
            "analysis_percent": 94.0,
            "read_percent": 100.0,
            "phase": "finalisation IA V14 · consolidation bornée",
            "v14_finalization_started_at": float(state.get("v14_finalization_started_at") or time.time()),
            "v14_live_frame_coverage": coverage,
        })
        _write_state(root, state)

        if coverage.get("eligible"):
            result = run_live_frame_analysis(
                db,
                match,
                root,
                source_start_second=start,
                source_duration_seconds=total_duration,
                playback_rate=rate,
                parallel_segments=segments,
                visual_samples=V14_LIVE_VISUAL_SAMPLES,
                ocr_samples=V14_LIVE_OCR_SAMPLES,
            )
            engine = "live-frame-final-v14"
            quality = "verified_live_evidence"
        else:
            result = _bounded_video_pass(db, match, root, start, total_duration, rate, segments)
            if result.get("terminal_already"):
                return
            engine = "sparse-video-final-v14"
            quality = "verified_sparse_video"

        summary = result.get("summary", {}) or {}
        db.commit()
        state = _read_state(root)
        if _terminal(state):
            return
        elapsed = time.monotonic() - started
        state.update({
            "status": "complete",
            "analysis_percent": 100.0,
            "read_percent": 100.0,
            "phase": "rapport Vision V14 prêt · traitement terminé à 100%",
            "redirect": f"/matches/{match_id}/analysis/result",
            "visual_samples": int(summary.get("visual_samples") or 0),
            "scoreboard_observations": int(summary.get("scoreboard_observations") or 0),
            "parallel_segments": int(summary.get("parallel_segments") or segments),
            "retained_live_frames": int(summary.get("retained_live_frames") or coverage.get("records") or 0),
            "finalization_engine": engine,
            "finalization_elapsed_seconds": round(elapsed, 2),
            "report_quality": quality,
            "retry_available": False,
        })
        _write_state(root, state)
        match.status = "browser_capture_analyzed"
        db.commit()
        log.info("V14 report ready match=%s engine=%s elapsed=%.2fs visual=%s", match_id, engine, elapsed, state.get("visual_samples"))
    except Exception as exc:
        log.exception("V14 bounded finalization failed; publishing evidence-limited report match=%s", match_id)
        try:
            db.rollback()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass
        _publish_fallback_report(match_id, root_value, f"bounded_pass_error: {exc}")
    finally:
        try:
            db.close()
        except Exception:
            pass


def turbo_capture_status(match_id: int, request: Request, session_id: str, db: Session = Depends(get_db)):
    response = v13.turbo_capture_status(match_id=match_id, request=request, session_id=session_id, db=db)
    payload = _body(response)
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else None
    if not progress:
        return response
    status = str(progress.get("status") or "")
    started_at = float(progress.get("v14_finalization_started_at") or 0.0)
    if status == "failed" or _should_rescue(status, started_at):
        user, match = _owned_match(match_id, request, db)
        root = _capture_session_dir(user, match, session_id)
        reason = str(progress.get("error") or "watchdog finalisation > 35 s")
        rescued = _publish_fallback_report(match_id, str(root), reason)
        if rescued:
            try:
                v11._close_finalize_marker(match_id, str(root))
            except Exception:
                pass
            return JSONResponse({"ok": True, "progress": rescued})
    return response


def turbo_finish_capture(
    match_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    source_start_second: float = Form(0.0),
    source_duration_seconds: float = Form(0.0),
    playback_rate: float = Form(1.0),
    parallel_segments: int = Form(1),
    scope_mode: str = Form("auto"),
    analysis_scope_start_second: float = Form(0.0),
    analysis_scope_end_second: float = Form(0.0),
    client_read_percent: float = Form(100.0),
    client_finish_reason: str = Form("normal"),
    db: Session = Depends(get_db),
):
    shadow_tasks = BackgroundTasks()
    response = v13.turbo_finish_capture(
        match_id=match_id,
        request=request,
        background_tasks=shadow_tasks,
        session_id=session_id,
        source_start_second=source_start_second,
        source_duration_seconds=source_duration_seconds,
        playback_rate=playback_rate,
        parallel_segments=parallel_segments,
        scope_mode=scope_mode,
        analysis_scope_start_second=analysis_scope_start_second,
        analysis_scope_end_second=analysis_scope_end_second,
        client_read_percent=client_read_percent,
        client_finish_reason=client_finish_reason,
        db=db,
    )
    payload = _body(response)
    if not payload.get("accepted"):
        return response

    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    state = _read_state(root)
    if state.get("v14_finalization_scheduled"):
        payload.update({"finalization_engine": "v14", "non_blocking": True})
        return JSONResponse(payload)

    start = max(0.0, float(state.get("source_start_second") or source_start_second or 0.0))
    total_duration = max(0.0, float(state.get("source_duration_seconds") or source_duration_seconds or 0.0))
    rate = max(1.0, min(4.0, float(state.get("playback_rate") or playback_rate or 1.0)))
    segments = v13.v10.v7._segments(state.get("parallel_segments") or parallel_segments)
    state.update({
        "v14_finalization_scheduled": True,
        "v14_finalization_started_at": time.time(),
        "phase": "capture reçue · finalisation IA V14 non bloquante",
        "analysis_percent": max(92.0, float(state.get("analysis_percent") or 0.0)),
    })
    _write_state(root, state)

    background_tasks.add_task(_core_finalize_job_v14, match_id, str(root), start, total_duration, rate, segments)
    background_tasks.add_task(v11._close_finalize_marker, match_id, str(root))
    background_tasks.add_task(v13._enrich_after_report, match_id, str(root))

    payload.update({
        "analysis_percent": max(92.0, float(payload.get("analysis_percent") or 0.0)),
        "finalization_engine": "v14",
        "non_blocking": True,
        "max_wait_before_rescue_seconds": V14_FINALIZATION_WATCHDOG_SECONDS,
    })
    return JSONResponse(payload)
