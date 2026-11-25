"""Owned progress, resumable action analysis and every action's video evidence."""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import SessionLocal, get_db
from models import AnalysisJob, Match, MediaArtifact, VideoActionAnalysis
from services.video_action_provider import provider_configuration
from services.video_action_report import action_report, run_progress
from services.video_action_runner import run_video_actions

router = APIRouter()
_CLIP_LOCK = Lock()


def workflow_active(db, match_id):
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.match_id == match_id, AnalysisJob.stage == "video_workflow")
                    .order_by(AnalysisJob.id.desc()))
    return bool(job and job.status in {"running", "queued"} and
                datetime.now(timezone.utc).timestamp() - job.created_at.replace(tzinfo=timezone.utc).timestamp() < 1200)


def _owned(match_id, request, db):
    from analysis_product_routes import _owned_match
    return _owned_match(match_id, request, db)


def run_capture_actions(match_id: int, root_value: str):
    from capture_turbo_routes import _read_state
    with SessionLocal() as db:
        match = db.get(Match, match_id)
        if match:
            root = Path(root_value)
            run_video_actions(db, match, root / "capture.webm", capture_state=_read_state(root))


def run_upload_actions(match_id):
    from analysis_product_routes import UPLOAD_DIR
    with SessionLocal() as db:
        match = db.get(Match, match_id)
        if match and match.video_source == "upload" and match.video_path:
            run_video_actions(db, match, UPLOAD_DIR / Path(match.video_path).name)


def run_segment_actions(match_id: int, segment_id: int):
    """Analyze an independently uploaded quarter; keep its own source run."""
    from analysis_product_routes import UPLOAD_DIR
    from models import MatchVideoSegment
    with SessionLocal() as db:
        match = db.get(Match, match_id)
        segment = db.get(MatchVideoSegment, segment_id)
        if not match or not segment or segment.match_id != match.id:
            return
        if segment.source_type != "upload" or not segment.video_path:
            return
        file_path = UPLOAD_DIR / Path(segment.video_path).name
        if file_path.is_file():
            run_video_actions(db, match, file_path)


def upload_analysis_background(match_id, job_id, include_audio):
    from analysis_product_routes import UPLOAD_DIR, EVIDENCE_DIR
    from services.complete_analysis_runner import run_complete_analysis
    from services.deep_analysis_sequences import materialize_deep_sequence_pack
    with SessionLocal() as db:
        match, job = db.get(Match, match_id), db.get(AnalysisJob, job_id)
        if not match or not job:
            return
        job.status, job.message = "running", "Lecture vidéo, score et reconnaissance des actions en cours."
        db.commit()
        try:
            run_complete_analysis(db, match, UPLOAD_DIR, EVIDENCE_DIR, include_audio=include_audio)
            job.progress, job.message = 90, "Statistiques enregistrées, préparation des extraits."
            db.commit()
            materialize_deep_sequence_pack(db, match, UPLOAD_DIR, EVIDENCE_DIR,
                                           max_targets=72, max_clips=48, max_image_targets=72, triple_frames=48)
            job.status, job.progress, job.message = "complete", 100, "Traitement terminé ; le rapport indique la couverture et les mesures disponibles."
        except Exception:
            db.rollback()
            job.status, job.message = "failed", "Le traitement s’est interrompu. Consulte les résultats enregistrés et relance l’analyse."
        db.commit()


