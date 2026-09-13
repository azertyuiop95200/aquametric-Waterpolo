"""V7 browser-capture pipeline: no 85/88% UI freeze and adaptive quality control.

Key changes:
- final Vision/OCR consolidation runs after the HTTP finish response, so the UI
  keeps polling real progress instead of blocking on one long request;
- final rescanning is intentionally sparse because live frames/OCR already run
  during capture;
- browser playback is pre-buffered and can pause/resume together with the
  MediaRecorder when the embedded YouTube stream is buffering or persistently
  blurry, preserving source-time mapping and avoiding duplicated seconds;
- live JPEG frames are retained only during the analysis session as a fallback
  evidence source and deleted once the core report is ready.
"""
from __future__ import annotations

import io
import json
import logging
import shutil
from pathlib import Path

import cv2
import numpy as np
from fastapi import BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from analysis_product_routes import EVIDENCE_DIR, UPLOAD_DIR, _capture_session_dir, _owned_match
from capture_turbo_routes import _FAST_CAPTURE_SENTINEL, _read_state, _write_state
from capture_turbo_routes_v6 import turbo_append_chunk, turbo_create_session
from capture_turbo_routes_v6 import turbo_browser_capture_page as _v6_page
from capture_turbo_routes_v6 import turbo_capture_status as _v6_status
from capture_turbo_routes_v6 import turbo_progress_frame as _v6_frame
from db import SessionLocal, get_db
from models import Match
from services.browser_capture_media import normalize_browser_capture
from services.deep_analysis_sequences import materialize_deep_sequence_pack
from services.mosaic_match_analysis import run_mosaic_analysis
from services.rapid_match_analysis import RapidAnalysisError, run_rapid_analysis

log = logging.getLogger("aquametric.browser_capture.v7")


def _json_body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def _segments(value) -> int:
    value = int(value or 1)
    return 4 if value >= 4 else (2 if value >= 2 else 1)


def _quality_metrics(image: np.ndarray, segments: int) -> dict:
    """Conservative blur detector used only to recommend a playback pause.

    A water-polo frame can naturally contain large smooth water areas, so a low
    Laplacian score alone is not enough. The recommendation becomes true only
    after repeated low-detail frames and is ignored for an external tab that
    AquaMetric cannot pause safely.
    """
    h, w = image.shape[:2]
    panes = []
    if segments <= 1:
        panes = [image]
    elif segments == 2:
        half = w // 2
        panes = [image[:, :half], image[:, half:]]
    else:
        hw, hh = w // 2, h // 2
        panes = [image[:hh, :hw], image[:hh, hw:], image[hh:, :hw], image[hh:, hw:]]

    sharpness = []
    edges = []
    for pane in panes:
        if pane.size == 0:
            continue
        small = pane
        if pane.shape[1] > 720:
            scale = 720.0 / pane.shape[1]
            small = cv2.resize(pane, (720, max(1, int(pane.shape[0] * scale))), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        sharpness.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        edge_map = cv2.Canny(gray, 55, 150)
        edges.append(float(np.mean(edge_map > 0)))

    avg_sharp = float(np.mean(sharpness)) if sharpness else 0.0
    avg_edges = float(np.mean(edges)) if edges else 0.0
    # The score is descriptive, not a fabricated source-resolution claim.
    score = max(0.0, min(100.0, avg_sharp * 1.65 + avg_edges * 650.0))
    quality_ok = bool(avg_sharp >= 16.0 or avg_edges >= 0.020)
    return {
        "quality_score": round(score, 1),
        "quality_sharpness": round(avg_sharp, 2),
        "quality_edge_density": round(avg_edges, 4),
        "quality_ok": quality_ok,
    }


def _persist_live_frame(root: Path, data: bytes, state: dict, wall_second: float) -> None:
    last = float(state.get("last_saved_live_frame_second") or -999.0)
    count = int(state.get("saved_live_frames") or 0)
    if count >= 240 or wall_second - last < 2.5:
        return
    folder = root / "live_frames"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"frame-{count:04d}.jpg").write_bytes(data)
    state["saved_live_frames"] = count + 1
    state["last_saved_live_frame_second"] = round(float(wall_second), 2)


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

    data = frame.file.read(3 * 1024 * 1024 + 1)
    frame.file.close()
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Progress frame is too large.")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Progress frame could not be decoded.")

    # Let V6/V5 perform the real progressive Vision/OCR work, using a fresh
    # in-memory UploadFile because the original request stream was consumed here.
    replay = StarletteUploadFile(file=io.BytesIO(data), filename="progress.jpg")
    response = _v6_frame(
        match_id=match_id,
        request=request,
        session_id=session_id,
        wall_second=wall_second,
        frame=replay,
        db=db,
    )
    payload = _json_body(response)
    state = _read_state(root)
    metrics = _quality_metrics(image, _segments(state.get("parallel_segments")))
    state.update(metrics)
    bad = int(state.get("quality_bad_streak") or 0)
    good = int(state.get("quality_good_streak") or 0)
    if metrics["quality_ok"]:
        bad = 0
        good += 1
    else:
        bad += 1
        good = 0
    state["quality_bad_streak"] = bad
    state["quality_good_streak"] = good
    state["quality_pause_recommended"] = bad >= 2
    state["quality_message"] = (
        "qualité visuelle stable"
        if metrics["quality_ok"]
        else "image peu détaillée · pause tampon recommandée si le lecteur est contrôlable"
    )
    _persist_live_frame(root, data, state, max(0.0, float(wall_second or 0.0)))
    _write_state(root, state)
    payload["progress"] = state
    return JSONResponse({"ok": True, "progress": state})


