"""V15 browser capture: eliminate the production 89% false-stall path.

V14 already publishes an evidence-limited terminal report when final Vision
processing fails. Production traces exposed two remaining lifecycle gaps:

* some MediaRecorder mosaic WebM files are seekable but report no frame-count
  duration through OpenCV, making the sparse mosaic verifier abort;
* the oldest V7 browser waiter can still surface its historical two-minute
  failure before the user observes V14's terminal rescue.

V15 keeps V14's evidence rules. It only adds a truthful duration hint for the
mosaic capture, a durable watchdog timestamp independent from progress.json
snapshot races, and a browser retry path that never labels the historical
2-minute threshold itself as an analysis failure.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time

import cv2
from fastapi import BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

import capture_turbo_routes_v14 as v14
import services.mosaic_match_analysis as mosaic_match_analysis
from analysis_product_routes import _capture_session_dir, _owned_match
from capture_turbo_routes import _read_state
from db import get_db
from services.vision_baseline import VisionBaselineError

log = logging.getLogger("aquametric.browser_capture.v15")

V15_FINALIZATION_WATCHDOG_SECONDS = v14.V14_FINALIZATION_WATCHDOG_SECONDS
_V15_START_MARKER = ".v15-finalization-start"
_LEGACY_TWO_MINUTE_FAILURE = (
    "throw new Error('La consolidation dépasse 2 minutes. La capture est conservée "
    "pour reprise, sans recommencer la lecture.');"
)


def _body(response) -> dict:
    try:
        return json.loads(bytes(response.body).decode("utf-8"))
    except Exception:
        return {}


def _session_root_for_media(video_path: Path) -> Path | None:
    """Find the browser-capture session root for original or derived media."""
    path = Path(video_path)
    candidates = [path.parent, *path.parents]
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if (candidate / "progress.json").exists():
            return candidate
    return None


def _capture_duration_hint(video_path: Path) -> float:
    """Derive encoded mosaic duration from authoritative source geometry.

    Four chronological panes played at x2 encode a source span in approximately
    span / (rate * panes) seconds. Quality pauses pause MediaRecorder as well, so
    they do not need to be added to this hint.
    """
    root = _session_root_for_media(video_path)
    if root is None:
        return 0.0
    state = _read_state(root)
    start = max(0.0, float(state.get("source_start_second") or 0.0))
    end = max(start, float(state.get("source_duration_seconds") or 0.0))
    rate = max(1.0, min(4.0, float(state.get("playback_rate") or 1.0)))
    raw_segments = int(state.get("parallel_segments") or 1)
    segments = 4 if raw_segments >= 4 else (2 if raw_segments >= 2 else 1)
    span = max(0.0, end - start)
    return span / (rate * segments) if span > 0.0 else 0.0


# run_mosaic_analysis is imported by older compatibility layers as a function,
# but its globals still resolve _probe on this module. Patching only _probe keeps
# all normal successful probes unchanged and adds a fallback for the exact
# production failure where OpenCV frame-count metadata is missing.
if getattr(mosaic_match_analysis._probe, "_aquametric_v15", False):
    _ORIGINAL_MOSAIC_PROBE = getattr(
        mosaic_match_analysis._probe,
        "_aquametric_original_probe",
        mosaic_match_analysis._probe,
    )
else:
    _ORIGINAL_MOSAIC_PROBE = mosaic_match_analysis._probe


def _probe_with_capture_hint(video_path: Path):
    try:
        return _ORIGINAL_MOSAIC_PROBE(video_path)
    except VisionBaselineError as exc:
        if "duration could not be determined" not in str(exc).lower():
            raise
        duration_hint = _capture_duration_hint(Path(video_path))
        if duration_hint <= 0.0:
            raise

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            cap.release()
            raise
        try:
            fps = max(0.0, float(cap.get(cv2.CAP_PROP_FPS) or 0.0))
            frames = max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
            width = max(0, int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0))
            height = max(0, int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
            ok, frame = cap.read()
            if not ok or frame is None or getattr(frame, "size", 0) <= 0:
                raise exc
        finally:
            cap.release()

        log.warning(
            "V15 mosaic duration metadata missing; using capture geometry hint path=%s hint=%.2fs",
            video_path,
            duration_hint,
        )
        return fps, frames, width, height, duration_hint


_probe_with_capture_hint._aquametric_v15 = True
_probe_with_capture_hint._aquametric_original_probe = _ORIGINAL_MOSAIC_PROBE
mosaic_match_analysis._probe = _probe_with_capture_hint


def _marker_path(root: Path) -> Path:
    return Path(root) / _V15_START_MARKER


def _write_start_marker(root: Path, started_at: float | None = None) -> float:
    """Persist one watchdog clock outside progress.json snapshot updates."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    value = float(time.time() if started_at is None else started_at)
    target = _marker_path(root)
    tmp = root / f".{_V15_START_MARKER}.{os.getpid()}.{time.time_ns()}.tmp"
    try:
        tmp.write_text(f"{value:.6f}", encoding="utf-8")
        os.replace(tmp, target)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return value