@router.get("/matches/{match_id}/analysis/actions/status")
def actions_status(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned(match_id, request, db)
    progress = run_progress(db, match)
    return JSONResponse(progress, headers={"Cache-Control": "private, no-store"})


@router.get("/matches/{match_id}/analysis/actions/live")
def live_actions(match_id: int, request: Request, db: Session = Depends(get_db)):
    """Per-sequence automatic provisional counters, without a page reload."""
    _, match = _owned(match_id, request, db)
    from services.live_action_dashboard import live_action_dashboard
    return JSONResponse(live_action_dashboard(db, match), headers={
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.post("/matches/{match_id}/analysis/actions/start")
def start_actions(match_id: int, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from analysis_product_routes import UPLOAD_DIR
    from services.capture_report_progress import latest_capture_root
    _, match = _owned(match_id, request, db)
    if not provider_configuration()["configured"]:
        raise HTTPException(503, detail=provider_configuration()["message"])
    if not run_progress(db, match)["active"]:
        from services.video_action_report import latest_run
        previous=latest_run(db,match.id)
        if previous and previous.source_kind=="youtube_direct":
            from services.youtube_direct_actions import prepare_run,run_direct_youtube_actions
            from services.video_action_provider import VideoActionError
            try:
                run,scheduled=prepare_run(db,match,previous.duration_seconds)
            except (ValueError,VideoActionError) as exc:
                raise HTTPException(422,"La reprise YouTube nécessite une durée de vidéo valide.") from None
            if scheduled:
                background_tasks.add_task(run_direct_youtube_actions,match.id,run.id)
        elif previous and previous.source_kind=="cloud":
            from services.cloud_video_actions import run_cloud_video_actions
            background_tasks.add_task(run_cloud_video_actions,match.id,previous.source_path)
        elif match.video_source=="cloud" and match.video_path:
            from services.cloud_video_actions import run_cloud_video_actions
            background_tasks.add_task(run_cloud_video_actions,match.id,match.video_path)
        elif match.video_source == "upload" and match.video_path and (UPLOAD_DIR / Path(match.video_path).name).is_file():
            background_tasks.add_task(run_upload_actions, match.id)
        else:
            root = latest_capture_root(match)
            if not root or not (root / "capture.webm").is_file():
                raise HTTPException(422, detail="Aucun fichier vidéo exploitable n’est conservé pour ce dossier. Importe la vidéo ou reprends sa capture.")
            background_tasks.add_task(run_capture_actions, match.id, str(root))
    return RedirectResponse(f"/matches/{match.id}/analysis/result?action_queued=1", status_code=303)


@router.post("/matches/{match_id}/analysis/youtube/direct")
def start_public_youtube_direct(
    match_id: int, request: Request, background_tasks: BackgroundTasks,
    duration_minutes: float = Form(..., gt=0, le=240),
    db: Session = Depends(get_db),
):
    """No YouTube download/capture; provider reads allowed public video URL."""
    from services.youtube_direct_actions import (
        action_plan, canonical_public_youtube, prepare_run, run_direct_youtube_actions,
    )
    from services.video_action_provider import VideoActionError
    _,match=_owned(match_id,request,db)
    if match.video_source!="youtube" or not match.video_url:
        raise HTTPException(400,"Une vidéo YouTube valide est nécessaire.")
    try:
        canonical_public_youtube(match.video_url)
        duration=round(duration_minutes*60,3)
        action_plan(duration)
        run,scheduled=prepare_run(db,match,duration)
    except (ValueError,VideoActionError) as exc:
        raise HTTPException(400 if isinstance(exc,ValueError) else 503,str(exc)) from None
    if scheduled:
        background_tasks.add_task(run_direct_youtube_actions,match.id,run.id)
    return RedirectResponse(f"/matches/{match.id}/analysis/result#liveAutomaticStats",status_code=303)


@router.get("/matches/{match_id}/analysis/actions/{run_id}/{action_key}/clip")
def action_clip(match_id: int, run_id: int, action_key: str, request: Request, db: Session = Depends(get_db)):
    from analysis_product_routes import EVIDENCE_DIR
    from services.capture_sequence_media import create_capture_clip
    _, match = _owned(match_id, request, db)
    run = db.get(VideoActionAnalysis, run_id)
    if not run or run.match_id != match.id:
        raise HTTPException(404, detail="Analyse introuvable dans ce dossier.")
    # Resolve historical links against their own run, not today's latest run.
    report = action_report(db, match, run=run)
    action = next((a for a in report["events"] if a["key"] == action_key), None)
    if not action:
        raise HTTPException(404, detail="Action introuvable.")
    if run.source_kind=="youtube_direct":
        from services.youtube_direct_actions import canonical_public_youtube
        from services.video import timestamped_video_url
        try:
            url=canonical_public_youtube(run.source_path)
        except ValueError:
            raise HTTPException(410,"La référence YouTube a changé.") from None
        return RedirectResponse(timestamped_video_url(url,action["second"]),status_code=307)
    if run.source_kind=="cloud":
        from services import large_video_storage as storage
        from models import LargeVideoUpload
        row=db.scalar(select(LargeVideoUpload).where(
            LargeVideoUpload.owner_id==match.owner_id,
            LargeVideoUpload.match_id==match.id,
            LargeVideoUpload.object_key==run.source_path,
            LargeVideoUpload.status=="complete"))
        if not row:
            raise HTTPException(404,"Vidéo cloud non associée au match.")
        destination=storage.signed_video_url(run.source_path)
        return RedirectResponse(destination+f"#t={max(0,int(action['second']))}",status_code=307)
    source_name = f"video_actions_{run.id}"
    marker = f"action_key={action_key} "
    with _CLIP_LOCK:
        artifact = db.scalar(select(MediaArtifact).where(MediaArtifact.match_id == match.id,
            MediaArtifact.source == source_name, MediaArtifact.artifact_type == "clip", MediaArtifact.note.startswith(marker)))
        path = EVIDENCE_DIR / Path(artifact.file_path).name if artifact and artifact.file_path else None
        if not path or not path.is_file():
            source = Path(run.source_path)
            if not source.is_file():
                raise HTTPException(410, detail="Le fichier vidéo source n’est plus disponible. Les statistiques restent consultables.")
            segment = next(s for s in json.loads(run.segments_json) if s["index"] == action["segment_index"])
            first, last = max(segment["clip_start"], action["second"] - 5), min(segment["clip_end"], action["second"] + 7)
            window = {"pane": segment["pane"], "segments": segment["panes"], "rate": segment["rate"],
                      "capture_start": segment["capture_start"] + (first - segment["clip_start"]) / segment["rate"],
                      "capture_duration": (last - first) / segment["rate"]}
            try:
                path = create_capture_clip(source, EVIDENCE_DIR, window)
            except Exception:
                raise HTTPException(422, detail="Cet extrait n’a pas pu être décodé. La source est conservée pour une nouvelle tentative.") from None
            artifact = artifact or MediaArtifact(match_id=match.id, artifact_type="clip", analysis_type="action", source=source_name)
            artifact.second, artifact.start_second, artifact.end_second = action["second"], first, last
            artifact.title = f"{action['label']} · {action['identity']} · détection automatique"
            artifact.note = marker + action["evidence"]
            artifact.file_path, artifact.mime_type, artifact.is_downloadable = path.name, "video/mp4", True
            db.add(artifact)
            db.commit()
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "private, no-store"})
