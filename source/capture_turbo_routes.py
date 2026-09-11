"""Priority browser-capture routes with live progress and concurrent pre-analysis."""
from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path

import cv2
import numpy as np
from fastapi import BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from db import get_db
from analysis_product_routes import (
    EVIDENCE_DIR,
    UPLOAD_DIR,
    TEMPLATES,
    _capture_session_dir,
    _owned_match,
    _source_start_second,
    _write_capture_chunk,
)
from services.deep_analysis_sequences import materialize_deep_sequence_pack
from services.mosaic_match_analysis import run_mosaic_analysis
from services.rapid_match_analysis import RapidAnalysisError, run_rapid_analysis
from services.reference_match_rosters import roster_payload
from services.scoreboard_ocr import ocr_image, parse_scoreboard_text, tesseract_available
from services.vision_baseline import _pool_ratio


_FAST_CAPTURE_SENTINEL = 1_000_000.0
_MAX_PROGRESS_FRAME_BYTES = 3 * 1024 * 1024


def _state_path(root: Path) -> Path:
    return root / "progress.json"


def _read_state(root: Path) -> dict:
    path = _state_path(root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(root: Path, state: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = _state_path(root)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _expected_capture_seconds(state: dict) -> float:
    total = max(0.0, float(state.get("source_duration_seconds") or 0.0) - float(state.get("source_start_second") or 0.0))
    rate = max(1.0, float(state.get("playback_rate") or 1.0))
    segments = max(1, int(state.get("parallel_segments") or 1))
    return total / (rate * segments) if total > 0 else 0.0


def _pane(frame: np.ndarray, index: int, segments: int) -> np.ndarray:
    if segments <= 1:
        return frame
    h, w = frame.shape[:2]
    if segments == 2:
        half = w // 2
        return frame[:, :half] if index == 0 else frame[:, half:]
    half_w, half_h = w // 2, h // 2
    boxes = (
        (0, 0, half_w, half_h),
        (half_w, 0, w, half_h),
        (0, half_h, half_w, h),
        (half_w, half_h, w, h),
    )
    x1, y1, x2, y2 = boxes[index]
    return frame[y1:y2, x1:x2]


def _progressive_frame_analysis(root: Path, frame: np.ndarray, wall_second: float) -> dict:
    state = _read_state(root)
    if not state:
        return {}
    segments = 4 if int(state.get("parallel_segments") or 1) >= 4 else (2 if int(state.get("parallel_segments") or 1) >= 2 else 1)
    rate = max(1.0, float(state.get("playback_rate") or 1.0))
    source_total = max(0.0, float(state.get("source_duration_seconds") or 0.0) - float(state.get("source_start_second") or 0.0))
    panes = [_pane(frame, idx, segments) for idx in range(segments)]
    pool_values = []
    for pane in panes:
        if pane.size:
            small = pane
            if pane.shape[1] > 640:
                scale = 640.0 / pane.shape[1]
                small = cv2.resize(pane, (640, max(1, int(pane.shape[0] * scale))), interpolation=cv2.INTER_AREA)
            pool_values.append(_pool_ratio(small))

    state["progressive_samples"] = int(state.get("progressive_samples") or 0) + len(pool_values)
    if pool_values:
        previous = float(state.get("avg_live_pool_ratio") or 0.0)
        n = max(1, int(state.get("progressive_frame_batches") or 0))
        state["avg_live_pool_ratio"] = round((previous * n + float(np.mean(pool_values))) / (n + 1), 4)
        state["progressive_frame_batches"] = n + 1

    # OCR is intentionally throttled: one real scoreboard pre-pass about every 12 s.
    last_ocr_wall = float(state.get("last_live_ocr_wall_second") or -999.0)
    if tesseract_available() and wall_second - last_ocr_wall >= 12.0:
        hits = 0
        texts = []
        for pane in panes:
            h = pane.shape[0]
            candidate_bands = (pane[: max(1, int(h * 0.24)), :], pane[max(0, int(h * 0.76)) :, :])
            best = None
            for band in candidate_bands:
                text, confidence = ocr_image(band)
                parsed = parse_scoreboard_text(text)
                useful = parsed["clock_seconds"] is not None or parsed["period"] is not None or parsed["home_score"] is not None
                if useful and (best is None or confidence > best[0]):
                    best = (confidence, parsed["normalized_text"])
            if best:
                hits += 1
                texts.append(best[1][:160])
        state["progressive_ocr_hits"] = int(state.get("progressive_ocr_hits") or 0) + hits
        state["last_live_ocr_wall_second"] = round(float(wall_second), 2)
        if texts:
            state["latest_live_ocr"] = texts[:4]

    covered = max(0.0, float(wall_second)) * rate * segments
    read_percent = min(99.0, (covered / source_total * 100.0) if source_total > 0 else 0.0)
    state["read_percent"] = max(float(state.get("read_percent") or 0.0), round(read_percent, 1))
    # This percentage is backed by actual processed live frames, not upload bytes.
    state["analysis_percent"] = max(float(state.get("analysis_percent") or 0.0), round(min(86.0, read_percent * 0.86), 1))
    state["phase"] = "lecture + pré-analyse IA en parallèle"
    state["wall_seconds"] = round(float(wall_second), 2)
    _write_state(root, state)
    return state


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    if not match.video_url:
        raise HTTPException(status_code=400, detail="This capture mode requires a video URL.")
    return TEMPLATES.TemplateResponse(
        request,
        "browser_capture.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "match": match,
            "source_start_second": _source_start_second(match.video_url),
            "roster": roster_payload(match.video_url),
        },
    )


def turbo_create_session(
    match_id: int,
    request: Request,
    source_start_second: float = Form(0.0),
    source_duration_seconds: float = Form(0.0),
    playback_rate: float = Form(2.0),
    parallel_segments: int = Form(1),
    db: Session = Depends(get_db),
):
    user, match = _owned_match(match_id, request, db)
    if not match.video_url:
        raise HTTPException(status_code=400, detail="This capture mode requires a video URL.")
    session_id = secrets.token_hex(16)
    root = _capture_session_dir(user, match, session_id)
    root.mkdir(parents=True, exist_ok=False)
    (root / "next_index.txt").write_text("0", encoding="utf-8")
    state = {
        "status": "running",
        "phase": "autorisation obtenue · démarrage du flux",
        "source_start_second": max(0.0, float(source_start_second or 0.0)),
        "source_duration_seconds": max(0.0, float(source_duration_seconds or 0.0)),
        "playback_rate": max(1.0, min(4.0, float(playback_rate or 1.0))),
        "parallel_segments": 4 if int(parallel_segments or 1) >= 4 else (2 if int(parallel_segments or 1) >= 2 else 1),
        "read_percent": 0.0,
        "analysis_percent": 0.0,
        "progressive_samples": 0,
        "progressive_ocr_hits": 0,
        "bytes": 0,
        "chunks": 0,
    }
    state["expected_capture_seconds"] = round(_expected_capture_seconds(state), 2)
    _write_state(root, state)
    match.status = "browser_capture_running"
    db.commit()
    return JSONResponse({"ok": True, "session_id": session_id, **state})


def turbo_append_chunk(
    match_id: int,
    request: Request,
    session_id: str = Form(...),
    index: int = Form(...),
    chunk: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    from services.capture_chunks import append_capture_chunk
    result = append_capture_chunk(root, int(index), chunk, _write_capture_chunk)
    state = _read_state(root)
    state["bytes"] = result["bytes"]
    state["chunks"] = result["next_index"]
    state["phase"] = state.get("phase") or "lecture + pré-analyse IA en parallèle"
    _write_state(root, state)
    return JSONResponse({**result, "progress": state})


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
    state = _progressive_frame_analysis(root, image, max(0.0, float(wall_second or 0.0)))
    return JSONResponse({"ok": True, "progress": state})


def turbo_capture_status(match_id: int, request: Request, session_id: str, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    if not root.is_dir():
        return JSONResponse({"ok": False, "status": "finished_or_expired"})
    return JSONResponse({"ok": True, "progress": _read_state(root)})


def turbo_finish_capture(
    match_id: int,
    request: Request,
    session_id: str = Form(...),
    source_start_second: float = Form(0.0),
    source_duration_seconds: float = Form(0.0),
    playback_rate: float = Form(1.0),
    parallel_segments: int = Form(1),
    db: Session = Depends(get_db),
):
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    source_path = root / "capture.webm"
    if not root.is_dir() or not source_path.exists():
        raise HTTPException(status_code=404, detail="Capture session expired or not found.")
    if source_path.stat().st_size < 64 * 1024:
        shutil.rmtree(root, ignore_errors=True)
        match.status = "browser_capture_failed"
        db.commit()
        raise HTTPException(status_code=422, detail="Capture too short: no usable video frames were received.")

    state = _read_state(root)
    start = max(0.0, float(state.get("source_start_second") or source_start_second or 0.0))
    total_duration = max(0.0, float(state.get("source_duration_seconds") or source_duration_seconds or 0.0))
    rate = max(1.0, min(4.0, float(state.get("playback_rate") or playback_rate or 1.0)))
    segments = int(state.get("parallel_segments") or parallel_segments or 1)
    segments = 4 if segments >= 4 else (2 if segments >= 2 else 1)
    state.update({"phase": "consolidation finale du rapport", "analysis_percent": 88.0, "read_percent": 100.0, "status": "finalizing"})
    _write_state(root, state)

    derived_dir = root / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    try:
        if segments >= 4 and total_duration > start + 30.0:
            result = run_mosaic_analysis(
                db,
                match,
                source_path,
                source_start_second=start,
                source_duration_seconds=total_duration,
                playback_rate=rate,
                parallel_segments=segments,
                visual_samples=360,
                ocr_samples=112,
            )
        else:
            encoded_offset = (_FAST_CAPTURE_SENTINEL + start) if rate >= 1.75 else start
            result = run_rapid_analysis(
                db,
                match,
                source_path,
                derived_dir,
                include_audio=False,
                visual_samples=320,
                ocr_samples=96,
                source_kind="browser_capture",
                persist_visual_artifacts=False,
                time_offset_seconds=encoded_offset,
            )
        state = _read_state(root)
        state.update({"phase": "séquences et synthèse tactique", "analysis_percent": 96.0})
        _write_state(root, state)
        materialize_deep_sequence_pack(
            db,
            match,
            UPLOAD_DIR,
            EVIDENCE_DIR,
            max_targets=72,
            max_clips=0,
            max_image_targets=0,
        )
        match.status = "browser_capture_analyzed"
        db.commit()
        summary = result.get("summary", {}) or {}
        state = _read_state(root)
        state.update({"phase": "rapport prêt", "analysis_percent": 100.0, "read_percent": 100.0, "status": "complete"})
        _write_state(root, state)
        return JSONResponse({
            "ok": True,
            "visual_samples": int(summary.get("visual_samples") or 0),
            "scoreboard_observations": int(summary.get("scoreboard_observations") or 0),
            "candidates": len(result.get("candidates", []) or []),
            "parallel_segments": int(summary.get("parallel_segments") or segments),
            "capture_duration_minutes": float(summary.get("capture_duration_minutes") or 0.0),
            "source_time_offset_seconds": float(summary.get("source_time_offset_seconds") or start),
            "redirect": f"/matches/{match.id}/analysis/result",
        })
    except RapidAnalysisError as exc:
        match.status = "browser_capture_failed"
        db.commit()
        state = _read_state(root)
        state.update({"phase": "échec de l’analyse", "status": "failed", "error": str(exc)})
        _write_state(root, state)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        # Keep the transient pixels only until the synchronous final response is ready.
        shutil.rmtree(root, ignore_errors=True)
