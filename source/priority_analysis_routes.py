"""Install result-first analysis routes directly on the FastAPI application."""
from __future__ import annotations

import logging
import os
from threading import Lock

from fastapi import BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from analysis_library_product_routes import published_ultimate_detail, ultimate_analysis_library
from analysis_input_routes_v2 import create_flexible_uploaded_match
from analysis_input_routes_v3 import create_flexible_url_analysis
from analysis_product_routes import (
    _owned_match,
    export_complete_analysis,
    regenerate_exact_evidence,
    start_real_analysis,
    start_real_url_analysis,
)
from analysis_result_clean_v2 import clean_analysis_result as _clean_analysis_result_v2, download_analysis_report
from db import get_db

# Patch the shared capture-state writer before importing V16 and its compatibility
# chain. Every capture route then receives the same collision-safe atomic writer.
import capture_turbo_routes as _capture_base
from services.capture_state_io import write_state_atomic
from services.scoreboard_ocr import tesseract_available
from services.capture_report_progress import latest_capture_root, report_progress

_capture_base._write_state = write_state_atomic

import capture_turbo_routes_v16 as _capture_v16
from capture_turbo_routes_v16 import (
    turbo_append_chunk,
    turbo_browser_capture_page as _turbo_browser_capture_page_v16,
    turbo_capture_status,
    turbo_create_session,
    turbo_finish_capture,
    turbo_progress_frame as _turbo_progress_frame_v16,
)
import capture_turbo_routes_v5 as _capture_v5


# V13's proven report finalizer used 10 targeted OCR checks. V16 accidentally
# requested 240, which can hold the only small Render instance in OCR for minutes
# before any visual candidates or action-engine work become visible. Keep V16's
# report-first behavior, but bound only its post-publication OCR pass back to the
# known-fast target count. The original function still owns all evidence rules.
if not getattr(_capture_v16.run_live_frame_analysis, "_aquametric_v16_bounded_ocr", False):
    _V16_ORIGINAL_RUN_LIVE_FRAME_ANALYSIS = _capture_v16.run_live_frame_analysis

    def _v16_bounded_live_frame_analysis(*args, **kwargs):
        try:
            requested = int(kwargs.get("ocr_samples", 10) or 10)
        except (TypeError, ValueError):
            requested = 10
        kwargs["ocr_samples"] = max(4, min(10, requested))
        return _V16_ORIGINAL_RUN_LIVE_FRAME_ANALYSIS(*args, **kwargs)

    _v16_bounded_live_frame_analysis._aquametric_v16_bounded_ocr = True
    _capture_v16.run_live_frame_analysis = _v16_bounded_live_frame_analysis


# V16 intentionally publishes before OCR/provider enrichment. The fallback report
# used to contain only a sample count, so the user could reach a technically valid
# but visually empty report for several minutes. Add one small provider-free pass
# before returning /finish: it publishes generic visual review timestamps from the
# JPEGs already received. It never invents a sporting action and is superseded by
# the newer full Vision/Autonomy rows when enrichment finishes.
if not getattr(_capture_v16._publish_report_first, "_aquametric_visual_prepublication", False):
    _V16_ORIGINAL_PUBLISH_REPORT_FIRST = _capture_v16._publish_report_first

    def _v16_publish_report_with_visual_review(match_id, root):
        state = _V16_ORIGINAL_PUBLISH_REPORT_FIRST(match_id, root)
        if not state:
            return state
        try:
            from services.report_first_visual import publish_report_first_visual
            quick = publish_report_first_visual(match_id, root, state)
            logging.getLogger("aquametric.report_first_visual").warning(
                "report_first_visual match=%s published=%s samples=%s candidates=%s reason=%s",
                match_id,
                bool(quick.get("published")),
                int(quick.get("visual_samples") or 0),
                int(quick.get("candidates") or 0),
                str(quick.get("reason") or "ok"),
            )
        except Exception:
            # The immediate report must remain available even if this optional
            # local pre-publication fails; OCR/provider enrichment still follows.
            logging.getLogger("aquametric.report_first_visual").exception(
                "report_first_visual prepublication failed match=%s", match_id
            )
        return state

    _v16_publish_report_with_visual_review._aquametric_visual_prepublication = True
    _capture_v16._publish_report_first = _v16_publish_report_with_visual_review