def _patch_quality_and_async_ui(html: str) -> str:
    html = html.replace(
        "<div class=\"capture-warning\"><b>Rapport prioritaire :</b>",
        "<div class=\"capture-good\"><b>Qualité adaptative :</b> AquaMetric précharge le replay. Si un lecteur intégré bufferise ou si deux contrôles visuels successifs sont trop dégradés, lecture et enregistrement se mettent en pause ensemble puis reprennent, sans décaler la chronologie.</div><div class=\"capture-warning\"><b>Rapport prioritaire :</b>",
        1,
    )
    html = html.replace(
        "let stream=null,recorder=null,sessionId='',startedAt=0,tick=null,statusTick=null,frameTick=null,playerTick=null,chunkIndex=0,uploadedBytes=0,uploadError=null,uploadChain=Promise.resolve(),frameBusy=false,stopping=false,analysisPercent=0,externalFallback=false;",
        "let stream=null,recorder=null,sessionId='',startedAt=0,tick=null,statusTick=null,frameTick=null,playerTick=null,chunkIndex=0,uploadedBytes=0,uploadError=null,uploadChain=Promise.resolve(),frameBusy=false,stopping=false,analysisPercent=0,externalFallback=false;let qualityPaused=false,qualityPauseStarted=0,qualityPausedMs=0,qualityRetryTimer=null,lastQualityPauseAt=0;",
        1,
    )

    quality_js = r'''
  function activeWallSeconds(){
    if(!startedAt)return 0;const now=Date.now();const openPause=qualityPaused&&qualityPauseStarted?now-qualityPauseStarted:0;
    return Math.max(0,(now-startedAt-qualityPausedMs-openPause)/1000);
  }
  function resumePlayers(){
    for(let i=0;i<parallelSegments;i++){try{if(!ytReady[i]||!ytPlayers[i])continue;const end=Number(segmentEnds[i]||0),now=Number(ytPlayers[i].getCurrentTime?ytPlayers[i].getCurrentTime():currentTimes[i])||currentTimes[i];if(end>segmentStarts[i]&&now>=end-0.08)continue;ytPlayers[i].mute();ytPlayers[i].setPlaybackRate(playbackRate);ytPlayers[i].playVideo()}catch(_){}}
  }
  function embeddedQualityPoor(){
    if(externalFallback)return false;let checked=0;
    for(let i=0;i<parallelSegments;i++){try{if(!ytReady[i]||!ytPlayers[i])continue;const end=Number(segmentEnds[i]||0),now=Number(ytPlayers[i].getCurrentTime?ytPlayers[i].getCurrentTime():currentTimes[i])||0;if(end>segmentStarts[i]&&now>=end-0.08)continue;checked++;const state=Number(ytPlayers[i].getPlayerState?ytPlayers[i].getPlayerState():-1),q=String(ytPlayers[i].getPlaybackQuality?ytPlayers[i].getPlaybackQuality():'');if(state===3||q==='small')return true}catch(_){}}
    return false;
  }
  function resumeAfterQualityPause(){
    if(!qualityPaused||stopping)return;qualityPausedMs+=Math.max(0,Date.now()-qualityPauseStarted);qualityPauseStarted=0;qualityPaused=false;
    try{if(recorder&&recorder.state==='paused')recorder.resume()}catch(_){}
    resumePlayers();setStatus('Qualité/tampon rétabli · reprise de la lecture et de la capture.');
  }
  function enterQualityPause(reason){
    if(externalFallback||qualityPaused||stopping||!recorder||Date.now()-lastQualityPauseAt<1600)return;lastQualityPauseAt=Date.now();qualityPaused=true;qualityPauseStarted=Date.now();pausePlayers();
    try{if(recorder.state==='recording')recorder.pause()}catch(_){}
    setStatus(`Pause qualité automatique · ${reason}. La chronologie est gelée avec l’enregistrement.`);
    clearTimeout(qualityRetryTimer);qualityRetryTimer=setTimeout(()=>resumeAfterQualityPause(),2200);
  }
  function adaptiveQualityGuard(){if(!externalFallback&&!qualityPaused&&!stopping&&embeddedQualityPoor())enterQualityPause('buffering ou définition YouTube trop basse')}
  async function waitForFinalReport(payload){
    analysisPercent=Math.max(90,analysisPercent);setBars(100,analysisPercent,'Lecture terminée','Consolidation rapide en arrière-plan · le navigateur reste réactif…');
    const url=payload.status_url||`/matches/{{match.id}}/analysis/browser-capture/status?session_id=${encodeURIComponent(sessionId)}`;
    for(let i=0;i<180;i++){
      const out=await jsonFetch(url);const p=out.progress||{};if(out.ok)applyServerProgress(p);
      const state=String(p.status||'');if(state==='complete'||state==='partial')return {redirect:p.redirect||payload.redirect||'/matches/{{match.id}}/analysis/result',warning:p.warning||''};
      if(state==='failed')throw new Error(p.error||'Échec de la consolidation finale.');
      await new Promise(r=>setTimeout(r,700));
    }
    throw new Error('La consolidation dépasse 2 minutes. La capture est conservée pour reprise, sans recommencer la lecture.');
  }
'''
    html = html.replace("  function localReadPercent(){", quality_js + "\n  function localReadPercent(){", 1)

    html = html.replace(
        "f.append('wall_second',String(Math.max(0,(Date.now()-startedAt)/1000)));",
        "f.append('wall_second',String(activeWallSeconds()));",
        1,
    )
    html = html.replace(
        "function applyServerProgress(p){",
        "function applyServerProgress(p){if(p.quality_pause_recommended&&!externalFallback&&!qualityPaused&&!stopping)enterQualityPause('deux contrôles visuels successifs trop flous');",
        1,
    )
    html = html.replace(
        "function tickUi(){pollPlayers();const r=localReadPercent();",
        "function tickUi(){pollPlayers();adaptiveQualityGuard();const r=localReadPercent();",
        1,
    )
    # Pre-buffer the embedded YouTube players before MediaRecorder starts. This
    # improves initial quality without recording duplicate/still frames.
    html = html.replace(
        "preview.srcObject=stream;await preview.play().catch(()=>{});await createSession();",
        "preview.srcObject=stream;await preview.play().catch(()=>{});await createSession();if(!externalFallback){setStatus('Préchargement vidéo · AquaMetric attend le tampon avant d’enregistrer…');playPlayers();await new Promise(r=>setTimeout(r,1800));pausePlayers();}",
        1,
    )
    html = html.replace("recorder.start(5000)", "recorder.start(3000)", 1)
    html = html.replace(
        "function requestStop(){if(stopping)return;stopping=true;pausePlayers();if(recorder&&recorder.state==='recording'){stopBtn.disabled=true;stopLiveBtn.disabled=true;setStatus('Lecture terminée. Finalisation de l’analyse…');recorder.stop()}}",
        "function requestStop(){if(stopping)return;stopping=true;clearTimeout(qualityRetryTimer);if(qualityPaused&&qualityPauseStarted){qualityPausedMs+=Math.max(0,Date.now()-qualityPauseStarted);qualityPauseStarted=0;qualityPaused=false;}pausePlayers();if(recorder&&(recorder.state==='recording'||recorder.state==='paused')){stopBtn.disabled=true;stopLiveBtn.disabled=true;analysisPercent=Math.max(87,analysisPercent);setBars(100,analysisPercent,'Lecture terminée','Envoi du dernier fragment · finalisation immédiate ensuite…');setStatus('Lecture terminée. Envoi du dernier fragment puis consolidation rapide…');try{if(recorder.state==='paused')recorder.resume()}catch(_){}setTimeout(()=>{try{if(recorder&&recorder.state!=='inactive')recorder.stop()}catch(_){}},60)}}",
        1,
    )
    html = html.replace(
        "async function finishAnalysis(){await uploadChain;for(let i=0;i<150&&frameBusy;i++)await new Promise(r=>setTimeout(r,100));if(uploadError)throw uploadError;analysisPercent=Math.max(analysisPercent,88);",
        "async function finishAnalysis(){await uploadChain;for(let i=0;i<20&&frameBusy;i++)await new Promise(r=>setTimeout(r,100));if(uploadError)throw uploadError;analysisPercent=Math.max(analysisPercent,89);",
        1,
    )
    html = html.replace(
        "setBars(100,analysisPercent,'Lecture terminée','Finalisation serveur en cours · progression 88–99 % suivie en direct…');",
        "setBars(100,analysisPercent,'Lecture terminée','Consolidation rapide lancée · progression suivie en direct…');",
        1,
    )
    html = html.replace(
        "const payload=await finishAnalysis();clearInterval(statusTick);statusTick=null;if(payload.needs_match_selection){",
        "const payload=await finishAnalysis();if(payload.accepted){const done=await waitForFinalReport(payload);clearInterval(statusTick);statusTick=null;analysisPercent=100;setBars(100,100,'Lecture complète',done.warning?'Rapport Vision prêt · enrichissement partiel':'Rapport prêt');setStatus(done.warning?`Rapport produit. ${done.warning} Redirection…`:'Analyse terminée. Redirection vers le rapport…');setTimeout(()=>location.href=done.redirect||'/matches/{{match.id}}/analysis/result',350);return;}clearInterval(statusTick);statusTick=null;if(payload.needs_match_selection){",
        1,
    )
    html = html.replace(
        "recorder.onstop=async()=>{clearInterval(tick);clearInterval(frameTick);clearInterval(playerTick);",
        "recorder.onstop=async()=>{clearTimeout(qualityRetryTimer);clearInterval(tick);clearInterval(frameTick);clearInterval(playerTick);",
        1,
    )
    return html


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    response = _v6_page(match_id=match_id, request=request, db=db)
    html = bytes(response.body).decode("utf-8")
    return HTMLResponse(_patch_quality_and_async_ui(html))


