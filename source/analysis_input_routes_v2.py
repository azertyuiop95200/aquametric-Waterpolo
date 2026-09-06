"""Flexible match creation for analysis.

Analysis must not depend on a pre-seeded AquaMetric team catalogue. A coach can
enter any two team names, choose men/women/mixed, and optionally restrict a long
video to one match window. URL and uploaded-video creation share the same rules.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_db
from models import Club, Match, Team
from analysis_product_routes import UPLOAD_DIR, _user
from services.video import is_http_url, youtube_embed

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".ogv", ".ogg"}


def _category(value: str) -> str:
    token = (value or "").strip().lower()
    if token in {"women", "woman", "female", "f", "feminin", "féminin", "feminine", "féminine"}:
        return "Women"
    if token in {"men", "man", "male", "m", "masculin", "masculine"}:
        return "Men"
    return "Mixed/Other"


def _free_team(db: Session, user, name: str, competition: str, category: str) -> Team:
    clean = (name or "").strip()[:160]
    if not clean:
        raise HTTPException(status_code=400, detail="Le nom de l'équipe est obligatoire.")
    cat = _category(category)
    team = db.scalar(
        select(Team).where(
            Team.owner_id == user.id,
            func.lower(Team.name) == clean.lower(),
        )
    )
    if team:
        # Do not silently overwrite a known category, but fill an unspecified one.
        if not (team.category or "").strip():
            team.category = cat
        return team
    club = db.scalar(
        select(Club).where(
            Club.owner_id == user.id,
            func.lower(Club.name) == clean.lower(),
        )
    )
    if not club:
        club = Club(
            name=clean,
            country="Analysis",
            division=(competition or "Video analysis")[:120],
            category=cat,
            owner_id=user.id,
        )
        db.add(club)
        db.flush()
    team = Team(name=clean, club_id=club.id, owner_id=user.id, category=cat)
    db.add(team)
    db.flush()
    return team


def _scope_query(scope_mode: str, scope_start_second: float, scope_end_second: float) -> str:
    mode = (scope_mode or "auto").strip().lower()
    if mode not in {"auto", "single", "manual", "multiple"}:
        mode = "auto"
    start = max(0.0, float(scope_start_second or 0.0))
    end = max(0.0, float(scope_end_second or 0.0))
    if end and end <= start:
        end = 0.0
    return urlencode({"scope_mode": mode, "scope_start": f"{start:.3f}", "scope_end": f"{end:.3f}"})


def create_flexible_url_analysis(
    request: Request,
    team_name: str = Form(""),
    opponent: str = Form(...),
    category: str = Form("Women"),
    competition: str = Form(""),
    match_date: str = Form(""),
    video_url: str = Form(...),
    scope_mode: str = Form("auto"),
    scope_start_second: float = Form(0.0),
    scope_end_second: float = Form(0.0),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    url = (video_url or "").strip()
    if not url or not is_http_url(url):
        raise HTTPException(status_code=400, detail="Un lien vidéo http/https valide est obligatoire.")
    opponent = (opponent or "").strip()[:160]
    if not opponent:
        raise HTTPException(status_code=400, detail="Le nom de l'adversaire est obligatoire.")
    team = _free_team(db, user, team_name, competition, category)
    match = Match(
        owner_id=user.id,
        team_id=team.id,
        opponent=opponent,
        competition=(competition or "")[:160],
        match_date=(match_date or "")[:32],
        video_source="youtube" if youtube_embed(url) else "url",
        video_url=url,
        video_path="",
        status="url_capture_required",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    query = _scope_query(scope_mode, scope_start_second, scope_end_second)
    return RedirectResponse(f"/matches/{match.id}/analysis/browser-capture?{query}", status_code=303)


def _save_upload(upload: UploadFile, user_id: int, team_id: int) -> str:
    original = Path(upload.filename or "video").name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Format vidéo non pris en charge.")
    if upload.content_type and not (
        upload.content_type.startswith("video/") or upload.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Le fichier importé n'est pas reconnu comme une vidéo.")
    safe = f"u{int(user_id)}_t{int(team_id)}_{uuid.uuid4().hex}{suffix}"
    target = UPLOAD_DIR / safe
    target.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with target.open("wb") as out:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"La vidéo dépasse {MAX_UPLOAD_MB} MB.")
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        upload.file.close()
    if total <= 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="La vidéo importée est vide.")
    return safe


def create_flexible_uploaded_match(
    request: Request,
    team_name: str = Form(""),
    opponent: str = Form(...),
    category: str = Form("Women"),
    competition: str = Form(""),
    match_date: str = Form(""),
    video_url: str = Form(""),
    video_file: UploadFile | None = File(None),
    scope_mode: str = Form("single"),
    scope_start_second: float = Form(0.0),
    scope_end_second: float = Form(0.0),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    opponent = (opponent or "").strip()[:160]
    if not opponent:
        raise HTTPException(status_code=400, detail="Le nom de l'adversaire est obligatoire.")
    team = _free_team(db, user, team_name, competition, category)
    if video_file and video_file.filename:
        stored = _save_upload(video_file, user.id, team.id)
        source = "upload"
        url = ""
    else:
        url = (video_url or "").strip()
        if not url or not is_http_url(url):
            raise HTTPException(status_code=400, detail="Importe une vidéo ou fournis une URL valide.")
        stored = ""
        source = "youtube" if youtube_embed(url) else "url"
    match = Match(
        owner_id=user.id,
        team_id=team.id,
        opponent=opponent,
        competition=(competition or "")[:160],
        match_date=(match_date or "")[:32],
        video_source=source,
        video_url=url,
        video_path=stored,
        status="uploaded_ready" if source == "upload" else "url_capture_required",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    if source == "upload":
        return RedirectResponse(f"/matches/{match.id}/analysis/result", status_code=303)
    query = _scope_query(scope_mode, scope_start_second, scope_end_second)
    return RedirectResponse(f"/matches/{match.id}/analysis/browser-capture?{query}", status_code=303)
