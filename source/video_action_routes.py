"""Owned progress, resumable action analysis and every action's video evidence."""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
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


@router.post("/matches/{match_id}/analysis/actions/start")
def start_actions(match_id: int, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from analysis_product_routes import UPLOAD_DIR
    from services.capture_report_progress import latest_capture_root
    _, match = _owned(match_id, request, db)
    if not provider_configuration()["configured"]:
        raise HTTPException(503, detail=provider_configuration()["message"])
    if not run_progress(db, match)["active"]:
        if match.video_source == "upload" and match.video_path and (UPLOAD_DIR / Path(match.video_path).name).is_file():
            background_tasks.add_task(run_upload_actions, match.id)
        else:
            root = latest_capture_root(match)
            if not root or not (root / "capture.webm").is_file():
                raise HTTPException(422, detail="Aucun fichier vidéo exploitable n’est conservé pour ce dossier. Importe la vidéo ou reprends sa capture.")
            background_tasks.add_task(run_capture_actions, match.id, str(root))
    return RedirectResponse(f"/matches/{match.id}/analysis/result?action_queued=1", status_code=303)


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
