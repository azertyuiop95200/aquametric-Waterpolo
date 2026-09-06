"""V10 browser capture: faster truthful finalization with adaptive quality warmup.

V10 keeps V9's real decoded-frame progress and background handoff, then reduces
redundant final rescanning when the live pass already produced dense coverage.
It also replaces the fixed 2.8 s YouTube warmup with a quality-aware warmup:
players warm at x1, recording starts as soon as all active players are stable,
and automatic quality pauses resume when the embedded stream recovers (bounded
so a permanently low-quality replay cannot block the analysis forever).
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from analysis_product_routes import EVIDENCE_DIR, UPLOAD_DIR, _capture_session_dir, _owned_match
from capture_turbo_routes import _FAST_CAPTURE_SENTINEL, _read_state, _write_state
from capture_turbo_routes_v7 import _cleanup_pixels_keep_state, _segments
from capture_turbo_routes_v9 import (
    turbo_append_chunk,
    turbo_capture_status,
    turbo_create_session,
    turbo_progress_frame,
)
from capture_turbo_routes_v9 import turbo_browser_capture_page as _v9_page
from db import SessionLocal, get_db
from models import Match
from services.browser_capture_media import normalize_browser_capture
from services.deep_analysis_sequences import materialize_deep_sequence_pack
from services.mosaic_match_analysis import run_mosaic_analysis
from services.rapid_match_analysis import run_rapid_analysis

log = logging.getLogger("aquametric.browser_capture.v10")


def _final_scan_budget(state: dict, start: float, total_duration: float, segments: int) -> tuple[int, int, str]:
    """Choose a small verification scan without pretending live samples are final stats.

    The browser already sends decoded JPEG frames throughout playback.  When that
    pass is dense, the final video scan only needs to verify the full timeline and
    materialize the canonical VisionAnalysis.  Sparse/fallback captures retain a
    larger budget.
    """
    span = max(0.0, float(total_duration or 0.0) - float(start or 0.0))
    progressive = max(
        int(state.get("progressive_samples") or 0),
        int(state.get("saved_live_frames") or 0),
    )
    if progressive >= 80 and segments >= 4:
        return 120, 24, "dense live coverage"
    if progressive >= 40:
        return 132, 28, "live coverage"
    if span and span <= 1800:
        return 136, 28, "short capture"
    return 144, 32, "fallback verification"


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    response = _v9_page(match_id=match_id, request=request, db=db)
    html = bytes(response.body).decode("utf-8")

    # Do not pay a fixed startup penalty on a healthy replay.  Warm at x1 (not
    # x2), wait until every active YouTube player is ready and stable twice, then
    # rewind to each segment start when recording actually begins.  The loop is
    # bounded to ~3 s for slow connections.
    html = html.replace(
        "playPlayers();await new Promise(r=>setTimeout(r,2800));pausePlayers();",
        "playPlayers();for(let i=0;i<parallelSegments;i++){try{if(ytReady[i]&&ytPlayers[i])ytPlayers[i].setPlaybackRate(1)}catch(_){}}let warmGood=0;for(let i=0;i<12;i++){await new Promise(r=>setTimeout(r,250));const allReady=ytReady.slice(0,parallelSegments).every(Boolean);if(allReady&&!embeddedQualityPoor())warmGood++;else warmGood=0;if(i>=3&&warmGood>=2)break;}pausePlayers();",
        1,
    )

    # A quality pause now waits for recovery instead of resuming blindly after a
    # fixed delay.  It checks the embedded player quality, but is capped at 6.5 s
    # so a low-resolution source cannot freeze the analysis.
    html = html.replace(
        "clearTimeout(qualityRetryTimer);qualityRetryTimer=setTimeout(()=>resumeAfterQualityPause(),2200);",
        "clearTimeout(qualityRetryTimer);const retryQuality=()=>{const waited=Date.now()-qualityPauseStarted;if(embeddedQualityPoor()&&waited<6500){qualityRetryTimer=setTimeout(retryQuality,900);return}resumeAfterQualityPause()};qualityRetryTimer=setTimeout(retryQuality,1500);",
        1,
    )
    return HTMLResponse(html)


def _fast_finalize_capture_job(match_id: int, root_value: str, start: float, total_duration: float, rate: float, segments: int) -> None:
    root = Path(root_value)
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if not match or not root.is_dir():
            return
        source_path = root / "capture.webm"
        derived_dir = root / "derived"
        derived_dir.mkdir(parents=True, exist_ok=True)
        state = _read_state(root)
        visual_samples, ocr_samples, budget_reason = _final_scan_budget(state, start, total_duration, segments)
        state.update({
            "status": "finalizing",
            "analysis_percent": 90.0,
            "phase": "normalisation rapide de la capture",
            "final_visual_budget": visual_samples,
            "final_ocr_budget": ocr_samples,
            "final_budget_reason": budget_reason,
        })
        _write_state(root, state)

        analysis_source, media_info = normalize_browser_capture(source_path, derived_dir, fast_analysis=True)
        state = _read_state(root)
        state.update({
            "analysis_percent": 92.0,
            "phase": f"Vision/OCR final ciblé · {visual_samples} images max · {ocr_samples} OCR max",
            "media_normalization": media_info.get("normalization", "unknown"),
        })
        _write_state(root, state)

        if segments >= 4 and total_duration > start + 30.0:
            result = run_mosaic_analysis(
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
        else:
            encoded_offset = (_FAST_CAPTURE_SENTINEL + start) if rate >= 1.75 else start
            result = run_rapid_analysis(
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

        match.status = "browser_capture_analyzed"
        db.commit()
        summary = result.get("summary", {}) or {}
        state = _read_state(root)
        state.update({
            "status": "complete",
            "analysis_percent": 100.0,
            "read_percent": 100.0,
            "phase": "rapport Vision prêt",
            "redirect": f"/matches/{match_id}/analysis/result",
            "visual_samples": int(summary.get("visual_samples") or 0),
            "scoreboard_observations": int(summary.get("scoreboard_observations") or 0),
            "parallel_segments": int(summary.get("parallel_segments") or segments),
        })
        _write_state(root, state)

        try:
            materialize_deep_sequence_pack(
                db,
                match,
                UPLOAD_DIR,
                EVIDENCE_DIR,
                max_targets=48,
                max_clips=0,
                max_image_targets=0,
            )
        except Exception as exc:
            state = _read_state(root)
            state["warning"] = f"Rapport principal prêt; enrichissement de séquences partiel: {exc}"
            state["status"] = "partial"
            _write_state(root, state)
            match.status = "browser_capture_analyzed_partial"
            db.commit()
        finally:
            _cleanup_pixels_keep_state(root)
    except Exception as exc:
        log.exception("V10 async browser capture finalization failed match=%s", match_id)
        try:
            state = _read_state(root)
            state.update({
                "status": "failed",
                "phase": "échec de la consolidation finale · capture conservée pour reprise",
                "analysis_percent": max(90.0, float(state.get("analysis_percent") or 0.0)),
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
    db: Session = Depends(get_db),
):
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    if not root.is_dir():
        raise HTTPException(status_code=404, detail="Capture session expired or not found.")

    state = _read_state(root)
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
        _write_state(root, state)
    elif mode in {"auto", "multiple"} and bool(state.get("multiple_match_candidates")):
        candidates = list(state.get("match_candidates") or [])
        first = float(candidates[0].get("first_second") or source_start_second or 0.0) if candidates else float(source_start_second or 0.0)
        last = float(candidates[-1].get("last_second") or source_duration_seconds or 0.0) if candidates else float(source_duration_seconds or 0.0)
        return JSONResponse({
            "ok": True,
            "needs_match_selection": True,
            "message": "Plusieurs matchs plausibles ont été détectés. Choisis la plage avant consolidation.",
            "match_candidates": candidates,
            "suggested_start": max(0.0, first - 30.0),
            "suggested_end": max(first + 60.0, min(float(source_duration_seconds or last + 900.0), last + 900.0)),
        })

    source_path = root / "capture.webm"
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Capture video is missing for this session.")
    if source_path.stat().st_size < 64 * 1024:
        raise HTTPException(status_code=422, detail="Capture too short: no usable video frames were received.")

    if state.get("status") in {"queued_finalization", "finalizing"}:
        return JSONResponse({
            "ok": True,
            "accepted": True,
            "analysis_percent": max(89.0, float(state.get("analysis_percent") or 0.0)),
            "status_url": f"/matches/{match_id}/analysis/browser-capture/status?session_id={session_id}",
            "redirect": f"/matches/{match_id}/analysis/result",
        })

    start = max(0.0, float(state.get("source_start_second") or source_start_second or 0.0))
    total_duration = max(0.0, float(state.get("source_duration_seconds") or source_duration_seconds or 0.0))
    rate = max(1.0, min(4.0, float(state.get("playback_rate") or playback_rate or 1.0)))
    segments = _segments(state.get("parallel_segments") or parallel_segments)
    state.update({
        "status": "queued_finalization",
        "phase": "dernier fragment reçu · consolidation V10 en arrière-plan",
        "analysis_percent": 89.0,
        "read_percent": 100.0,
    })
    _write_state(root, state)
    match.status = "browser_capture_finalizing"
    db.commit()

    background_tasks.add_task(
        _fast_finalize_capture_job,
        match_id,
        str(root),
        start,
        total_duration,
        rate,
        segments,
    )
    return JSONResponse({
        "ok": True,
        "accepted": True,
        "analysis_percent": 89.0,
        "status_url": f"/matches/{match_id}/analysis/browser-capture/status?session_id={session_id}",
        "redirect": f"/matches/{match_id}/analysis/result",
    })