# V16's immediate response remains API-compatible with earlier capture versions.
# Report-first made some evidence fields implicit in progress.json, which caused
# the production E2E (and any client using those fields) to treat a successful
# finish as incomplete. Re-expose only already-persisted metadata; no extra work
# is performed here, so the fast redirect remains non-blocking.
if not getattr(_capture_v16._finish_payload, "_aquametric_evidence_metadata", False):
    _V16_ORIGINAL_FINISH_PAYLOAD = _capture_v16._finish_payload

    def _v16_finish_payload_with_evidence(match_id, session_id, progress):
        payload = _V16_ORIGINAL_FINISH_PAYLOAD(match_id, session_id, progress)
        payload.update({
            "retained_live_frames": int(progress.get("retained_live_frames") or progress.get("saved_live_frames") or 0),
            "visual_samples": int(progress.get("visual_samples") or progress.get("progressive_samples") or 0),
            "scoreboard_observations": int(progress.get("scoreboard_observations") or progress.get("progressive_ocr_hits") or 0),
            "finalization_elapsed_seconds": float(progress.get("finalization_elapsed_seconds") or 0.0),
        })
        return payload

    _v16_finish_payload_with_evidence._aquametric_evidence_metadata = True
    _capture_v16._finish_payload = _v16_finish_payload_with_evidence


# Log only boolean/configuration metadata. Never emit credentials.
try:
    from services.video_action_provider import provider_configuration as _video_action_configuration
    _video_action_config = _video_action_configuration()
    logging.getLogger("aquametric.video_actions").warning(
        "video_action_readiness enabled=%s configured=%s code=%s model=%s",
        bool(_video_action_config.get("enabled")),
        bool(_video_action_config.get("configured")),
        str(_video_action_config.get("availability_code") or "unknown"),
        str(_video_action_config.get("model") or ""),
    )
except Exception:
    logging.getLogger("aquametric.video_actions").exception("video_action_readiness diagnostic failed")


# Native RapidOCR/ONNX remains available to the report-first final/enrichment pass,
# but it must not run inside the live /frame request. On the small Render runtime a
# native inference failure can terminate the Uvicorn process without a Python
# traceback, deleting the ephemeral capture session before /finish is reached.
# The live loop therefore uses only system Tesseract when it is available; pixel
# coverage and retained JPEG evidence continue regardless of OCR availability.
_LIVE_FRAME_OCR_LOCK = Lock()


