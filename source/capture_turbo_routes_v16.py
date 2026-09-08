"""V16 browser capture: publish first, enrich second.

The browser must never wait at 89-99% for ffmpeg/OpenCV/OCR finalisation. V16
turns evidence already processed during playback into a publishable terminal
report as soon as /finish is accepted. More expensive verification then runs in
BackgroundTasks and may upgrade the report, but it can no longer block the user.

A separate report-ready marker is authoritative. Late chunk/frame requests may
still race with progress.json, but they cannot make a finished session look
running again because /status restores the terminal marker immediately.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time

from fastapi import BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

import capture_turbo_routes_v15 as v15
from analysis_product_routes import _capture_session_dir, _owned_match
from capture_turbo_routes import _FAST_CAPTURE_SENTINEL, _read_state, _write_state
from db import SessionLocal, get_db
from models import Match
from services.live_frame_match_analysis import live_frame_coverage, run_live_frame_analysis

log = logging.getLogger("aquametric.browser_capture.v16")

_REPORT_MARKER = ".v16-report-ready.json"

# Keep V15's proven capture transport and progressive analysis.
turbo_create_session = v15.turbo_create_session
turbo_append_chunk = v15.turbo_append_chunk
turbo_progress_frame = v15.turbo_progress_frame


def _body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def _report_marker_path(root: Path) -> Path:
    return Path(root) / _REPORT_MARKER


def _write_report_marker(root: Path, state: dict) -> dict:
    """Publish an authoritative terminal marker outside mutable progress.json."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": str(state.get("status") or "partial"),
        "analysis_percent": 100.0,
        "read_percent": max(100.0, float(state.get("read_percent") or 0.0)),
        "phase": str(state.get("phase") or "rapport disponible"),
        "redirect": str(state.get("redirect") or ""),
        "finalization_engine": str(state.get("finalization_engine") or "report-first-v16"),
        "report_quality": str(state.get("report_quality") or "published_progressive_evidence"),
        "report_ready": True,
        "retry_available": False,
        "enrichment_status": str(state.get("enrichment_status") or "queued"),
        "visual_samples": int(state.get("visual_samples") or 0),
        "scoreboard_observations": int(state.get("scoreboard_observations") or 0),
        "retained_live_frames": int(state.get("retained_live_frames") or 0),
        "published_at": float(state.get("v16_report_published_at") or state.get("published_at") or time.time()),
    }
    for key in (
        "enrichment_warning",
        "enrichment_elapsed_seconds",
        "media_normalization",
        "evidence_confidence",
        "evidence_coverage_ratio",
        "finalization_job_status",
        "finalization_job_progress",
    ):
        if key in state:
            payload[key] = state[key]
    target = _report_marker_path(root)
    tmp = root / f".{_REPORT_MARKER}.{os.getpid()}.{time.time_ns()}.tmp"
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, target)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return payload


def _read_report_marker(root: Path) -> dict:
    try:
        payload = json.loads(_report_marker_path(Path(root)).read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) and payload.get("report_ready") else {}
    except Exception:
        return {}


def _terminal_from_marker(root: Path, current: dict | None = None) -> dict:
    marker = _read_report_marker(root)
    if not marker:
        return current or {}
    state = dict(current or {})
    state.update(marker)
    state["analysis_percent"] = 100.0
    state["report_ready"] = True
    if str(state.get("status") or "") not in {"complete", "partial"}:
        state["status"] = "partial"
    return state


def _publish_report_first(match_id: int, root: Path) -> dict:
    """Persist a truthful report using only evidence already obtained live."""
    existing = _read_report_marker(root)
    if existing:
        return _terminal_from_marker(root, _read_state(root))

    state = v15.v14._publish_fallback_report(
        match_id,
        str(root),
        "V16 report-first checkpoint: publication before optional heavy verification",
    )
    if not state:
        return {}
    state.update({
        "status": "partial",
        "analysis_percent": 100.0,
        "read_percent": 100.0,
        "phase": "rapport disponible immédiatement · enrichissement IA en arrière-plan",
        "redirect": f"/matches/{match_id}/analysis/result",
        "finalization_engine": "report-first-v16",
        "report_quality": "published_progressive_evidence",
        "report_ready": True,
        "retry_available": False,
        "enrichment_status": "queued",
        "v16_report_published_at": time.time(),
    })
    _write_state(root, state)
    try:
        v15._clear_start_marker(root)
    except Exception:
        pass
    try:
        v15.v14.v11._close_finalize_marker(match_id, str(root))
    except Exception:
        pass

    # Report publication, not the later verifier, closes the user-facing job.
    # A partial report is terminal but remains labelled partial so evidence
    # quality is never confused with processing completion.
    state = _read_state(root)
    state.update({
        "status": "partial",
        "analysis_percent": 100.0,
        "read_percent": 100.0,
        "phase": "rapport disponible immédiatement · enrichissement IA en arrière-plan",
        "redirect": f"/matches/{match_id}/analysis/result",
        "finalization_engine": "report-first-v16",
        "report_quality": "published_progressive_evidence",
        "report_ready": True,
        "retry_available": False,
        "enrichment_status": "queued",
        "v16_report_published_at": float(state.get("v16_report_published_at") or time.time()),
        "finalization_job_status": "partial",
        "finalization_job_progress": 100,
    })
    _write_state(root, state)
    _write_report_marker(root, state)
    log.info(
        "V16 report-first published match=%s samples=%s retained=%s",
        match_id,
        state.get("visual_samples"),
        state.get("retained_live_frames"),
    )
    return state