def turbo_capture_status(match_id: int, request: Request, session_id: str, db: Session = Depends(get_db)):
    response = _v6_status(match_id=match_id, request=request, session_id=session_id, db=db)
    payload = _json_body(response)
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else None
    if progress and progress.get("status") in {"complete", "partial"}:
        progress.setdefault("redirect", f"/matches/{match_id}/analysis/result")
    return JSONResponse({"ok": bool(payload.get("ok")), "progress": progress or payload.get("progress", {}), **({"status": payload.get("status")} if payload.get("status") else {})})


def _cleanup_pixels_keep_state(root: Path) -> None:
    (root / "capture.webm").unlink(missing_ok=True)
    shutil.rmtree(root / "derived", ignore_errors=True)
    shutil.rmtree(root / "live_frames", ignore_errors=True)
    (root / "next_index.txt").unlink(missing_ok=True)


def _finalize_capture_job(match_id: int, root_value: str, start: float, total_duration: float, rate: float, segments: int) -> None:
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
        state.update({"status": "finalizing", "analysis_percent": 90.0, "phase": "normalisation rapide de la capture"})
        _write_state(root, state)

        analysis_source, media_info = normalize_browser_capture(source_path, derived_dir, fast_analysis=True)
        state = _read_state(root)
        state.update({
            "analysis_percent": 92.0,
            "phase": "Vision/OCR final ciblé · réutilisation de la pré-analyse live",
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
                visual_samples=176,
                ocr_samples=40,
            )
        else:
            encoded_offset = (_FAST_CAPTURE_SENTINEL + start) if rate >= 1.75 else start
            result = run_rapid_analysis(
                db,
                match,
                analysis_source,
                derived_dir,
                include_audio=False,
                visual_samples=176,
                ocr_samples=40,
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

        # Core report is already available at 100%. This enrichment is deliberately
        # non-blocking from the user's point of view.
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
        log.exception("async browser capture finalization failed match=%s", match_id)
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
    source_path = root / "capture.webm"
    if not root.is_dir() or not source_path.exists():
        raise HTTPException(status_code=404, detail="Capture session expired or not found.")
    if source_path.stat().st_size < 64 * 1024:
        raise HTTPException(status_code=422, detail="Capture too short: no usable video frames were received.")

    state = _read_state(root)
    if state.get("status") in {"queued_finalization", "finalizing"}:
        return JSONResponse({
            "ok": True,
            "accepted": True,
            "status_url": f"/matches/{match_id}/analysis/browser-capture/status?session_id={session_id}",
            "redirect": f"/matches/{match_id}/analysis/result",
        }, status_code=202)

    mode = scope_mode if scope_mode in {"auto", "single", "manual", "multiple"} else str(state.get("scope_mode") or "auto")
    chosen_start = max(0.0, float(analysis_scope_start_second or state.get("analysis_scope_start_second") or source_start_second or 0.0))
    chosen_end = max(0.0, float(analysis_scope_end_second or state.get("analysis_scope_end_second") or 0.0))
    if mode == "manual" and chosen_end > chosen_start:
        # Manual mode is expected to arrive through a recaptured selected range.
        state.update({"scope_mode": "manual", "analysis_scope_start_second": chosen_start, "analysis_scope_end_second": chosen_end, "scope_confirmed": True})
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

    start = max(0.0, float(state.get("source_start_second") or source_start_second or 0.0))
    total_duration = max(0.0, float(state.get("source_duration_seconds") or source_duration_seconds or 0.0))
    rate = max(1.0, min(4.0, float(state.get("playback_rate") or playback_rate or 1.0)))
    segments = _segments(state.get("parallel_segments") or parallel_segments)
    state.update({
        "status": "queued_finalization",
        "phase": "dernier fragment reçu · consolidation rapide mise en file",
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
    }, status_code=202)
