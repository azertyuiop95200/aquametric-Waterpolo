from __future__ import annotations

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import User, OfficialStanding, OfficialTeamStat, OfficialDataSource
from scorer_models import OfficialScorerStanding  # registers scorer table before Base.metadata.create_all
from services.scorer_rankings import build_scorer_groups

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


@router.get("/competitions", response_class=HTMLResponse)
def competitions_with_scorers(request: Request, db: Session = Depends(get_db)):
    """Upgrade the Results/Classifications screen with multi-season scorer rankings.

    This router is registered before main.py declares the legacy /competitions route, so
    FastAPI resolves this implementation first while preserving the original URL.
    """
    user = _user(request, db)
    standings = db.scalars(
        select(OfficialStanding)
        .order_by(OfficialStanding.competition, OfficialStanding.season.desc(), OfficialStanding.position)
        .limit(1000)
    ).all()
    team_stats = db.scalars(
        select(OfficialTeamStat)
        .order_by(OfficialTeamStat.competition, OfficialTeamStat.team_name, OfficialTeamStat.metric)
        .limit(7500)
    ).all()
    sources = db.scalars(select(OfficialDataSource).order_by(OfficialDataSource.region, OfficialDataSource.name)).all()

    competitions = {}
    for row in standings:
        competitions.setdefault((row.competition, row.season, row.category), []).append(row)
    stats_by_competition = {}
    for row in team_stats:
        stats_by_competition.setdefault(row.competition, {}).setdefault(row.team_name, {})[row.metric] = row.value

    scorer_data = build_scorer_groups(db)
    return TEMPLATES.TemplateResponse(request, "competitions.html", {
        "request": request,
        "user": user,
        "app_name": "AquaMetric",
        "competitions": competitions,
        "stats_by_competition": stats_by_competition,
        "sources": sources,
        "scorer_groups": scorer_data["groups"],
        "scorer_seasons": scorer_data["seasons"],
        "scorer_current_season": scorer_data["current_season"],
        "scorer_policy": scorer_data["policy"],
    })


@router.get("/api/scorers")
def scorer_rankings_api(request: Request, db: Session = Depends(get_db)):
    _user(request, db)
    payload = build_scorer_groups(db)
    # Keep the API JSON-safe and compact. Datetime source metadata is intentionally not
    # exposed here; source URLs/quality remain available inside each row.
    return payload
