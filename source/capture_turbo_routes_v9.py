"""V9 browser capture bindings.

This layer keeps the V7/V8 async analysis and quality protection, while fixing
production stalls and misleading progress:
- live AI progress no longer plateaus around 85% while the last video seconds are
  still being read;
- /finish acknowledges the background consolidation immediately with HTTP 200;
- multi-match scope selection is evaluated before requiring capture bytes;
- final 90–99% progress only follows a currently running analysis job, never a
  completed job left over from an earlier run.
"""
from __future__ import annotations

from fastapi import BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis_product_routes import _capture_session_dir, _owned_match
from capture_turbo_routes import _read_state, _write_state
from capture_turbo_routes_v7 import _finalize_capture_job, _segments
from capture_turbo_routes_v8 import (
    turbo_append_chunk,
    turbo_browser_capture_page,
    turbo_create_session,
)
from capture_turbo_routes_v7 import turbo_progress_frame as _v7_progress_frame
from db import get_db
from models import AnalysisJob


def _json_body(response) -> dict:
    try:
        import json
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
    """Keep live progress moving continuously into the async handoff window."""
    response = _v7_progress_frame(
        match_id=match_id,
        request=request,
        session_id=session_id,
        wall_second=wall_second,
        frame=frame,
        db=db,
    )
    payload = _json_body(response)
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else None
    if not progress:
        return response

    read = max(0.0, min(100.0, float(progress.get("read_percent") or 0.0)))
    # The previous pre-analysis ceiling yielded ~85.1% at its 99% read cap.
    # This value is still backed only by decoded live frames and stays below the
    # 89% finalization handoff.
    moving = min(87.5, read * 0.884)
    progress["analysis_percent"] = max(float(progress.get("analysis_percent") or 0.0), round(moving, 1))
    if read >= 98.0:
        progress["phase"] = "dernières images live + préparation du dernier fragment"

    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    state = _read_state(root)
    state.update(progress)
    _write_state(root, state)
    return JSONResponse({"ok": True, "progress": progress})


def turbo_capture_status(
    match_id: int,
    request: Request,
    session_id: str,
    db: Session = Depends(get_db),
):
    """Return session progress without inheriting stale jobs from older runs."""
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    if not root.is_dir():
        return JSONResponse({"ok": False, "status": "finished_or_expired"})
    state = _read_state(root)
    status = str(state.get("status") or "")

    if status in {"queued_finalization", "finalizing"}:
        job = db.scalar(
            select(AnalysisJob)
            .where(AnalysisJob.match_id == match_id)
            .order_by(AnalysisJob.id.desc())
        )
        if job and str(job.status or "") == "running":
            raw = max(0, min(100, int(job.progress or 0)))
            mapped = min(99.0, 92.0 + raw * 0.07)
            state["analysis_percent"] = max(float(state.get("analysis_percent") or 0.0), round(mapped, 1))
            state["phase"] = job.message or state.get("phase") or "Vision/OCR final ciblé"
            state["final_job_progress"] = raw
    if status in {"complete", "partial"}:
        state.setdefault("redirect", f"/matches/{match_id}/analysis/result")
    return JSONResponse({"ok": True, "progress": state})


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
        "phase": "dernier fragment reçu · consolidation rapide en arrière-plan",
        "analysis_percent": 89.0,
        "read_percent": 100.0,
    })
    _write_state(root, state)
    match.status = "browser_capture_finalizing"
    db.commit()

    background_tasks.add_task(
        _finalize_capture_job,
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
