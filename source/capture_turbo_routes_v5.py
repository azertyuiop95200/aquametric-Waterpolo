"""V5 browser-capture wrappers: truthful pixels, multi-match scope and retry.

AquaMetric only reports AI progress after OpenCV decodes real captured pixels.
This layer also keeps a best-effort OCR record of title/scoreboard banners so a
long video containing several matches can be flagged before final consolidation.
"""
from __future__ import annotations

import json
import re
import unicodedata

import cv2
import numpy as np
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from db import get_db
from analysis_product_routes import TEMPLATES, _capture_session_dir, _owned_match, _source_start_second
from capture_turbo_routes import (
    _MAX_PROGRESS_FRAME_BYTES,
    _pane,
    _progressive_frame_analysis,
    _read_state,
    _write_state,
)
from capture_turbo_routes import turbo_append_chunk as _append_chunk
from capture_turbo_routes import turbo_capture_status as _capture_status
from capture_turbo_routes import turbo_create_session as _create_session
from capture_turbo_routes_v4 import turbo_finish_capture as _finish_capture
from services.scoreboard_ocr import ocr_image, tesseract_available


def _json_body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def _number(value, default=0.0) -> float:
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return float(default)


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _team_tokens(value: str) -> set[str]:
    stop = {"water", "polo", "club", "wp", "sc", "cn", "team", "feminin", "feminine", "masculin"}
    return {token for token in _fold(value).split() if len(token) >= 3 and token not in stop}


def _banner_signature(text: str) -> str:
    stop = {
        "period", "periode", "quarter", "match", "water", "polo", "live", "score",
        "plus", "videos", "video", "youtube", "samedi", "dimanche", "septembre",
    }
    words = [w for w in _fold(text).split() if len(w) >= 3 and not w.isdigit() and w not in stop]
    return " ".join(sorted(dict.fromkeys(words)))[:140]


def _source_second_for_pane(state: dict, wall_second: float, pane_index: int, segments: int) -> float:
    start = max(0.0, _number(state.get("source_start_second")))
    end = max(start, _number(state.get("source_duration_seconds")))
    rate = max(1.0, _number(state.get("playback_rate"), 1.0))
    if end <= start:
        return start + max(0.0, wall_second) * rate
    span = (end - start) / max(1, segments)
    return min(end, start + pane_index * span + max(0.0, wall_second) * rate)


