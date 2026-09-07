"""V13 browser capture: make the final AI pass reuse work already done live.

V12 fixed the 87% reader handoff.  V13 removes the next bottleneck: after the
reader finishes, the server no longer rescans the full WebM when enough decoded
JPEG frames have already been retained during playback.  It builds the canonical
Vision/Autonomy report directly from those frames and runs only a small bounded
OCR verification pass.  Sparse/incomplete sessions still fall back to V10's
video finalizer, so speed never replaces evidence requirements.
"""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path
import time

from fastapi import BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

import capture_turbo_routes_v10 as v10
import capture_turbo_routes_v11 as v11
import capture_turbo_routes_v12 as v12
from analysis_product_routes import EVIDENCE_DIR, UPLOAD_DIR, _capture_session_dir, _owned_match
from capture_turbo_routes import _read_state, _write_state
from db import SessionLocal, get_db
from models import Match
from services.deep_analysis_sequences import materialize_deep_sequence_pack
from services.live_frame_match_analysis import live_frame_coverage, run_live_frame_analysis
from services.rapid_match_analysis import RapidAnalysisError

log = logging.getLogger("aquametric.browser_capture.v13")

# V12 page/session/status lifecycle remains authoritative.
turbo_browser_capture_page = v12.turbo_browser_capture_page
turbo_create_session = v12.turbo_create_session
turbo_capture_status = v12.turbo_capture_status
turbo_append_chunk = v12.turbo_append_chunk


