"""V11 browser capture: never strand the user at 88/89%.

Production evidence showed that real chunks and the /finish request reached the
server, while the browser stopped polling immediately afterwards. V11 makes the
post-finish wait independent from the older string-patch chain by installing a
small fetch watchdog before the Studio script runs. It also writes a durable
AnalysisJob marker before the background handoff so History is never empty while
the final Vision pass is running.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

import capture_turbo_routes_v10 as v10
from analysis_product_routes import _capture_session_dir, _owned_match
from capture_turbo_routes import _read_state
from capture_turbo_routes_v9 import turbo_append_chunk, turbo_create_session, turbo_progress_frame
from db import SessionLocal, get_db
from models import AnalysisJob

log = logging.getLogger("aquametric.browser_capture.v11")


def _body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def _finalize_marker(db: Session, match_id: int) -> AnalysisJob:
    marker = db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.match_id == match_id, AnalysisJob.stage == "browser_capture_finalize_v11")
        .order_by(AnalysisJob.id.desc())
    )
    if marker and marker.status in {"queued", "running"}:
        marker.progress = max(89, int(marker.progress or 0))
        marker.status = "running"
        marker.message = "Capture reçue · consolidation Vision/OCR en cours"
        return marker
    marker = AnalysisJob(
        match_id=match_id,
        stage="browser_capture_finalize_v11",
        progress=89,
        status="running",
        message="Capture reçue · consolidation Vision/OCR en cours",
    )
    db.add(marker)
    return marker


def _close_finalize_marker(match_id: int, root_value: str) -> None:
    """Runs after V10's finalizer because BackgroundTasks preserves insertion order."""
    db = SessionLocal()
    try:
        marker = db.scalar(
            select(AnalysisJob)
            .where(AnalysisJob.match_id == match_id, AnalysisJob.stage == "browser_capture_finalize_v11")
            .order_by(AnalysisJob.id.desc())
        )
        if not marker:
            return
        state = _read_state(Path(root_value))
        status = str(state.get("status") or "")
        if status in {"complete", "partial"}:
            marker.progress = 100
            marker.status = "complete" if status == "complete" else "partial"
            marker.message = str(state.get("phase") or "Rapport Vision prêt")
            log.info(
                "V11 browser capture report ready match=%s status=%s samples=%s scoreboard=%s",
                match_id,
                status,
                state.get("visual_samples"),
                state.get("scoreboard_observations"),
            )
        elif status == "failed":
            marker.progress = max(90, int(marker.progress or 0))
            marker.status = "failed"
            marker.message = str(state.get("error") or "Échec de la consolidation finale")
            log.error("V11 browser capture report failed match=%s error=%s", match_id, marker.message)
        else:
            marker.progress = max(90, int(marker.progress or 0))
            marker.status = "failed"
            marker.message = "La tâche de consolidation s'est arrêtée avant la publication du rapport."
            log.error("V11 browser capture finalizer ended without terminal state match=%s state=%s", match_id, status)
        db.commit()
    finally:
        db.close()