def _observe_match_banners(root, image: np.ndarray, wall_second: float, match) -> dict:
    state = _read_state(root)
    if not state or not tesseract_available():
        return state
    last = _number(state.get("last_banner_ocr_wall_second"), -999.0)
    if wall_second - last < 15.0:
        return state
    segments = 4 if int(state.get("parallel_segments") or 1) >= 4 else (2 if int(state.get("parallel_segments") or 1) >= 2 else 1)
    team_a = _team_tokens(getattr(match.team, "name", ""))
    team_b = _team_tokens(getattr(match, "opponent", ""))
    candidates = list(state.get("match_candidates") or [])
    raw_samples = list(state.get("banner_text_samples") or [])

    for idx in range(segments):
        pane = _pane(image, idx, segments)
        if pane.size == 0:
            continue
        h = pane.shape[0]
        bands = [pane[: max(1, int(h * 0.30)), :], pane[max(0, int(h * 0.70)) :, :]]
        best = None
        for band in bands:
            text, confidence = ocr_image(band)
            clean = " ".join((text or "").split())
            if len(clean) < 4:
                continue
            if best is None or float(confidence) > best[0]:
                best = (float(confidence), clean)
        if not best or best[0] < 0.12:
            continue
        confidence, text = best
        second = round(_source_second_for_pane(state, wall_second, idx, segments), 2)
        folded = _fold(text)
        signature = _banner_signature(text)
        hit_a = bool(team_a and any(token in folded for token in team_a))
        hit_b = bool(team_b and any(token in folded for token in team_b))
        target = bool(hit_a and hit_b)
        raw_samples.append({"second": second, "pane": idx + 1, "text": text[:180], "confidence": round(confidence, 3), "target": target})
        if target:
            state["target_match_banner_seen"] = True
        if not signature or len(signature) < 5:
            continue
        existing = next((c for c in candidates if c.get("signature") == signature), None)
        if existing:
            existing["first_second"] = min(float(existing.get("first_second") or second), second)
            existing["last_second"] = max(float(existing.get("last_second") or second), second)
            existing["confidence"] = max(float(existing.get("confidence") or 0.0), confidence)
            existing["target"] = bool(existing.get("target") or target)
            if confidence >= float(existing.get("confidence") or 0.0):
                existing["label"] = text[:110]
        else:
            candidates.append({
                "signature": signature,
                "label": text[:110],
                "first_second": second,
                "last_second": second,
                "confidence": round(confidence, 3),
                "target": target,
            })

    # Keep only substantial, chronologically useful observations. This is a
    # prompt-to-choose mechanism, not an assertion that OCR identified official teams.
    candidates = sorted(candidates, key=lambda c: float(c.get("first_second") or 0.0))[:12]
    state["match_candidates"] = candidates
    state["banner_text_samples"] = raw_samples[-48:]
    state["last_banner_ocr_wall_second"] = round(float(wall_second), 2)
    state["multiple_match_candidates"] = len(candidates) >= 2
    _write_state(root, state)
    return state


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    if not match.video_url:
        raise HTTPException(status_code=400, detail="This capture mode requires a video URL.")
    mode = (request.query_params.get("scope_mode") or "auto").lower()
    try:
        scope_start = max(0.0, float(request.query_params.get("scope_start") or _source_start_second(match.video_url)))
    except (TypeError, ValueError):
        scope_start = _source_start_second(match.video_url)
    try:
        scope_end = max(0.0, float(request.query_params.get("scope_end") or 0.0))
    except (TypeError, ValueError):
        scope_end = 0.0

    html = TEMPLATES.env.get_template("browser_capture_v4.html").render(
        request=request,
        user=user,
        app_name="AquaMetric",
        match=match,
        source_start_second=scope_start,
        scope_end_second=scope_end,
        scope_mode=mode,
    )
    scope_panel = f'''<div class="capture-permission" id="matchScopeState"><b>Match ciblé</b><div>{match.team.name} vs {match.opponent} · {getattr(match.team, 'category', '') or 'catégorie non précisée'}. Portée: {mode}.</div><div style="margin-top:8px">Si la vidéo contient plusieurs rencontres, AquaMetric compare les bandeaux OCR et demande une plage avant de mélanger deux matchs.</div></div>'''
    html = html.replace(
        '<div class="capture-warning"><b>Rapport prioritaire :</b>',
        '<div class="capture-permission" id="videoProofState"><b>Vidéo réelle</b><div>En attente d’une image vidéo décodée côté serveur.</div></div>\n    ' + scope_panel + '\n    <div class="capture-warning"><b>Rapport prioritaire :</b>',
        1,
    )
    html = html.replace(
        "Vision/OCR démarre dès les premières images capturées.",
        "Analyse IA à 0 % tant qu’aucune image vidéo réelle n’a été décodée côté serveur.",
        1,
    )
    # Scope values are explicit JS state. A manual end caps the YouTube duration so
    # Turbo reads only the selected match instead of the rest of a multi-match video.
    html = html.replace(
        "let mode='turbo',playbackRate=2,parallelSegments=4,sourceStart=Math.max(0,Number(sourceStartInput.value||0)),sourceDuration=0;",
        f"let mode='turbo',playbackRate=2,parallelSegments=4,sourceStart=Math.max(0,Number(sourceStartInput.value||0)),sourceDuration=0;let requestedScopeMode={json.dumps(mode)},requestedScopeStart={scope_start:.3f},requestedScopeEnd={scope_end:.3f};",
        1,
    )
    html = html.replace(
        "if(d>sourceStart+30){sourceDuration=d;durationState.textContent=`durée détectée ${fmt(d)}`;",
        "if(d>sourceStart+30){sourceDuration=(requestedScopeEnd>sourceStart&&requestedScopeEnd<=d)?requestedScopeEnd:d;durationState.textContent=`durée détectée ${fmt(d)} · plage analysée ${fmt(sourceStart)} → ${fmt(sourceDuration)}`;",
        1,
    )
    html = html.replace(
        "f.append('parallel_segments',String(parallelSegments));const p=await jsonFetch('/matches/{{match.id}}/analysis/browser-capture/session'",
        "f.append('parallel_segments',String(parallelSegments));f.append('scope_mode',requestedScopeMode);f.append('analysis_scope_start_second',String(requestedScopeStart||sourceStart));f.append('analysis_scope_end_second',String(requestedScopeEnd||0));const p=await jsonFetch('/matches/{{match.id}}/analysis/browser-capture/session'",
        1,
    )
    html = html.replace(
        "f.append('parallel_segments',String(parallelSegments));return jsonFetch('/matches/{{match.id}}/analysis/browser-capture/finish'",
        "f.append('parallel_segments',String(parallelSegments));f.append('scope_mode',requestedScopeMode);f.append('analysis_scope_start_second',String(requestedScopeStart||sourceStart));f.append('analysis_scope_end_second',String(requestedScopeEnd||0));return jsonFetch('/matches/{{match.id}}/analysis/browser-capture/finish'",
        1,
    )
    html = html.replace(
        "function applyServerProgress(p){if(Number.isFinite(Number(p.analysis_percent)))",
        "function applyServerProgress(p){if(p.video_confirmed){const proof=document.getElementById('videoProofState');if(proof){proof.innerHTML='<b>Vidéo réelle reçue par l’IA ✓</b><div>Une image issue du flux capturé a été décodée côté serveur.</div>';proof.style.borderLeftColor='#4ade80'}}const scope=document.getElementById('matchScopeState');if(scope&&Array.isArray(p.match_candidates)&&p.match_candidates.length){const labels=p.match_candidates.slice(0,4).map(c=>`${fmt(c.first_second||0)} · ${c.label||'bandeau détecté'}`);scope.innerHTML='<b>Bandeaux / matchs détectés</b><div>'+labels.join('<br>')+(p.multiple_match_candidates?'<br><b>Plusieurs rencontres possibles : une plage sera demandée avant consolidation si nécessaire.</b>':'')+'</div>';}if(Number.isFinite(Number(p.analysis_percent)))",
        1,
    )
    # Do not launch final consolidation while a live JPEG OCR request is still in flight.
    html = html.replace(
        "async function finishAnalysis(){await uploadChain;if(uploadError)throw uploadError;",
        "async function finishAnalysis(){await uploadChain;for(let i=0;i<150&&frameBusy;i++)await new Promise(r=>setTimeout(r,100));if(uploadError)throw uploadError;",
        1,
    )
    # A 200 response can request match selection instead of falsely declaring 100%.
    html = html.replace(
        "const payload=await finishAnalysis();analysisPercent=100;",
        "const payload=await finishAnalysis();if(payload.needs_match_selection){leaveStudio();analysisPercent=Math.min(88,analysisPercent);setBars(100,analysisPercent,'Lecture terminée','Plusieurs matchs détectés · choisis la plage à analyser');showMatchScopeChooser(payload);return;}analysisPercent=100;",
        1,
    )
    chooser_js = '''
  function showMatchScopeChooser(payload){
    const box=document.getElementById('matchScopeState');if(!box)return;
    const rows=(payload.match_candidates||[]).map(c=>`<div style="margin:5px 0"><b>${fmt(c.first_second||0)}</b> · ${(c.label||'Bandeau détecté').replace(/[<>]/g,'')}</div>`).join('');
    box.innerHTML=`<b>Plusieurs matchs possibles — choisis le match à analyser</b>${rows}<div class="capture-time" style="margin-top:10px"><label>Début <input id="scopeRetryStart" type="number" min="0" step="0.1" value="${payload.suggested_start||sourceStart}"></label><label>Fin <input id="scopeRetryEnd" type="number" min="0" step="0.1" value="${payload.suggested_end||sourceDuration}"></label><button id="scopeRetryBtn" class="btn primary" type="button">Analyser cette plage</button></div><div id="scopeRetryStatus" style="margin-top:8px"></div>`;
    document.getElementById('scopeRetryBtn').onclick=async()=>{const start=Math.max(0,Number(document.getElementById('scopeRetryStart').value||0)),end=Math.max(0,Number(document.getElementById('scopeRetryEnd').value||0));if(!(end>start)){document.getElementById('scopeRetryStatus').textContent='Indique une fin supérieure au début.';return}requestedScopeMode='manual';requestedScopeStart=start;requestedScopeEnd=end;document.getElementById('scopeRetryStatus').textContent='Consolidation du match choisi…';try{const f=new FormData();f.append('session_id',sessionId);f.append('source_start_second',String(sourceStart));f.append('source_duration_seconds',String(sourceDuration));f.append('playback_rate',String(playbackRate));f.append('parallel_segments',String(parallelSegments));f.append('scope_mode','manual');f.append('analysis_scope_start_second',String(start));f.append('analysis_scope_end_second',String(end));const out=await jsonFetch('/matches/{{match.id}}/analysis/browser-capture/finish',{method:'POST',body:f});location.href=out.redirect||'/matches/{{match.id}}/analysis/result'}catch(err){document.getElementById('scopeRetryStatus').textContent='Échec : '+(err.message||err)}};
  }
'''
    html = html.replace("  function requestStop(){", chooser_js + "\n  function requestStop(){", 1)
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
    scope_mode: str = Form("auto"),
    analysis_scope_start_second: float = Form(0.0),
    analysis_scope_end_second: float = Form(0.0),
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
        "scope_mode": scope_mode if scope_mode in {"auto", "single", "manual", "multiple"} else "auto",
        "analysis_scope_start_second": max(0.0, float(analysis_scope_start_second or source_start_second or 0.0)),
        "analysis_scope_end_second": max(0.0, float(analysis_scope_end_second or 0.0)),
        "target_team_name": match.team.name,
        "target_opponent_name": match.opponent,
        "match_candidates": [],
        "banner_text_samples": [],
        "multiple_match_candidates": False,
        "target_match_banner_seen": False,
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
    return _append_chunk(match_id=match_id, request=request, session_id=session_id, index=index, chunk=chunk, db=db)