def turbo_progress_frame(
    match_id: int,
    request: Request,
    session_id: str = Form(...),
    wall_second: float = Form(...),
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    with _LIVE_FRAME_OCR_LOCK:
        base_gate = _capture_base.ocr_available
        banner_gate = _capture_v5.ocr_available
        live_ocr = (lambda: False) if os.getenv("CAPTURE_LIVE_OCR", "1") == "0" else tesseract_available
        _capture_base.ocr_available = live_ocr
        _capture_v5.ocr_available = live_ocr
        try:
            return _turbo_progress_frame_v16(
                match_id=match_id,
                request=request,
                session_id=session_id,
                wall_second=wall_second,
                frame=frame,
                db=db,
            )
        finally:
            _capture_base.ocr_available = base_gate
            _capture_v5.ocr_available = banner_gate


def _patch_capture_failure_redirect(html: str, match_id: int) -> str:
    """Never leave the capture Studio stranded after a lost/restarted session."""
    old = "catch(err){leaveStudio();setStatus(`Échec de l’analyse Vision : ${err.message||err}`)}"
    if old not in html:
        return html
    new = (
        "catch(err){leaveStudio();setStatus(`Échec de l’analyse Vision : ${err.message||err}. "
        "Ouverture du rapport de diagnostic…`);"
        f"setTimeout(()=>location.href='/matches/{int(match_id)}/analysis/result?capture_interrupted=1',600)"
        "}"
    )
    return html.replace(old, new, 1)


def turbo_browser_capture_page(
    match_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        response = _turbo_browser_capture_page_v16(match_id=match_id, request=request, db=db)
    except HTTPException as exc:
        return _unavailable_match_page(request, exc)
    html = bytes(response.body).decode("utf-8")
    return HTMLResponse(
        _patch_capture_failure_redirect(html, match_id),
        status_code=response.status_code,
    )


def clean_analysis_result(
    match_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    # If the browser explicitly reports that its capture session disappeared,
    # clear the persisted running/finalizing flag before rendering. Otherwise the
    # report template would auto-refresh forever after an instance restart.
    try:
        if request.query_params.get("capture_interrupted") == "1":
            _, match = _owned_match(match_id, request, db)
            if match.status in {"browser_capture_running", "browser_capture_finalizing"}:
                match.status = "browser_capture_failed"
                db.commit()
        return _clean_analysis_result_v2(match_id=match_id, request=request, db=db)
    except HTTPException as exc:
        return _unavailable_match_page(request, exc)


def _unavailable_match_page(request: Request, exc: HTTPException):
    if exc.status_code not in {401, 404}:
        raise exc
    from analysis_product_routes import TEMPLATES
    return TEMPLATES.TemplateResponse(request, "analysis_match_unavailable.html",
        {"request": request, "user": None, "app_name": "AquaMetric"},
        status_code=exc.status_code, headers={"Cache-Control": "private, no-store"})


def saved_report_progress(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    return JSONResponse(report_progress(match, db=db), headers={"Cache-Control": "private, no-store"})


def video_action_readiness():
    """Public, secret-free provider readiness for deployment diagnostics."""
    from services.video_action_provider import provider_configuration
    config = provider_configuration()
    return JSONResponse({
        "ok": True,
        "enabled": bool(config.get("enabled")),
        "configured": bool(config.get("configured")),
        "availability_code": str(config.get("availability_code") or "unknown"),
        "model": str(config.get("model") or ""),
    }, headers={"Cache-Control": "no-store"})


def regenerate_capture_clips(match_id: int, request: Request, background_tasks: BackgroundTasks,
                             db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    root = latest_capture_root(match)
    if root is None or not (root / "capture.webm").is_file():
        raise HTTPException(409, "La capture source n'est plus disponible. Il faut fournir de nouveau la vidéo.")
    if not report_progress(match, root=root)["active"]:
        import time
        from capture_turbo_routes_v13 import _enrich_after_report
        state = _capture_base._read_state(root)
        state.update(media_status="queued", media_updated_at=time.time())
        write_state_atomic(root, state)
        background_tasks.add_task(_enrich_after_report, match.id, str(root))
    return RedirectResponse(f"/matches/{match_id}/analysis/result#sequences", status_code=303)


def install_priority_analysis_routes(app) -> None:
    from video_action_routes import router as video_action_router
    app.include_router(video_action_router)
    registrations = [
        ("/health/video-actions", video_action_readiness, "GET", None, "video_action_readiness"),
        ("/matches/{match_id}/analysis/report.html", download_analysis_report, "GET", HTMLResponse, "download_analysis_report"),
        ("/analysis/url/create", create_flexible_url_analysis, "POST", None, "product_create_url_analysis"),
        ("/matches", create_flexible_uploaded_match, "POST", None, "product_create_uploaded_match"),
        ("/matches/{match_id}/analysis/start", start_real_analysis, "POST", None, "product_start_analysis"),
        ("/matches/{match_id}/url-analysis/start", start_real_url_analysis, "POST", None, "product_start_url_analysis"),
        ("/matches/{match_id}/analysis/browser-capture", turbo_browser_capture_page, "GET", HTMLResponse, "turbo_browser_capture_page"),
        ("/matches/{match_id}/analysis/browser-capture/session", turbo_create_session, "POST", None, "turbo_capture_session"),
        ("/matches/{match_id}/analysis/browser-capture/chunk", turbo_append_chunk, "POST", None, "turbo_capture_chunk"),
        ("/matches/{match_id}/analysis/browser-capture/frame", turbo_progress_frame, "POST", None, "turbo_capture_frame"),
        ("/matches/{match_id}/analysis/browser-capture/status", turbo_capture_status, "GET", None, "turbo_capture_status"),
        ("/matches/{match_id}/analysis/browser-capture/finish", turbo_finish_capture, "POST", None, "turbo_capture_finish"),
        ("/matches/{match_id}/analysis/result", clean_analysis_result, "GET", HTMLResponse, "product_analysis_result"),
        ("/matches/{match_id}/analysis/progress", saved_report_progress, "GET", None, "saved_report_progress"),
        ("/matches/{match_id}/analysis/captured-clips", regenerate_capture_clips, "POST", None, "regenerate_capture_clips"),
        ("/matches/{match_id}/analysis/evidence-pack", regenerate_exact_evidence, "POST", None, "product_evidence_pack"),
        ("/matches/{match_id}/analysis/export.zip", export_complete_analysis, "GET", None, "product_analysis_export"),
        ("/analysis-library", ultimate_analysis_library, "GET", HTMLResponse, "product_analysis_library"),
        ("/analysis-library/{item_id}", published_ultimate_detail, "GET", HTMLResponse, "product_analysis_library_detail"),
    ]
    for path, endpoint, method, response_class, name in registrations:
        kwargs = {"methods": [method], "name": name}
        if response_class is not None:
            kwargs["response_class"] = response_class
        app.add_api_route(path, endpoint, **kwargs)
