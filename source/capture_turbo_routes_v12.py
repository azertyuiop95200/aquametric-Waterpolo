"""V12 browser capture: guarantee the live reader hands off to finalization.

A real production capture on 2026-09-07 kept uploading chunks and polling status
with the AI bar around 87%, but never called /finish.  The decoded live pass was
near the end of the four-pane timeline and one pane never crossed the historical
99.8% client threshold.  V12 adds two independent, evidence-based end guards:

* the browser stops at 99.5%, or after a near-end read stalls for 7 seconds;
* the server status response asks the browser to stop under the same near-end
  conditions, so a future UI refactor cannot silently remove the guard.

A generous elapsed-time deadline is only a last resort and still requires at
least 95% source coverage.  Forced handoffs are recorded in the session state so
coverage is never silently represented as exact when the last source fraction
was not observed.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

import capture_turbo_routes_v11 as v11
from analysis_product_routes import _capture_session_dir, _owned_match
from capture_turbo_routes import _read_state, _write_state
from db import get_db

# Keep the proven V11 data path.  V12 changes only lifecycle/end-of-read logic.
turbo_append_chunk = v11.turbo_append_chunk
turbo_progress_frame = v11.turbo_progress_frame


def _body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def _end_guard_decision(
    *,
    read_percent: float,
    stalled_seconds: float,
    elapsed_seconds: float,
    expected_seconds: float,
) -> tuple[bool, str]:
    """Return whether a running capture should hand off to finalization.

    This helper is intentionally deterministic and unit-testable.  It never
    treats a low-coverage timeout as complete.
    """
    read = max(0.0, min(100.0, float(read_percent or 0.0)))
    stalled = max(0.0, float(stalled_seconds or 0.0))
    elapsed = max(0.0, float(elapsed_seconds or 0.0))
    expected = max(0.0, float(expected_seconds or 0.0))
    if read >= 99.5:
        return True, "near_complete"
    if read >= 98.0 and stalled >= 7.0:
        return True, "near_end_stall"
    if expected > 0.0 and read >= 95.0 and elapsed >= expected + 45.0:
        return True, "deadline_guard"
    return False, ""


def _patch_end_guard(html: str) -> str:
    """Patch the already-rendered V11 Studio without depending on template order."""
    guard_js = r'''
  let v12ReadBest=0,v12ReadChangedAt=0,v12ForcedFinishReason='';
  function v12EndGuard(r){
    const read=Math.max(0,Math.min(100,Number(r)||0)),now=Date.now();
    if(!v12ReadChangedAt||read>v12ReadBest+0.08){v12ReadBest=read;v12ReadChangedAt=now;}
    const active=(typeof activeWallSeconds==='function')?activeWallSeconds():Math.max(0,(now-startedAt)/1000);
    const expected=(sourceDuration>sourceStart)?(sourceDuration-sourceStart)/(Math.max(1,playbackRate)*Math.max(1,parallelSegments)):0;
    if(read>=99.5){v12ForcedFinishReason='near_complete';return true;}
    if(read>=98&&v12ReadChangedAt&&now-v12ReadChangedAt>=7000){v12ForcedFinishReason='near_end_stall';return true;}
    if(expected>0&&read>=95&&active>=expected+45){v12ForcedFinishReason='deadline_guard';return true;}
    return false;
  }
  function v12FlushAndStop(reason){
    if(stopping||!recorder||!['recording','paused'].includes(recorder.state))return;
    v12ForcedFinishReason=reason||v12ForcedFinishReason||'server_end_guard';
    setStatus('Fin de lecture détectée · envoi du dernier fragment puis création du rapport…');
    try{if(recorder.state==='recording'&&typeof recorder.requestData==='function')recorder.requestData()}catch(_){}
    requestStop();
  }
'''
    anchor = "  function localReadPercent(){"
    if anchor in html and "function v12EndGuard(" not in html:
        html = html.replace(anchor, guard_js + "\n" + anchor, 1)

    # V7 adds adaptiveQualityGuard() but leaves the historical 99.8% condition.
    old_stop = "if(sourceDuration>sourceStart&&recorder&&recorder.state==='recording'&&r>=99.8&&!stopping)requestStop()"
    if old_stop in html:
        html = html.replace(old_stop, "if(v12EndGuard(r))v12FlushAndStop(v12ForcedFinishReason)", 1)
    else:
        # Defensive fallback for the unpatched V4 shape used by some test builds.
        old_stop = "if(sourceDuration>sourceStart&&recorder&&recorder.state==='recording'&&r>=99.8&&!stopping) requestStop()"
        html = html.replace(old_stop, "if(v12EndGuard(r))v12FlushAndStop(v12ForcedFinishReason)", 1)

    # Server-side status independently tells the browser to stop. requestStop is
    # a function declaration, so it is available here even though defined later.
    marker = "function applyServerProgress(p){"
    if marker in html and "p.force_finish" not in html:
        html = html.replace(
            marker,
            marker + "if(p.force_finish&&!stopping){v12FlushAndStop(p.force_finish_reason||'server_end_guard');}",
            1,
        )

    # Persist the real client read percentage/reason into the finish request.
    finish_tail = "f.append('analysis_scope_end_second',String(requestedScopeEnd||0));return jsonFetch("
    if finish_tail in html and "client_finish_reason" not in html:
        html = html.replace(
            finish_tail,
            "f.append('analysis_scope_end_second',String(requestedScopeEnd||0));f.append('client_read_percent',String(localReadPercent()));f.append('client_finish_reason',v12ForcedFinishReason||'normal');return jsonFetch(",
            1,
        )
    return html


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    response = v11.turbo_browser_capture_page(match_id=match_id, request=request, db=db)
    html = bytes(response.body).decode("utf-8")
    return HTMLResponse(_patch_end_guard(html))


def turbo_create_session(
    match_id: int,
    request: Request,
    source_start_second: float = Form(0.0),
    source_duration_seconds: float = Form(0.0),
    playback_rate: float = Form(2.0),
    parallel_segments: int = Form(1),
    scope_mode: str = Form("auto"),
    analysis_scope_start_second: float = Form(0.0),
    analysis_scope_end_second: float = Form(0.0),
    db: Session = Depends(get_db),
):
    response = v11.turbo_create_session(
        match_id=match_id,
        request=request,
        source_start_second=source_start_second,
        source_duration_seconds=source_duration_seconds,
        playback_rate=playback_rate,
        parallel_segments=parallel_segments,
        scope_mode=scope_mode,
        analysis_scope_start_second=analysis_scope_start_second,
        analysis_scope_end_second=analysis_scope_end_second,
        db=db,
    )
    payload = _body(response)
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        return response
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    state = _read_state(root)
    now = time.time()
    state.update({
        "v12_started_at": now,
        "v12_last_progress_at": now,
        "v12_last_read_percent": 0.0,
        "v12_end_guard": True,
    })
    _write_state(root, state)
    return JSONResponse({"ok": True, "session_id": session_id, **state})


def turbo_capture_status(
    match_id: int,
    request: Request,
    session_id: str,
    db: Session = Depends(get_db),
):
    response = v11.turbo_capture_status(match_id=match_id, request=request, session_id=session_id, db=db)
    payload = _body(response)
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else None
    if not progress:
        return response
    status = str(progress.get("status") or "")
    if status in {"complete", "partial", "failed", "queued_finalization", "finalizing"}:
        return response

    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    if not root.is_dir():
        return response
    state = _read_state(root)
    now = time.time()
    read = max(0.0, min(100.0, float(progress.get("read_percent") or state.get("read_percent") or 0.0)))
    last_read = max(0.0, float(state.get("v12_last_read_percent") or 0.0))
    last_at = float(state.get("v12_last_progress_at") or state.get("v12_started_at") or now)
    if read > last_read + 0.08:
        last_read = read
        last_at = now
        state["v12_last_read_percent"] = read
        state["v12_last_progress_at"] = now
    started = float(state.get("v12_started_at") or now)
    expected = max(0.0, float(state.get("expected_capture_seconds") or 0.0))
    force, reason = _end_guard_decision(
        read_percent=read,
        stalled_seconds=now - last_at,
        elapsed_seconds=now - started,
        expected_seconds=expected,
    )
    if force:
        progress["force_finish"] = True
        progress["force_finish_reason"] = reason
        progress["phase"] = "fin de lecture confirmée · fermeture automatique de la capture"
        state["v12_force_finish"] = True
        state["v12_force_finish_reason"] = reason
        state["v12_force_finish_read_percent"] = round(read, 3)
    _write_state(root, state)
    return JSONResponse({"ok": True, "progress": progress})


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
    if root.is_dir():
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
        _write_state(root, state)

    return v11.turbo_finish_capture(
        match_id=match_id,
        request=request,
        background_tasks=background_tasks,
        session_id=session_id,
        source_start_second=source_start_second,
        source_duration_seconds=source_duration_seconds,
        playback_rate=playback_rate,
        parallel_segments=parallel_segments,
        scope_mode=scope_mode,
        analysis_scope_start_second=analysis_scope_start_second,
        analysis_scope_end_second=analysis_scope_end_second,
        db=db,
    )
