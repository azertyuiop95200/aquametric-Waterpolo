"""Resilient browser-capture surface for real URL video analysis.

V4 deliberately does not preload a user-supplied player roster. Cap numbers and
player identity remain unknown until the video pipeline has visual evidence.
It also preserves a core Vision report when optional deep-sequence generation
fails after the main analysis has already completed.
"""
from __future__ import annotations

import shutil

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from db import get_db
from analysis_product_routes import (
    EVIDENCE_DIR,
    UPLOAD_DIR,
    TEMPLATES,
    _capture_session_dir,
    _owned_match,
    _source_start_second,
)
from capture_turbo_routes import (
    _FAST_CAPTURE_SENTINEL,
    _read_state,
    _write_state,
    turbo_append_chunk,
    turbo_capture_status,
    turbo_create_session,
    turbo_progress_frame,
)
from services.deep_analysis_sequences import materialize_deep_sequence_pack
from services.mosaic_match_analysis import run_mosaic_analysis
from services.rapid_match_analysis import RapidAnalysisError, run_rapid_analysis


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    if not match.video_url:
        raise HTTPException(status_code=400, detail="This capture mode requires a video URL.")
    return TEMPLATES.TemplateResponse(
        request,
        "browser_capture_v4.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "match": match,
            "source_start_second": _source_start_second(match.video_url),
        },
    )


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
    state.update({
        "phase": "consolidation finale du rapport",
        "analysis_percent": 88.0,
        "read_percent": 100.0,
        "status": "finalizing",
    })
    _write_state(root, state)

    derived_dir = root / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    core_complete = False
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
            # A fast single-pane capture has no reliable source clock in the
            # encoded file, so keep the established sentinel-based remapping.
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

        # Commit the core report BEFORE optional enrichment. A later failure in
        # sequence materialisation must never erase a successful Vision analysis.
        core_complete = True
        match.status = "browser_capture_analyzed"
        db.commit()

        state = _read_state(root)
        state.update({"phase": "séquences et synthèse tactique", "analysis_percent": 96.0})
        _write_state(root, state)

        enrichment_warning = ""
        try:
            materialize_deep_sequence_pack(
                db,
                match,
                UPLOAD_DIR,
                EVIDENCE_DIR,
                max_targets=72,
                max_clips=0,
                max_image_targets=0,
            )
        except Exception as exc:  # optional enrichment: keep the core report usable
            enrichment_warning = f"Séquences avancées non finalisées: {exc}"
            match.status = "browser_capture_analyzed_partial"
            db.commit()

        summary = result.get("summary", {}) or {}
        state = _read_state(root)
        state.update({
            "phase": "rapport prêt" if not enrichment_warning else "rapport Vision prêt · enrichissement partiel",
            "analysis_percent": 100.0,
            "read_percent": 100.0,
            "status": "complete" if not enrichment_warning else "partial",
        })
        if enrichment_warning:
            state["warning"] = enrichment_warning
        _write_state(root, state)
        return JSONResponse({
            "ok": True,
            "partial": bool(enrichment_warning),
            "warning": enrichment_warning,
            "visual_samples": int(summary.get("visual_samples") or 0),
            "scoreboard_observations": int(summary.get("scoreboard_observations") or 0),
            "candidates": len(result.get("candidates", []) or []),
            "parallel_segments": int(summary.get("parallel_segments") or segments),
            "playback_rate": float(summary.get("playback_rate") or rate),
            "capture_duration_minutes": float(summary.get("capture_duration_minutes") or 0.0),
            "source_time_offset_seconds": float(summary.get("source_time_offset_seconds") or start),
            "redirect": f"/matches/{match.id}/analysis/result",
        })
    except RapidAnalysisError as exc:
        match.status = "browser_capture_failed"
        db.commit()
        state = _read_state(root)
        state.update({"phase": "échec de l’analyse Vision", "status": "failed", "error": str(exc)})
        _write_state(root, state)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # If the core analysis already committed, return the report rather than
        # converting an enrichment/UI problem into a total analysis failure.
        if core_complete:
            match.status = "browser_capture_analyzed_partial"
            db.commit()
            return JSONResponse({
                "ok": True,
                "partial": True,
                "warning": f"Rapport Vision conservé malgré une erreur secondaire: {exc}",
                "redirect": f"/matches/{match.id}/analysis/result",
            })
        match.status = "browser_capture_failed"
        db.commit()
        state = _read_state(root)
        state.update({"phase": "échec de l’analyse Vision", "status": "failed", "error": str(exc)})
        _write_state(root, state)
        raise HTTPException(status_code=422, detail=f"Core video analysis failed: {exc}") from exc
    finally:
        shutil.rmtree(root, ignore_errors=True)
