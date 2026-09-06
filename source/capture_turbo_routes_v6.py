"""V6 capture routing: multi-match selection is always timeline-correct.

A 4-pane Turbo capture encodes four source ranges into one mosaic. If OCR later
finds several matches, reinterpreting that already-encoded mosaic with a new
range would be chronologically wrong. V6 therefore asks the user to relaunch
only the selected source range; it never remaps the old mosaic as another match.
"""
from __future__ import annotations

import json
import shutil

from fastapi import Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from db import get_db
from analysis_product_routes import _capture_session_dir, _owned_match
from capture_turbo_routes_v5 import (
    turbo_append_chunk,
    turbo_capture_status,
    turbo_create_session,
    turbo_progress_frame,
)
from capture_turbo_routes_v5 import turbo_browser_capture_page as _v5_page
from capture_turbo_routes_v5 import turbo_finish_capture as _v5_finish


def _json_body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    response = _v5_page(match_id=match_id, request=request, db=db)
    html = bytes(response.body).decode("utf-8")
    # Capture-phase handler prevents the V5 same-mosaic retry and reloads the
    # Studio on the exact source range. The next capture then has correct pane
    # chronology and can be consolidated normally.
    patch = f'''
<script>
(() => {{
  document.addEventListener('click', (event) => {{
    const target = event.target && event.target.closest ? event.target.closest('#scopeRetryBtn') : null;
    if(!target) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const start = Math.max(0, Number((document.getElementById('scopeRetryStart')||{{}}).value || 0));
    const end = Math.max(0, Number((document.getElementById('scopeRetryEnd')||{{}}).value || 0));
    const status = document.getElementById('scopeRetryStatus');
    if(!(end > start)) {{ if(status) status.textContent='Indique une fin supérieure au début.'; return; }}
    if(status) status.textContent='Plage choisie. Préparation d’une capture ciblée du seul match…';
    const q = new URLSearchParams({{scope_mode:'manual', scope_start:String(start), scope_end:String(end)}});
    location.href = '/matches/{match_id}/analysis/browser-capture?' + q.toString();
  }}, true);
}})();
</script>
'''
    html = html.replace(
        "Plusieurs matchs possibles — choisis le match à analyser",
        "Plusieurs matchs possibles — choisis la plage du match à analyser",
    )
    html = html.replace("</body>", patch + "</body>") if "</body>" in html else html + patch
    return HTMLResponse(html)


def turbo_finish_capture(
    match_id: int,
    request: Request,
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
    response = _v5_finish(
        match_id=match_id,
        request=request,
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
    payload = _json_body(response)
    if payload.get("needs_match_selection"):
        # The full multi-match capture is not reused with a different timeline.
        # Free it now; V6 will capture only the chosen match range on reload.
        user, match = _owned_match(match_id, request, db)
        shutil.rmtree(_capture_session_dir(user, match, session_id), ignore_errors=True)
        payload["recapture_selected_range"] = True
        payload["message"] = (
            "Plusieurs matchs plausibles ont été détectés. Choisis la plage : "
            "AquaMetric relancera une capture ciblée pour ne jamais mélanger les rencontres."
        )
        return JSONResponse(payload)
    return response