def _verify_after_publish(
    match_id: int,
    root_value: str,
    start: float,
    total_duration: float,
    rate: float,
    segments: int,
) -> None:
    """Upgrade the already-published report without touching its availability."""
    root = Path(root_value)
    db = SessionLocal()
    started = time.monotonic()
    try:
        match = db.get(Match, match_id)
        if not match or not root.is_dir():
            return
        state = _terminal_from_marker(root, _read_state(root))
        coverage = live_frame_coverage(root, state)
        state.update({
            "status": str(state.get("status") or "partial"),
            "analysis_percent": 100.0,
            "report_ready": True,
            "enrichment_status": "running",
            "phase": "rapport disponible · vérification enrichie en arrière-plan",
        })
        _write_state(root, state)
        _write_report_marker(root, state)

        if coverage.get("eligible"):
            result = run_live_frame_analysis(
                db,
                match,
                root,
                source_start_second=start,
                source_duration_seconds=total_duration,
                playback_rate=rate,
                parallel_segments=segments,
                visual_samples=v15.v14.V14_LIVE_VISUAL_SAMPLES,
                ocr_samples=v15.v14.V14_LIVE_OCR_SAMPLES,
            )
            engine = "live-frame-enriched-v16"
            quality = "verified_live_evidence"
        else:
            source_path = root / "capture.webm"
            derived_dir = root / "derived_v16"
            derived_dir.mkdir(parents=True, exist_ok=True)
            # Call through V7, the owner of browser-media analysis behavior, so
            # resilience hooks and regression extensions remain compatible.
            analysis_source, media_info = v15.v14.v13.v10.v7.normalize_browser_capture(
                source_path,
                derived_dir,
                fast_analysis=True,
            )
            mosaic = segments >= 4 and total_duration > start + 30.0
            if mosaic:
                result = v15.v14.v13.v10.v7.run_mosaic_analysis(
                    db,
                    match,
                    analysis_source,
                    source_start_second=start,
                    source_duration_seconds=total_duration,
                    playback_rate=rate,
                    parallel_segments=segments,
                    visual_samples=v15.v14.V14_MOSAIC_VISUAL_SAMPLES,
                    ocr_samples=v15.v14.V14_MOSAIC_OCR_SAMPLES,
                )
            else:
                encoded_offset = (_FAST_CAPTURE_SENTINEL + start) if rate >= 1.75 else start
                result = v15.v14.v13.v10.v7.run_rapid_analysis(
                    db,
                    match,
                    analysis_source,
                    derived_dir,
                    include_audio=False,
                    visual_samples=v15.v14.V14_VIDEO_VISUAL_SAMPLES,
                    ocr_samples=v15.v14.V14_VIDEO_OCR_SAMPLES,
                    source_kind="browser_capture",
                    persist_visual_artifacts=False,
                    time_offset_seconds=encoded_offset,
                )
            engine = "sparse-video-enriched-v16"
            quality = "verified_sparse_video"
            state = _terminal_from_marker(root, _read_state(root))
            state["media_normalization"] = media_info.get("normalization", "unknown")
            _write_state(root, state)

        db.commit()
        summary = result.get("summary", {}) or {}
        elapsed = time.monotonic() - started
        state = _terminal_from_marker(root, _read_state(root))
        state.update({
            "status": "complete",
            "analysis_percent": 100.0,
            "read_percent": 100.0,
            "report_ready": True,
            "phase": "rapport enrichi V16 prêt",
            "redirect": f"/matches/{match_id}/analysis/result",
            "finalization_engine": engine,
            "report_quality": quality,
            "enrichment_status": "complete",
            "enrichment_elapsed_seconds": round(elapsed, 2),
            "visual_samples": int(summary.get("visual_samples") or state.get("visual_samples") or 0),
            "scoreboard_observations": int(summary.get("scoreboard_observations") or state.get("scoreboard_observations") or 0),
            "retained_live_frames": int(summary.get("retained_live_frames") or coverage.get("records") or state.get("retained_live_frames") or 0),
        })
        _write_state(root, state)
        _write_report_marker(root, state)
        match.status = "browser_capture_analyzed"
        db.commit()
        log.info("V16 enrichment complete match=%s engine=%s elapsed=%.2fs", match_id, engine, elapsed)
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        state = _terminal_from_marker(root, _read_state(root))
        if state:
            state.update({
                "status": "partial",
                "analysis_percent": 100.0,
                "report_ready": True,
                "phase": "rapport disponible · enrichissement secondaire indisponible",
                "enrichment_status": "failed",
                "enrichment_warning": str(exc)[:240],
            })
            _write_state(root, state)
            _write_report_marker(root, state)

        # A verifier is secondary once the V16 report marker exists. Some legacy
        # analysis functions mark the match failed before raising; restore the
        # published lifecycle state so history/library surfaces do not contradict
        # the report that is already available to the user.
        try:
            published_match = db.get(Match, match_id)
            if published_match:
                published_match.status = "browser_capture_analyzed"
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        log.exception("V16 enrichment failed after report publication match=%s", match_id)
    finally:
        db.close()


