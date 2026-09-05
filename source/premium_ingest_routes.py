from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import SessionLocal, get_db
from models import Club, Match, ScoutingTeam, Team, User
from services.analysis_product import run_product_analysis
from services.complete_analysis_runner import run_complete_analysis
from services.deep_analysis_sequences import materialize_deep_sequence_pack
from services.video import is_http_url, youtube_embed

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads")); UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", BASE_DIR / "evidence")); EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024")); MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".ogv", ".ogg"}


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _clean(value: str, length: int = 160):
    return (value or "").strip()[:length]


def _resolve_team(db: Session, user: User, team_id: int | None, team_name: str):
    """Resolve both legacy per-user team ids and the universal catalogue selector.

    Catalogue teams are materialised as a private workspace team for the user so
    match events, players and analysis remain isolated from other accounts.
    """
    if team_id:
        team = db.get(Team, team_id)
        if team and team.owner_id == user.id:
            return team
        raise HTTPException(status_code=400, detail="Selected team is not available in this workspace.")

    name = _clean(team_name)
    if not name:
        raise HTTPException(status_code=400, detail="Choose an AquaMetric team or enter a catalogue team name.")
    existing = db.scalar(select(Team).where(Team.owner_id == user.id, func.lower(Team.name) == name.lower()))
    if existing:
        return existing

    scouting = db.scalar(select(ScoutingTeam).where(func.lower(ScoutingTeam.name) == name.lower()))
    country = scouting.country if scouting else "International"
    division = scouting.competition if scouting else "AquaMetric analysis catalogue"
    category = scouting.category if scouting and scouting.category else "Women"
    club = db.scalar(select(Club).where(Club.owner_id == user.id, func.lower(Club.name) == name.lower()))
    if not club:
        club = Club(name=name, country=country or "International", division=division or "", category=category, owner_id=user.id)
        db.add(club); db.flush()
    team = Team(name=name, club_id=club.id, owner_id=user.id, category=category)
    db.add(team); db.flush()
    return team


def _save_upload(file: UploadFile, user_id: int, team_id: int):
    original = Path(file.filename or "video").name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported video format: {suffix}")
    safe = f"u{user_id}_t{team_id}_{uuid.uuid4().hex}{suffix}"
    target = UPLOAD_DIR / safe
    total = 0
    try:
        with target.open("wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"Video exceeds {MAX_UPLOAD_MB} MB.")
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()
    if not total:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded video is empty.")
    return safe


def _run_owned_video(match_id: int):
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if not match:
            return
        match.status = "analysis_running"; db.commit()
        try:
            run_complete_analysis(db, match, UPLOAD_DIR, EVIDENCE_DIR, include_audio=True)
            materialize_deep_sequence_pack(
                db, match, UPLOAD_DIR, EVIDENCE_DIR,
                max_targets=72, max_clips=48, max_image_targets=72, triple_frames=48,
            )
            match.status = "analysis_ready"; db.commit()
        except Exception as exc:
            match.status = "analysis_failed"; db.commit()
            print(f"[premium-ingest] analysis failed for match {match_id}: {type(exc).__name__}: {exc}")
    finally:
        db.close()


def _run_remote_reference(match_id: int):
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        if not match:
            return
        match.status = "url_analysis_running"; db.commit()
        try:
            run_product_analysis(db, match, UPLOAD_DIR, EVIDENCE_DIR, include_audio=False)
            materialize_deep_sequence_pack(db, match, UPLOAD_DIR, EVIDENCE_DIR, max_targets=72, max_clips=0, max_image_targets=0)
            match.status = "url_reference_ready"; db.commit()
        except Exception as exc:
            match.status = "analysis_failed"; db.commit()
            print(f"[premium-ingest] URL analysis failed for match {match_id}: {type(exc).__name__}: {exc}")
    finally:
        db.close()


@router.post("/matches")
def premium_create_match(
    background_tasks: BackgroundTasks,
    request: Request,
    team_id: int | None = Form(None),
    team_name: str = Form(""),
    opponent: str = Form(...),
    competition: str = Form(""),
    match_date: str = Form(""),
    video_url: str = Form(""),
    video_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    team = _resolve_team(db, user, team_id, team_name)
    opponent = _clean(opponent)
    if not opponent:
        raise HTTPException(status_code=400, detail="Opponent is required.")
    video_url = (video_url or "").strip()
    if video_url and not is_http_url(video_url):
        raise HTTPException(status_code=400, detail="Only http/https video links are supported.")

    video_source = "none"; video_path = ""
    if video_file and video_file.filename:
        video_path = _save_upload(video_file, user.id, team.id); video_source = "upload"
    elif video_url:
        video_source = "youtube" if youtube_embed(video_url) else "url"

    status = "analysis_queued" if video_source == "upload" else "url_analysis_queued" if video_url else "created_no_video"
    match = Match(
        owner_id=user.id, team_id=team.id, opponent=opponent,
        competition=_clean(competition), match_date=_clean(match_date, 32),
        video_source=video_source, video_url=video_url, video_path=video_path, status=status,
    )
    db.add(match); db.commit(); db.refresh(match)

    if video_source == "upload":
        background_tasks.add_task(_run_owned_video, match.id)
    elif video_url:
        background_tasks.add_task(_run_remote_reference, match.id)

    # Compatibility: many internal tools parse the match id from this canonical
    # location. The browser then auto-opens the Ultimate result via premium JS
    # whenever analysis is queued/running/ready.
    return RedirectResponse(f"/matches/{match.id}", status_code=303)