def _watchdog_script(match_id: int) -> str:
    """Fetch interceptor installed before the legacy Studio IIFE.

    This is intentionally independent from the generated Studio variables. If a
    future UI refactor changes recorder.onstop, every successful /finish response
    still starts authoritative status polling and redirects only after the server
    reports complete/partial.
    """
    return f"""
<script id="aquametric-v11-final-watchdog">
(() => {{
  if (window.__aqV11FinalWatchdogInstalled) return;
  window.__aqV11FinalWatchdogInstalled = true;
  const nativeFetch = window.fetch.bind(window);
  let watcherStarted = false;
  const finishNeedle = '/matches/{match_id}/analysis/browser-capture/finish';

  function setFinalUi(percent, text) {{
    const pct = Math.max(89, Math.min(100, Number(percent) || 89));
    ['analysisPct','analysisPctLive'].forEach(id => {{ const n=document.getElementById(id); if(n) n.textContent=Math.round(pct)+'%'; }});
    ['analysisBar','analysisBarLive'].forEach(id => {{ const n=document.getElementById(id); if(n) n.style.width=pct+'%'; }});
    ['status','statusStatic'].forEach(id => {{ const n=document.getElementById(id); if(n && text) n.textContent=text; }});
    const meta=document.getElementById('analysisMeta'); if(meta && text) meta.textContent=text;
  }}

  async function pollUntilPublished(payload) {{
    if (watcherStarted || !payload || !payload.accepted || !payload.status_url) return;
    watcherStarted = true;
    setFinalUi(payload.analysis_percent || 89, 'Capture terminée · publication du rapport en cours…');
    for (let attempt=0; attempt<300; attempt++) {{
      try {{
        const r = await nativeFetch(payload.status_url, {{cache:'no-store', credentials:'same-origin'}});
        const out = await r.json().catch(() => ({{}}));
        const p = out.progress || {{}};
        const state = String(p.status || '');
        const pct = Number(p.analysis_percent || payload.analysis_percent || 89);
        setFinalUi(pct, p.phase || 'Consolidation Vision/OCR en cours…');
        if (state === 'complete' || state === 'partial') {{
          setFinalUi(100, state === 'partial' ? 'Rapport publié · enrichissement partiel' : 'Rapport publié');
          window.location.replace(p.redirect || payload.redirect || '/matches/{match_id}/analysis/result');
          return;
        }}
        if (state === 'failed') {{
          setFinalUi(Math.max(90,pct), 'Échec de consolidation : ' + (p.error || 'capture conservée pour reprise'));
          watcherStarted = false;
          return;
        }}
      }} catch (_) {{ /* transient poll errors are retried */ }}
      await new Promise(resolve => setTimeout(resolve, 600));
    }}
    setFinalUi(90, 'La consolidation prend plus de temps que prévu. Le rapport reste en cours et la capture est conservée.');
    watcherStarted = false;
  }}

  window.fetch = async function(input, init) {{
    const response = await nativeFetch(input, init);
    try {{
      const url = typeof input === 'string' ? input : String((input && input.url) || '');
      if (url.includes(finishNeedle) && response.ok) {{
        const payload = await response.clone().json();
        if (payload && payload.accepted) void pollUntilPublished(payload);
      }}
    }} catch (_) {{}}
    return response;
  }};
}})();
</script>
"""


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    response = v10.turbo_browser_capture_page(match_id=match_id, request=request, db=db)
    html = bytes(response.body).decode("utf-8")
    watchdog = _watchdog_script(match_id)
    # Install before all Studio scripts so it cannot lose the /finish response.
    if "</head>" in html:
        html = html.replace("</head>", watchdog + "\n</head>", 1)
    else:
        html = watchdog + html
    return HTMLResponse(html)


def turbo_capture_status(
    match_id: int,
    request: Request,
    session_id: str,
    db: Session = Depends(get_db),
):
    response = v10.turbo_capture_status(match_id=match_id, request=request, session_id=session_id, db=db)
    payload = _body(response)
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else None
    if not progress:
        return response
    marker = db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.match_id == match_id, AnalysisJob.stage == "browser_capture_finalize_v11")
        .order_by(AnalysisJob.id.desc())
    )
    if marker:
        progress["finalization_job_status"] = marker.status
        progress["finalization_job_progress"] = int(marker.progress or 0)
        if progress.get("status") in {"queued_finalization", "finalizing"}:
            progress["analysis_percent"] = max(
                float(progress.get("analysis_percent") or 0.0),
                min(99.0, float(marker.progress or 0.0)),
            )
            if marker.message:
                progress["phase"] = marker.message
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
    db: Session = Depends(get_db),
):
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    response = v10.turbo_finish_capture(
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
    payload = _body(response)
    if payload.get("accepted"):
        marker = _finalize_marker(db, match_id)
        db.commit()
        log.info(
            "V11 browser capture finish accepted match=%s session=%s marker=%s",
            match_id,
            session_id,
            marker.id,
        )
        # V10 already inserted the real finalizer into this BackgroundTasks list.
        # This closure is appended after it and therefore records the terminal
        # state in History once the report has actually been persisted.
        background_tasks.add_task(_close_finalize_marker, match_id, str(root))
    return response
