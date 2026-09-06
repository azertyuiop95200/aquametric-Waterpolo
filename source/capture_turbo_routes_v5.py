"""V5 browser-capture wrappers: prove real video pixels before claiming analysis.

The underlying V4 pipeline already performs browser capture, progressive Vision/OCR,
full WebM analysis and resilient report preservation. V5 adds a hard, user-visible
server state: ``video_confirmed`` only becomes true after OpenCV has successfully
decoded an actual progress JPEG sent from the captured browser stream.
"""
from __future__ import annotations

import json

from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from db import get_db
from analysis_product_routes import TEMPLATES, _capture_session_dir, _owned_match, _source_start_second
from capture_turbo_routes import _read_state, _write_state
from capture_turbo_routes import turbo_append_chunk as _append_chunk
from capture_turbo_routes import turbo_capture_status as _capture_status
from capture_turbo_routes import turbo_create_session as _create_session
from capture_turbo_routes import turbo_progress_frame as _progress_frame
from capture_turbo_routes_v4 import turbo_finish_capture


def _json_body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    if not match.video_url:
        raise HTTPException(status_code=400, detail="This capture mode requires a video URL.")
    html = TEMPLATES.env.get_template("browser_capture_v4.html").render(
        request=request,
        user=user,
        app_name="AquaMetric",
        match=match,
        source_start_second=_source_start_second(match.video_url),
    )
    # Keep the stable V4 template while making the truth state explicit. The UI
    # must not claim that AI analysis is running before the server decodes pixels.
    html = html.replace(
        '<div class="capture-warning"><b>Rapport prioritaire :</b>',
        '<div class="capture-permission" id="videoProofState"><b>Vidéo réelle</b><div>En attente d’une image vidéo décodée côté serveur.</div></div>\n    <div class="capture-warning"><b>Rapport prioritaire :</b>',
        1,
    )
    html = html.replace(
        "Vision/OCR démarre dès les premières images capturées.",
        "Analyse IA à 0 % tant qu’aucune image vidéo réelle n’a été décodée côté serveur.",
        1,
    )
    html = html.replace(
        "function applyServerProgress(p){if(Number.isFinite(Number(p.analysis_percent)))",
        "function applyServerProgress(p){if(p.video_confirmed){const proof=document.getElementById('videoProofState');if(proof){proof.innerHTML='<b>Vidéo réelle reçue par l’IA ✓</b><div>Une image issue du flux capturé a été décodée côté serveur.</div>';proof.style.borderLeftColor='#4ade80'}setStatus('Vidéo réelle reçue par l’IA ✓ · analyse Vision/OCR en cours.')}if(Number.isFinite(Number(p.analysis_percent)))",
        1,
    )
    html = html.replace(
        "Capture active · ${parallelSegments} segment(s) · x${playbackRate}. Pré-analyse Vision/OCR démarrée.",
        "Capture active · ${parallelSegments} segment(s) · x${playbackRate}. En attente de la première image vidéo confirmée côté serveur…",
        1,
    )
    return HTMLResponse(html)


def turbo_create_session(
    match_id: int,
    request: Request,
    source_start_second: float = Form(0.0),
    source_duration_seconds: float = Form(0.0),
    playback_rate: float = Form(2.0),
    parallel_segments: int = Form(1),
    db: Session = Depends(get_db),
):
    response = _create_session(
        match_id=match_id,
        request=request,
        source_start_second=source_start_second,
        source_duration_seconds=source_duration_seconds,
        playback_rate=playback_rate,
        parallel_segments=parallel_segments,
        db=db,
    )
    payload = _json_body(response)
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        return response
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    state = _read_state(root)
    state.update({
        "video_confirmed": False,
        "decoded_frame_batches": 0,
        "first_decoded_wall_second": None,
        "video_confirmation": "en attente d'une image vidéo décodée côté serveur",
        "phase": "capture autorisée · attente de la première image vidéo réelle",
        "analysis_percent": 0.0,
    })
    _write_state(root, state)
    return JSONResponse({"ok": True, "session_id": session_id, **state})


def turbo_append_chunk(
    match_id: int,
    request: Request,
    session_id: str = Form(...),
    index: int = Form(...),
    chunk: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return _append_chunk(
        match_id=match_id,
        request=request,
        session_id=session_id,
        index=index,
        chunk=chunk,
        db=db,
    )


def turbo_progress_frame(
    match_id: int,
    request: Request,
    session_id: str = Form(...),
    wall_second: float = Form(...),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # The base route rejects malformed/non-decodable images with HTTP 400. We only
    # set video_confirmed AFTER that successful OpenCV decode and real frame pass.
    _progress_frame(
        match_id=match_id,
        request=request,
        session_id=session_id,
        wall_second=wall_second,
        frame=frame,
        db=db,
    )
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    state = _read_state(root)
    batches = max(
        int(state.get("decoded_frame_batches") or 0) + 1,
        int(state.get("progressive_frame_batches") or 0),
    )
    state["video_confirmed"] = True
    state["decoded_frame_batches"] = batches
    if state.get("first_decoded_wall_second") is None:
        state["first_decoded_wall_second"] = round(max(0.0, float(wall_second or 0.0)), 2)
    state["video_confirmation"] = "Vidéo réelle reçue par l’IA ✓"
    state["phase"] = "Vidéo réelle reçue par l’IA ✓ · lecture + pré-analyse IA en parallèle"
    # A successful decoded frame is the first moment at which the UI may honestly
    # report non-zero AI progress. Keep at least 1% even when source duration is
    # unknown, while preserving the richer percentage computed by the base route.
    state["analysis_percent"] = max(1.0, float(state.get("analysis_percent") or 0.0))
    _write_state(root, state)
    return JSONResponse({"ok": True, "progress": state})


def turbo_capture_status(
    match_id: int,
    request: Request,
    session_id: str,
    db: Session = Depends(get_db),
):
    return _capture_status(
        match_id=match_id,
        request=request,
        session_id=session_id,
        db=db,
    )