def _read_start_marker(root: Path) -> float:
    try:
        return max(0.0, float(_marker_path(root).read_text(encoding="utf-8").strip()))
    except Exception:
        return 0.0


def _clear_start_marker(root: Path) -> None:
    try:
        _marker_path(root).unlink(missing_ok=True)
    except OSError:
        pass


def _marker_should_rescue(root: Path, status: str, now: float | None = None) -> bool:
    if str(status or "") in {"complete", "partial"}:
        return False
    started = _read_start_marker(root)
    if started <= 0.0:
        return False
    current = float(time.time() if now is None else now)
    return current - started >= V15_FINALIZATION_WATCHDOG_SECONDS


def _patch_legacy_timeout(html: str, match_id: int) -> str:
    """Turn the inherited 2-minute false failure into authoritative retries."""
    if _LEGACY_TWO_MINUTE_FAILURE not in html:
        return html
    replacement = f"""
setStatus('Finalisation prolongée · vérification serveur maintenue, sans perdre la capture.');
for(let rescueAttempt=0;rescueAttempt<60;rescueAttempt++){{
  try{{
    const rescue=await jsonFetch(url);const p=rescue.progress||{{}};
    if(rescue.ok)applyServerProgress(p);
    const state=String(p.status||'');
    if(state==='complete'||state==='partial')return {{redirect:p.redirect||payload.redirect||'/matches/{match_id}/analysis/result',warning:p.warning||''}};
    if(state==='failed')throw new Error(p.error||'Échec de la consolidation finale.');
  }}catch(err){{if(rescueAttempt>=59)throw err;}}
  await new Promise(r=>setTimeout(r,1000));
}}
throw new Error('La finalisation serveur ne répond pas. La capture reste conservée et peut être reprise.');
""".strip()
    return html.replace(_LEGACY_TWO_MINUTE_FAILURE, replacement, 1)


def turbo_browser_capture_page(
    match_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    response = v14.turbo_browser_capture_page(match_id=match_id, request=request, db=db)
    html = bytes(response.body).decode("utf-8")
    return HTMLResponse(_patch_legacy_timeout(html, match_id), status_code=response.status_code)


# Keep V14's proven streaming path unchanged.
turbo_create_session = v14.turbo_create_session
turbo_append_chunk = v14.turbo_append_chunk
turbo_progress_frame = v14.turbo_progress_frame


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
    response = v14.turbo_finish_capture(
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
        client_read_percent=client_read_percent,
        client_finish_reason=client_finish_reason,
        db=db,
    )
    payload = _body(response)
    if payload.get("accepted") and root.is_dir():
        state = _read_state(root)
        started_at = float(state.get("v14_finalization_started_at") or time.time())
        _write_start_marker(root, started_at)
        log.info("V15 durable finalization watchdog armed match=%s session=%s", match_id, session_id)
    return response


def turbo_capture_status(
    match_id: int,
    request: Request,
    session_id: str,
    db: Session = Depends(get_db),
):
    response = v14.turbo_capture_status(
        match_id=match_id,
        request=request,
        session_id=session_id,
        db=db,
    )
    payload = _body(response)
    progress = payload.get("progress") if isinstance(payload.get("progress"), dict) else None
    if not progress:
        return response

    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    status = str(progress.get("status") or "")
    if status in {"complete", "partial"}:
        _clear_start_marker(root)
        return response

    # The marker is written only after /finish was accepted, so any non-terminal
    # snapshot older than the watchdog budget is safe to rescue. This remains
    # true even if a stale concurrent progress.json writer temporarily restored
    # status='running' or removed v14_finalization_started_at.
    if root.is_dir() and _marker_should_rescue(root, status):
        reason = str(progress.get("error") or "watchdog V15 durable > 35 s")
        rescued = v14._publish_fallback_report(match_id, str(root), reason)
        if rescued:
            try:
                v14.v11._close_finalize_marker(match_id, str(root))
            except Exception:
                pass
            _clear_start_marker(root)
            log.warning("V15 watchdog published terminal report match=%s prior_status=%s", match_id, status)
            return JSONResponse({"ok": True, "progress": rescued})
    return response