def _body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def turbo_progress_frame(
    match_id: int,
    request: Request,
    session_id: str = Form(...),
    wall_second: float = Form(...),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Preserve V12 processing and record exact wall time for each retained JPEG."""
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    before = _read_state(root)
    before_count = int(before.get("saved_live_frames") or 0)

    # V12/V11 consumes the upload stream, so pass it through unchanged once.
    response = v12.turbo_progress_frame(
        match_id=match_id,
        request=request,
        session_id=session_id,
        wall_second=wall_second,
        frame=frame,
        db=db,
    )
    payload = _body(response)
    state = _read_state(root)
    after_count = int(state.get("saved_live_frames") or 0)
    if after_count > before_count:
        timeline = list(state.get("v13_live_frame_timeline") or [])
        known = {int(row.get("index")) for row in timeline if isinstance(row, dict) and row.get("index") is not None}
        # _persist_live_frame currently writes at most one JPEG per frame request.
        for idx in range(before_count, after_count):
            if idx not in known:
                timeline.append({"index": idx, "wall_second": round(max(0.0, float(wall_second or 0.0)), 3)})
        state["v13_live_frame_timeline"] = timeline[-240:]
        state["v13_fast_finalization_ready"] = bool(live_frame_coverage(root, state).get("eligible"))
        _write_state(root, state)
        payload["progress"] = state
    return JSONResponse({"ok": True, "progress": payload.get("progress") or state})


def _core_fast_finalize_job(
    match_id: int,
    root_value: str,
    start: float,
    total_duration: float,
    rate: float,
    segments: int,
) -> None:
    root = Path(root_value)
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if not match or not root.is_dir():
            return
        state = _read_state(root)
        coverage = live_frame_coverage(root, state)
        state.update({
            "status": "finalizing",
            "analysis_percent": 91.0,
            "read_percent": 100.0,
            "phase": "finalisation IA accélérée · réutilisation des images déjà analysées",
            "v13_live_frame_coverage": coverage,
        })
        _write_state(root, state)

        if not coverage.get("eligible"):
            log.info(
                "V13 fallback to V10 match=%s records=%s coverage=%s",
                match_id,
                coverage.get("records"),
                coverage.get("coverage_ratio"),
            )
            # Sparse sessions keep the proven seekable-video fallback.
            db.close()
            v10._fast_finalize_capture_job(match_id, root_value, start, total_duration, rate, segments)
            return

        started = time.monotonic()
        result = run_live_frame_analysis(
            db,
            match,
            root,
            source_start_second=start,
            source_duration_seconds=total_duration,
            playback_rate=rate,
            parallel_segments=segments,
            visual_samples=96,
            ocr_samples=10,
        )
        elapsed = time.monotonic() - started
        summary = result.get("summary", {}) or {}
        state = _read_state(root)
        state.update({
            "status": "complete",
            "analysis_percent": 100.0,
            "read_percent": 100.0,
            "phase": "rapport Vision prêt · finalisation IA accélérée",
            "redirect": f"/matches/{match_id}/analysis/result",
            "visual_samples": int(summary.get("visual_samples") or 0),
            "scoreboard_observations": int(summary.get("scoreboard_observations") or 0),
            "parallel_segments": int(summary.get("parallel_segments") or segments),
            "finalization_engine": "live-frame-final-v1",
            "finalization_elapsed_seconds": round(elapsed, 2),
            "retained_live_frames": int(summary.get("retained_live_frames") or coverage.get("records") or 0),
        })
        _write_state(root, state)
        match.status = "browser_capture_analyzed"
        db.commit()
        log.info(
            "V13 fast report ready match=%s elapsed=%.2fs frames=%s visual=%s ocr=%s",
            match_id,
            elapsed,
            state.get("retained_live_frames"),
            state.get("visual_samples"),
            state.get("scoreboard_observations"),
        )
    except Exception as exc:
        log.exception("V13 fast browser finalization failed match=%s", match_id)
        try:
            state = _read_state(root)
            state.update({
                "status": "failed",
                "phase": "échec de la finalisation IA accélérée · capture conservée pour reprise",
                "analysis_percent": max(91.0, float(state.get("analysis_percent") or 0.0)),
                "error": str(exc),
                "retry_available": True,
            })
            _write_state(root, state)
        except Exception:
            pass
        try:
            match = db.get(Match, match_id)
            if match:
                match.status = "browser_capture_failed"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        try:
            db.close()
        except Exception:
            pass


def _enrich_after_report(match_id: int, root_value: str) -> None:
    """Run secondary sequence materialization only after the report is publishable."""
    root = Path(root_value)
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if not match:
            return
        try:
            materialize_deep_sequence_pack(
                db,
                match,
                UPLOAD_DIR,
                EVIDENCE_DIR,
                max_targets=24,
                max_clips=0,
                max_image_targets=0,
            )
        except Exception as exc:
            log.warning("V13 secondary enrichment partial match=%s error=%s", match_id, exc)
        finally:
            # Delete transient pixels but keep progress.json long enough for the
            # browser/report page to observe the terminal state.
            try:
                v10.v7._cleanup_pixels_keep_state(root)
            except Exception:
                pass
    finally:
        db.close()


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
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    if not root.is_dir():
        raise HTTPException(status_code=404, detail="Capture session expired or not found.")

    state = _read_state(root)
    read = max(0.0, min(100.0, float(client_read_percent or 0.0)))
    reason = (client_finish_reason or "normal")[:80]
    state["client_finish_read_percent"] = round(read, 3)
    state["client_finish_reason"] = reason
    if reason != "normal" and read < 99.5:
        state["coverage_warning"] = (
            f"Fin automatique après {read:.1f}% de lecture calculée; "
            "le rapport conserve uniquement les preuves réellement décodées."
        )

    mode = scope_mode if scope_mode in {"auto", "single", "manual", "multiple"} else str(state.get("scope_mode") or "auto")
    chosen_start = max(0.0, float(analysis_scope_start_second or state.get("analysis_scope_start_second") or source_start_second or 0.0))
    chosen_end = max(0.0, float(analysis_scope_end_second or state.get("analysis_scope_end_second") or 0.0))
    if mode == "manual" and chosen_end > chosen_start:
        state.update({
            "scope_mode": "manual",
            "analysis_scope_start_second": chosen_start,
            "analysis_scope_end_second": chosen_end,
            "scope_confirmed": True,
        })
    elif mode in {"auto", "multiple"} and bool(state.get("multiple_match_candidates")):
        candidates = list(state.get("match_candidates") or [])
        first = float(candidates[0].get("first_second") or source_start_second or 0.0) if candidates else float(source_start_second or 0.0)
        last = float(candidates[-1].get("last_second") or source_duration_seconds or 0.0) if candidates else float(source_duration_seconds or 0.0)
        _write_state(root, state)
        return JSONResponse({
            "ok": True,
            "needs_match_selection": True,
            "message": "Plusieurs matchs plausibles ont été détectés. Choisis la plage avant consolidation.",
            "match_candidates": candidates,
            "suggested_start": max(0.0, first - 30.0),
            "suggested_end": max(first + 60.0, min(float(source_duration_seconds or last + 900.0), last + 900.0)),
        })
    _write_state(root, state)

    source_path = root / "capture.webm"
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Capture video is missing for this session.")
    if source_path.stat().st_size < 64 * 1024:
        raise HTTPException(status_code=422, detail="Capture too short: no usable video frames were received.")

    if state.get("status") in {"queued_finalization", "finalizing"}:
        return JSONResponse({
            "ok": True,
            "accepted": True,
            "analysis_percent": max(91.0, float(state.get("analysis_percent") or 0.0)),
            "status_url": f"/matches/{match_id}/analysis/browser-capture/status?session_id={session_id}",
            "redirect": f"/matches/{match_id}/analysis/result",
        })

    start = max(0.0, float(state.get("source_start_second") or source_start_second or 0.0))
    total_duration = max(0.0, float(state.get("source_duration_seconds") or source_duration_seconds or 0.0))
    rate = max(1.0, min(4.0, float(state.get("playback_rate") or playback_rate or 1.0)))
    segments = v10.v7._segments(state.get("parallel_segments") or parallel_segments)
    coverage = live_frame_coverage(root, state)
    state.update({
        "status": "queued_finalization",
        "phase": (
            "dernier fragment reçu · finalisation IA depuis les images live"
            if coverage.get("eligible")
            else "dernier fragment reçu · vérification finale vidéo"
        ),
        "analysis_percent": 91.0,
        "read_percent": 100.0,
        "v13_live_frame_coverage": coverage,
    })
    _write_state(root, state)
    match.status = "browser_capture_finalizing"
    marker = v11._finalize_marker(db, match_id)
    marker.progress = max(91, int(marker.progress or 0))
    marker.message = "Capture reçue · finalisation IA accélérée en cours"
    db.commit()

    background_tasks.add_task(
        _core_fast_finalize_job,
        match_id,
        str(root),
        start,
        total_duration,
        rate,
        segments,
    )
    background_tasks.add_task(v11._close_finalize_marker, match_id, str(root))
    background_tasks.add_task(_enrich_after_report, match_id, str(root))

    return JSONResponse({
        "ok": True,
        "accepted": True,
        "analysis_percent": 91.0,
        "status_url": f"/matches/{match_id}/analysis/browser-capture/status?session_id={session_id}",
        "redirect": f"/matches/{match_id}/analysis/result",
        "fast_finalization": bool(coverage.get("eligible")),
        "retained_live_frames": int(coverage.get("records") or 0),
    })
