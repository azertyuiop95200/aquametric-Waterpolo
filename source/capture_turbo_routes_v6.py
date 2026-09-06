"""V6 capture routing: timeline-safe match scope and truthful final progress."""
from __future__ import annotations

import json
import re
import shutil

from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import AnalysisJob
from analysis_product_routes import _capture_session_dir, _owned_match, _source_start_second
from capture_turbo_routes_v5 import turbo_append_chunk, turbo_create_session, turbo_progress_frame
from capture_turbo_routes_v5 import turbo_browser_capture_page as _v5_page
from capture_turbo_routes_v5 import turbo_capture_status as _v5_status
from capture_turbo_routes_v5 import turbo_finish_capture as _v5_finish


def _json_body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def _patch_full_match_scope(html: str, *, mode: str, embedded_start: float) -> str:
    """Auto/single/multiple means analyse the whole video, not the URL t= marker.

    A YouTube ``t=`` value is a viewing cursor, not proof that the match starts
    there. Only manual scope is allowed to trim the beginning of the analysis.
    """
    if mode == "manual":
        return html

    html = re.sub(
        r'(<input id="sourceStart"[^>]*value=")[^"]+("[^>]*>)',
        r'\g<1>0.0\g<2>',
        html,
        count=1,
    )
    html = re.sub(r"requestedScopeStart=-?\d+(?:\.\d+)?", "requestedScopeStart=0.000", html, count=1)
    html = re.sub(r"requestedScopeEnd=-?\d+(?:\.\d+)?", "requestedScopeEnd=0.000", html, count=1)
    html = html.replace(
        "Si la vidéo contient plusieurs rencontres, AquaMetric compare les bandeaux OCR et demande une plage avant de mélanger deux matchs.",
        "Analyse automatique depuis 0:00 : le t=/start= du lien YouTube sert seulement de curseur d’ouverture et ne coupe jamais le début du match. Si la vidéo contient plusieurs rencontres, AquaMetric compare les bandeaux OCR avant toute consolidation.",
        1,
    )
    if embedded_start > 0:
        html = html.replace(
            "<b>Match ciblé</b>",
            f"<b>Match ciblé · vidéo complète</b><div>Curseur YouTube ignoré pour l’analyse : {embedded_start:.1f} s → départ réel 0.0 s.</div>",
            1,
        )
    return html


def _patch_final_progress_polling(html: str) -> str:
    """Keep /status polling alive while the synchronous /finish job is running.

    V6 already exposes AnalysisJob progress in the 88–99% range. The old client
    stopped polling immediately before /finish, so the UI could look frozen at
    85–88% while the server was actually working. Keep polling until /finish
    resolves, then clear the timer.
    """
    html = html.replace(
        "recorder.onstop=async()=>{clearInterval(tick);clearInterval(statusTick);clearInterval(frameTick);clearInterval(playerTick);",
        "recorder.onstop=async()=>{clearInterval(tick);clearInterval(frameTick);clearInterval(playerTick);",
        1,
    )
    html = html.replace(
        "const payload=await finishAnalysis();if(payload.needs_match_selection){",
        "const payload=await finishAnalysis();clearInterval(statusTick);statusTick=null;if(payload.needs_match_selection){",
        1,
    )
    html = html.replace(
        "}catch(err){leaveStudio();setStatus(`Échec de l’analyse Vision : ${err.message||err}`)}};",
        "}catch(err){clearInterval(statusTick);statusTick=null;leaveStudio();setStatus(`Échec de l’analyse Vision : ${err.message||err}`)}};",
        1,
    )
    html = html.replace(
        "setBars(100,analysisPercent,'Lecture terminée','Consolidation finale Vision/OCR + tactique…');",
        "setBars(100,analysisPercent,'Lecture terminée','Finalisation serveur en cours · progression 88–99 % suivie en direct…');",
        1,
    )
    return html


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    response = _v5_page(match_id=match_id, request=request, db=db)
    html = bytes(response.body).decode("utf-8")
    user, match = _owned_match(match_id, request, db)
    del user
    mode = (request.query_params.get("scope_mode") or "auto").strip().lower()
    if mode not in {"auto", "single", "manual", "multiple"}:
        mode = "auto"
    embedded_start = max(0.0, float(_source_start_second(match.video_url) or 0.0))
    html = _patch_full_match_scope(html, mode=mode, embedded_start=embedded_start)
    html = _patch_final_progress_polling(html)

    patch = f'''
<script>
(() => {{
  document.addEventListener('click', (event) => {{
    const target = event.target && event.target.closest ? event.target.closest('#scopeRetryBtn') : null;
    if(!target) return;
    event.preventDefault(); event.stopImmediatePropagation();
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
    html = html.replace("Plusieurs matchs possibles — choisis le match à analyser", "Plusieurs matchs possibles — choisis la plage du match à analyser")
    html = html.replace("</body>", patch + "</body>") if "</body>" in html else html + patch
    return HTMLResponse(html)


def turbo_capture_status(match_id: int, request: Request, session_id: str, db: Session = Depends(get_db)):
    response = _v5_status(match_id=match_id, request=request, session_id=session_id, db=db)
    payload = _json_body(response)
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else None
    if not progress:
        return response

    # During /finish, run_mosaic_analysis maintains a real AnalysisJob. Surface
    # that backend progress in the 88–99% consolidation window instead of leaving
    # the browser apparently frozen at 85–88%.
    if float(progress.get("analysis_percent") or 0.0) >= 88.0 or progress.get("status") == "finalizing":
        job = db.scalar(
            select(AnalysisJob)
            .where(AnalysisJob.match_id == match_id)
            .order_by(AnalysisJob.id.desc())
        )
        if job and job.status in {"running", "complete", "completed"}:
            raw = max(0, min(100, int(job.progress or 0)))
            mapped = min(99.0, 88.0 + raw * 0.11)
            progress["analysis_percent"] = max(float(progress.get("analysis_percent") or 0.0), round(mapped, 1))
            progress["phase"] = job.message or progress.get("phase") or "consolidation Vision/OCR"
            progress["final_job_progress"] = raw
    return JSONResponse({"ok": True, "progress": progress})


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
        user, match = _owned_match(match_id, request, db)
        shutil.rmtree(_capture_session_dir(user, match, session_id), ignore_errors=True)
        payload["recapture_selected_range"] = True
        payload["message"] = (
            "Plusieurs matchs plausibles ont été détectés. Choisis la plage : "
            "AquaMetric relancera une capture ciblée pour ne jamais mélanger les rencontres."
        )
        return JSONResponse(payload)
    return response
