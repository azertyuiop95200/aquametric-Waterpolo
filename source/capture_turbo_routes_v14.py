"""V14 browser capture: bounded, non-blocking and always-terminal finalization.

V13 already reuses retained live JPEGs for the normal fast path. V14 removes the
remaining user-visible stall modes: it never launches the expensive full-WebM
rescan during finalization, uses a smaller evidence budget, and publishes a
truthful partial report when retained evidence is insufficient or a fast pass
fails. "100%" here means the processing lifecycle reaches a terminal published
state; it never means that uncertain measurements are promoted to factual truth.
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
from capture_turbo_routes import _read_state, _write_state
from db import SessionLocal, get_db
from models import AutonomousAnalysis, Match, VisionAnalysis
from services.live_frame_match_analysis import live_frame_coverage, run_live_frame_analysis
from services.scoreboard_ocr import tesseract_available

log = logging.getLogger("aquametric.browser_capture.v14")

V14_FINALIZATION_WATCHDOG_SECONDS = 35.0

# Keep the proven V13 capture/read path. V14 changes only final publication.
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
    """Return True when finalization has exceeded its bounded publication window."""
    if str(status or "") not in {"queued_finalization", "finalizing"}:
        return False
    started = float(started_at or 0.0)
    if started <= 0:
        return False
    current = float(time.time() if now is None else now)
    return current - started >= V14_FINALIZATION_WATCHDOG_SECONDS


def _publish_fallback_report(match_id: int, root_value: str, reason: str) -> dict:
    """Publish a terminal evidence-limited report instead of leaving the UI stuck.

    The fallback only persists measurements that were already produced during the
    live progressive pass. Missing motion/events/score values remain absent/zero
    and are explicitly labelled as unmeasured.
    """
    root = Path(root_value)
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if not match or not root.is_dir():
            return {}
        state = _read_state(root)
        if str(state.get("status") or "") in {"complete", "partial"} and float(state.get("analysis_percent") or 0.0) >= 100.0:
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
            "Publication de secours V14: le rapport utilise uniquement les preuves réellement traitées pendant la lecture live.",
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
        autonomy = AutonomousAnalysis(
            match_id=match.id,
            status="partial",
            engine_version="live-frame-autonomy-resilient-v14",
            ocr_available=tesseract_available(),
            observations_json="[]",
            periods_json="[]",
            summary_json=json.dumps(summary, ensure_ascii=False),
            limitations_json=json.dumps(limitations, ensure_ascii=False),
        )
        db.add(autonomy)
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
        log.warning(
            "V14 published bounded fallback match=%s coverage=%.3f samples=%s frames=%s reason=%s",
            match_id,
            evidence_ratio,
            progressive_samples,
            retained_frames,
            reason,
        )
        return state
    except Exception:
        db.rollback()
        log.exception("V14 fallback publication failed match=%s", match_id)
        return {}
    finally:
        db.close()


def _core_finalize_job_v14(
    match_id: int,
    root_value: str,
    start: float,
    total_duration: float,
    rate: float,
    segments: int,
) -> None:
    """Run one short live-frame pass; publish a bounded fallback on any failure."""
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
            "phase": "finalisation IA V14 · consolidation bornée des preuves live",
            "v14_finalization_started_at": float(state.get("v14_finalization_started_at") or time.time()),
            "v14_live_frame_coverage": coverage,
        })
        _write_state(root, state)

        if not coverage.get("eligible"):
            db.close()
            _publish_fallback_report(match_id, root_value, "couverture live insuffisante pour le pass complet; aucun rescannage vidéo lancé")
            return

        result = run_live_frame_analysis(
            db,
            match,
            root,
            source_start_second=start,
            source_duration_seconds=total_duration,
            playback_rate=rate,
            parallel_segments=segments,
            visual_samples=56,
            ocr_samples=4,
        )
        elapsed = time.monotonic() - started
        summary = result.get("summary", {}) or {}
        state = _read_state(root)
        # A watchdog rescue may already have published a partial report. Do not
        # turn that terminal state back into a waiting state; an eventual complete
        # pass may safely upgrade it to complete.
        state.update({
            "status": "complete",
            "analysis_percent": 100.0,
            "read_percent": 100.0,
            "phase": "rapport Vision V14 prêt · traitement terminé à 100%",
            "redirect": f"/matches/{match_id}/analysis/result",
            "visual_samples": int(summary.get("visual_samples") or 0),
            "scoreboard_observations": int(summary.get("scoreboard_observations") or 0),
            "retained_live_frames": int(summary.get("retained_live_frames") or coverage.get("records") or 0),
            "finalization_engine": "live-frame-final-v14",
            "finalization_elapsed_seconds": round(elapsed, 2),
            "report_quality": "verified_live_evidence",
            "retry_available": False,
        })
        _write_state(root, state)
        match.status = "browser_capture_analyzed"
        db.commit()
        log.info(
            "V14 report ready match=%s elapsed=%.2fs visual=%s ocr=%s",
            match_id,
            elapsed,
            state.get("visual_samples"),
            state.get("scoreboard_observations"),
        )
    except Exception as exc:
        log.exception("V14 fast pass failed; publishing bounded report match=%s", match_id)
        try:
            db.rollback()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass
        _publish_fallback_report(match_id, root_value, f"fast_pass_error: {exc}")
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
    # Let V13 validate ownership/scope/source and create its durable marker, but
    # capture its background tasks in a throwaway container so the V10 full-video
    # fallback is never scheduled by V14.
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

    background_tasks.add_task(
        _core_finalize_job_v14,
        match_id,
        str(root),
        start,
        total_duration,
        rate,
        segments,
    )
    background_tasks.add_task(v11._close_finalize_marker, match_id, str(root))
    # Enrichment happens only after the report is terminal and therefore cannot
    # keep the browser waiting for publication.
    background_tasks.add_task(v13._enrich_after_report, match_id, str(root))

    payload.update({
        "analysis_percent": max(92.0, float(payload.get("analysis_percent") or 0.0)),
        "finalization_engine": "v14",
        "non_blocking": True,
        "max_wait_before_rescue_seconds": V14_FINALIZATION_WATCHDOG_SECONDS,
    })
    return JSONResponse(payload)