def turbo_progress_frame(
    match_id: int,
    request: Request,
    session_id: str = Form(...),
    wall_second: float = Form(...),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    if not root.is_dir():
        raise HTTPException(status_code=404, detail="Capture session expired or not found.")
    data = frame.file.read(_MAX_PROGRESS_FRAME_BYTES + 1)
    frame.file.close()
    if len(data) > _MAX_PROGRESS_FRAME_BYTES:
        raise HTTPException(status_code=413, detail="Progress frame is too large.")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Progress frame could not be decoded.")
    wall = max(0.0, float(wall_second or 0.0))
    state = _progressive_frame_analysis(root, image, wall)
    state = _observe_match_banners(root, image, wall, match) or state
    batches = max(int(state.get("decoded_frame_batches") or 0) + 1, int(state.get("progressive_frame_batches") or 0))
    state["video_confirmed"] = True
    state["decoded_frame_batches"] = batches
    if state.get("first_decoded_wall_second") is None:
        state["first_decoded_wall_second"] = round(wall, 2)
    state["video_confirmation"] = "Vidéo réelle reçue par l’IA ✓"
    state["phase"] = "Vidéo réelle reçue par l’IA ✓ · lecture + pré-analyse IA en parallèle"
    state["analysis_percent"] = max(1.0, float(state.get("analysis_percent") or 0.0))
    _write_state(root, state)
    return JSONResponse({"ok": True, "progress": state})


def turbo_capture_status(match_id: int, request: Request, session_id: str, db: Session = Depends(get_db)):
    return _capture_status(match_id=match_id, request=request, session_id=session_id, db=db)


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
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    if not root.is_dir():
        raise HTTPException(status_code=404, detail="Capture session expired or not found.")
    state = _read_state(root)
    mode = scope_mode if scope_mode in {"auto", "single", "manual", "multiple"} else str(state.get("scope_mode") or "auto")
    chosen_start = max(0.0, float(analysis_scope_start_second or state.get("analysis_scope_start_second") or source_start_second or 0.0))
    chosen_end = max(0.0, float(analysis_scope_end_second or state.get("analysis_scope_end_second") or 0.0))
    if mode == "manual" and chosen_end > chosen_start:
        state["scope_mode"] = "manual"
        state["analysis_scope_start_second"] = chosen_start
        state["analysis_scope_end_second"] = chosen_end
        state["scope_confirmed"] = True
        _write_state(root, state)
    elif mode in {"auto", "multiple"} and bool(state.get("multiple_match_candidates")):
        candidates = list(state.get("match_candidates") or [])
        first = float(candidates[0].get("first_second") or source_start_second or 0.0) if candidates else float(source_start_second or 0.0)
        last = float(candidates[-1].get("last_second") or source_duration_seconds or 0.0) if candidates else float(source_duration_seconds or 0.0)
        return JSONResponse({
            "ok": True,
            "needs_match_selection": True,
            "message": "Plusieurs bandeaux/matchs plausibles ont été détectés. Choisis la plage avant la consolidation.",
            "match_candidates": candidates,
            "suggested_start": max(0.0, first - 30.0),
            "suggested_end": max(first + 60.0, min(float(source_duration_seconds or last + 900.0), last + 900.0)),
        })
    return _finish_capture(
        match_id=match_id,
        request=request,
        session_id=session_id,
        source_start_second=source_start_second,
        source_duration_seconds=source_duration_seconds,
        playback_rate=playback_rate,
        parallel_segments=parallel_segments,
        db=db,
    )
