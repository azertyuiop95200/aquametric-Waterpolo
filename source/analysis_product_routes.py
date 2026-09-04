from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_db
from models import Club, Match, Team, User
from services.analysis_product import (
    analysis_snapshot,
    build_analysis_zip,
    build_exact_evidence_pack,
    run_product_analysis,
)
from services.deep_analysis_sequences import (
    append_sequence_manifest,
    materialize_deep_sequence_pack,
    sequence_gallery,
    sequence_summary,
)
from services.rapid_match_analysis import RapidAnalysisError
from services.video import is_http_url, youtube_embed
from analysis_library_product_routes import router as analysis_library_product_router

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", BASE_DIR / "evidence"))
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()
router.include_router(analysis_library_product_router)


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _owned_match(match_id: int, request: Request, db: Session):
    user = _user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Match not found")
    return user, match


def _url_team(db: Session, user: User, team_name: str, competition: str) -> Team:
    name = (team_name or "").strip()[:160]
    if not name:
        raise HTTPException(status_code=400, detail="Team is required.")
    team = db.scalar(select(Team).where(Team.owner_id == user.id, func.lower(Team.name) == name.lower()))
    if team:
        return team
    club = db.scalar(select(Club).where(Club.owner_id == user.id, func.lower(Club.name) == name.lower()))
    if not club:
        club = Club(
            name=name, country="Analysis", division=(competition or "Video analysis")[:120],
            category="Women", owner_id=user.id,
        )
        db.add(club)
        db.flush()
    team = Team(name=name, club_id=club.id, owner_id=user.id, category="Women")
    db.add(team)
    db.flush()
    return team


def _template_side(report: dict) -> dict:
    view = dict(report)
    view["phases"] = {"rows": list(report.get("phases", []) or [])}
    possessions = dict(report.get("possessions", {}) or {})
    if not possessions.get("available"):
        possessions["reason"] = possessions.get("note") or "Les identifiants de possession manquent encore."
    view["possessions"] = possessions
    return view


def _zip_root(match: Match) -> str:
    def slug(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("_")
        return value[:80] or "match"
    return f"AquaMetric_{slug(match.team.name)}_vs_{slug(match.opponent)}_{match.id}"


@router.post("/analysis/url/create")
def create_real_url_analysis(
    request: Request,
    team_name: str = Form(""),
    opponent: str = Form(...),
    competition: str = Form(""),
    match_date: str = Form(""),
    video_url: str = Form(...),
    db: Session = Depends(get_db),
):
    """Create a URL match and immediately build the real available result, not a framework page."""
    user = _user(request, db)
    video_url = (video_url or "").strip()
    if not video_url or not is_http_url(video_url):
        raise HTTPException(status_code=400, detail="A valid http/https video URL is required.")
    opponent = (opponent or "").strip()[:160]
    if not opponent:
        raise HTTPException(status_code=400, detail="Opponent is required.")
    team = _url_team(db, user, team_name, competition)
    match = Match(
        owner_id=user.id, team_id=team.id, opponent=opponent,
        competition=(competition or "")[:160], match_date=(match_date or "")[:32],
        video_source="youtube" if youtube_embed(video_url) else "url",
        video_url=video_url, video_path="", status="url_analysis_created",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    run_product_analysis(db, match, UPLOAD_DIR, EVIDENCE_DIR)
    materialize_deep_sequence_pack(
        db, match, UPLOAD_DIR, EVIDENCE_DIR,
        max_targets=72, max_clips=0, max_image_targets=0,
    )
    return RedirectResponse(f"/matches/{match.id}/analysis/result", status_code=303)


@router.post("/matches/{match_id}/analysis/start")
def start_real_analysis(
    match_id: int,
    request: Request,
    include_audio: str = Form(""),
    db: Session = Depends(get_db),
):
    """Run the actual analysis pipeline and materialize a dense first sequence pack."""
    _, match = _owned_match(match_id, request, db)
    try:
        run_product_analysis(
            db,
            match,
            UPLOAD_DIR,
            EVIDENCE_DIR,
            include_audio=include_audio.lower() in {"1", "true", "on", "yes"},
        )
        materialize_deep_sequence_pack(
            db, match, UPLOAD_DIR, EVIDENCE_DIR,
            max_targets=72, max_clips=24, max_image_targets=48, triple_frames=18,
        )
    except RapidAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RedirectResponse(f"/matches/{match_id}/analysis/result", status_code=303)


@router.post("/matches/{match_id}/url-analysis/start")
def start_real_url_analysis(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    if not match.video_url:
        raise HTTPException(status_code=400, detail="This analysis mode requires a video URL.")
    run_product_analysis(db, match, UPLOAD_DIR, EVIDENCE_DIR)
    materialize_deep_sequence_pack(
        db, match, UPLOAD_DIR, EVIDENCE_DIR,
        max_targets=72, max_clips=0, max_image_targets=0,
    )
    return RedirectResponse(f"/matches/{match_id}/analysis/result", status_code=303)


@router.get("/matches/{match_id}/analysis/result", response_class=HTMLResponse)
def analysis_result(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    snapshot = analysis_snapshot(db, match)
    team_report = _template_side(snapshot["ultimate"]["team"])
    opponent_report = _template_side(snapshot["ultimate"]["opponent"])
    sequences = sequence_gallery(db, match, max_total=72)
    summary = sequence_summary(sequences)
    source_embed = youtube_embed(match.video_url) if match.video_url else ""
    if not source_embed and snapshot.get("reference") and snapshot["reference"].get("video_url"):
        source_embed = youtube_embed(snapshot["reference"]["video_url"]) or ""
    return TEMPLATES.TemplateResponse(
        request,
        "analysis_result.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "match": match,
            "snapshot": snapshot,
            "ultimate": snapshot["ultimate"],
            "team_report": team_report,
            "opponent_report": opponent_report,
            "automatic": snapshot["automatic"],
            "vision": snapshot["vision"],
            "reference": snapshot["reference"],
            "artifacts": snapshot["artifacts"],
            "verified_events": snapshot["verified_events"],
            "sequences": sequences,
            "sequence_summary": summary,
            "source_embed": source_embed,
        },
    )


@router.post("/matches/{match_id}/analysis/evidence-pack")
def regenerate_exact_evidence(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    build_exact_evidence_pack(
        db, match, UPLOAD_DIR, EVIDENCE_DIR,
        max_verified_events=32, max_candidates=24,
    )
    materialize_deep_sequence_pack(
        db, match, UPLOAD_DIR, EVIDENCE_DIR,
        max_targets=72, max_clips=48, max_image_targets=72, triple_frames=30,
    )
    return RedirectResponse(f"/matches/{match_id}/analysis/result#sequences", status_code=303)


@router.get("/matches/{match_id}/analysis/export.zip")
def export_complete_analysis(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    # The ZIP request is the maximum-materialization pass: create as many exact local
    # clips as the bounded sequence catalogue allows before archiving everything.
    materialize_deep_sequence_pack(
        db, match, UPLOAD_DIR, EVIDENCE_DIR,
        max_targets=72, max_clips=64, max_image_targets=72, triple_frames=36,
    )
    archive = build_analysis_zip(db, match, EVIDENCE_DIR)
    cards = sequence_gallery(db, match, max_total=72)
    append_sequence_manifest(archive, cards, _zip_root(match))
    filename = f"AquaMetric_match_{match.id}_analysis.zip"
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
