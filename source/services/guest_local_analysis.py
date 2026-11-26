"""Bounded local guest analysis; no paid provider."""
from pathlib import Path
from threading import BoundedSemaphore
from sqlalchemy import select

_slots = BoundedSemaphore(1)

def queue_guest_local(db, match, background_tasks):
    from models import AnalysisJob
    pending = db.scalar(select(AnalysisJob).where(
        AnalysisJob.match_id == match.id, AnalysisJob.status.in_(("queued","running"))))
    if pending:
        return
    if not _slots.acquire(blocking=False):
        match.status = "uploaded_ready"
        db.commit()
        return
    try:
        job = AnalysisJob(match_id=match.id, stage="guest_local_vision", progress=0,
                          status="queued", message="Vision locale en attente.")
        db.add(job)
        db.commit()
        background_tasks.add_task(run_guest_local, match.id, job.id)
    except Exception:
        _slots.release()
        raise

def run_guest_local(match_id, job_id):
    from db import SessionLocal
    from models import Match, AnalysisJob
    db = SessionLocal()
    try:
        match, job = db.get(Match, match_id), db.get(AnalysisJob, job_id)
        if not match or not job:
            return
        from analysis_product_routes import UPLOAD_DIR, EVIDENCE_DIR
        from services.rapid_match_analysis import run_rapid_analysis
        if match.video_source != "upload" or not match.video_path:
            raise ValueError("Source locale requise.")
        source = UPLOAD_DIR / Path(match.video_path).name
        if not source.is_file():
            raise ValueError("Fichier local absent.")
        job.status, job.progress = "running", 5
        match.status = "analysis_running"
        db.commit()
        run_rapid_analysis(db, match, source, EVIDENCE_DIR, include_audio=False,
                           visual_samples=120, ocr_samples=40,
                           source_kind="upload", persist_visual_artifacts=False)
        job.status, job.progress, job.message = "complete", 100, "Vision/OCR locale terminée. Candidats à vérifier."
        match.status = "analysis_ready"
        db.commit()
    except Exception:
        db.rollback()
        job, match = db.get(AnalysisJob, job_id), db.get(Match, match_id)
        if job:
            job.status, job.message = "failed", "Vision locale impossible sur cette source."
        if match:
            match.status = "analysis_failed"
        db.commit()
    finally:
        db.close()
        _slots.release()