def _patch_report_first_ui(html: str, match_id: int) -> str:
    needle = "if(payload.accepted){const done=await waitForFinalReport(payload);"
    if needle not in html:
        return html
    immediate = (
        "if(payload.accepted&&payload.report_ready){clearInterval(statusTick);statusTick=null;"
        "analysisPercent=100;setBars(100,100,'Lecture complète','Rapport disponible · enrichissement en arrière-plan');"
        "setStatus('Analyse publiée. Ouverture immédiate du rapport…');"
        f"setTimeout(()=>location.href=payload.redirect||'/matches/{match_id}/analysis/result',120);return;}}"
        "if(payload.accepted){const done=await waitForFinalReport(payload);"
    )
    return html.replace(needle, immediate, 1)


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    response = v15.turbo_browser_capture_page(match_id=match_id, request=request, db=db)
    html = bytes(response.body).decode("utf-8")
    return HTMLResponse(_patch_report_first_ui(html, match_id), status_code=response.status_code)


def _finish_payload(match_id: int, session_id: str, progress: dict) -> dict:
    return {
        "ok": True,
        "accepted": True,
        "report_ready": True,
        "analysis_percent": 100.0,
        "status": progress.get("status", "partial"),
        "redirect": progress.get("redirect") or f"/matches/{match_id}/analysis/result",
        "status_url": f"/matches/{match_id}/analysis/browser-capture/status?session_id={session_id}",
        "finalization_engine": progress.get("finalization_engine") or "report-first-v16",
        "report_quality": progress.get("report_quality") or "published_progressive_evidence",
        "enrichment_status": progress.get("enrichment_status") or "queued",
        # Compatibility metadata; unlike earlier versions these are not waits.
        "non_blocking": True,
        "fast_finalization": True,
        "max_wait_before_rescue_seconds": 0.0,
    }


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
    existing = _read_report_marker(root) if root.is_dir() else {}
    if existing:
        progress = _terminal_from_marker(root, _read_state(root))
        return JSONResponse(_finish_payload(match_id, session_id, progress))

    # Reuse every V15 validation/scope check, but discard its heavy V14 tasks.
    shadow_tasks = BackgroundTasks()
    response = v15.turbo_finish_capture(
        match_id=match_id,
        request=request,
        background_tasks=shadow_tasks,
        session_id=session_id,
        source_start_second=source_start_second,
        source_duration_seconds=source_duration_seconds,
        playback_rate=playback_rate,
        parallel_segments=parallel_segments,
        scope_mode=scope_mode,
        analysis_scope_start_second=analysis_scope_start_second,
        analysis_scope_end_second=analysis_scope_end_second,
        client_read_percent=client_read_percent,
        client_finish_reason=client_finish_reason,
        db=db,
    )
    payload = _body(response)
    if not payload.get("accepted"):
        return response

    state = _read_state(root)
    start = max(0.0, float(state.get("source_start_second") or source_start_second or 0.0))
    total_duration = max(0.0, float(state.get("source_duration_seconds") or source_duration_seconds or 0.0))
    rate = max(1.0, min(4.0, float(state.get("playback_rate") or playback_rate or 1.0)))
    raw_segments = int(state.get("parallel_segments") or parallel_segments or 1)
    segments = 4 if raw_segments >= 4 else (2 if raw_segments >= 2 else 1)

    published = _publish_report_first(match_id, root)
    if not published:
        # Explicit failure is preferable to another invisible 89% wait.
        return JSONResponse(
            {"ok": False, "accepted": False, "error": "Le rapport initial n'a pas pu être publié."},
            status_code=500,
        )

    background_tasks.add_task(
        _verify_after_publish,
        match_id,
        str(root),
        start,
        total_duration,
        rate,
        segments,
    )
    background_tasks.add_task(v15.v14.v13._enrich_after_report, match_id, str(root))
    return JSONResponse(_finish_payload(match_id, session_id, published))


def turbo_capture_status(match_id: int, request: Request, session_id: str, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    if root.is_dir():
        marker = _read_report_marker(root)
        if marker:
            # The marker is authoritative even if a late writer regressed progress.json.
            raw = _read_state(root)
            state = _terminal_from_marker(root, raw)
            if str(raw.get("status") or "") not in {"complete", "partial"} or float(raw.get("analysis_percent") or 0.0) < 100.0:
                _write_state(root, state)
            return JSONResponse({"ok": True, "progress": state})
    return v15.turbo_capture_status(match_id=match_id, request=request, session_id=session_id, db=db)
