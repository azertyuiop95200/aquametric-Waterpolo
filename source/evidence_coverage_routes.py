from pathlib import Path

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import User, ScoutingTeam, OfficialFixture
from services.team_evidence_coverage import team_evidence_coverage, coverage_totals
from services.scouting_player_resources import scouting_player_resources, scouting_team_resource_summary
from analysis_match_routes import router as analysis_match_router
from analysis_library_routes_v2 import router as analysis_library_router

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


@router.get("/evidence-coverage", response_class=HTMLResponse)
def evidence_coverage_page(request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    rows = team_evidence_coverage(db)
    totals = coverage_totals(rows)
    return TEMPLATES.TemplateResponse(
        request,
        "evidence_coverage.html",
        {"request": request, "user": user, "app_name": "AquaMetric", "rows": rows, "totals": totals},
    )


@router.get("/api/evidence-coverage")
def evidence_coverage_api(request: Request, db: Session = Depends(get_db)):
    _user(request, db)
    rows = team_evidence_coverage(db)
    return {
        "totals": coverage_totals(rows),
        "teams": [
            {
                "id": r["team"].id,
                "name": r["team"].name,
                "team_type": r["team"].team_type,
                "country": r["team"].country,
                "competition": r["team"].competition,
                "season": r["team"].season_label,
                "age_group": r["team"].age_group,
                "roster_status": r["team"].roster_status,
                "state": r["state"],
                "coverage_score": r["coverage_score"],
                "roster_players": r["roster_players"],
                "evidence_players": r["evidence_players"],
                "performance_players": r["performance_players"],
                "documented_matches": r["documented_matches"],
                "performance_matches": r["performance_matches"],
                "lineup_only_matches": r["lineup_only_matches"],
                "missing_player_evidence": r["missing_player_evidence"],
                "evidence_seasons": r["evidence_seasons"],
            }
            for r in rows
        ],
    }


@router.get("/scouting/{team_id}", response_class=HTMLResponse)
def enriched_scouting_detail(team_id: int, request: Request, db: Session = Depends(get_db)):
    """Resource-rich Scouting dossier registered before main.py's legacy route.

    The roster stays evidence-first, but every player card now reuses the same
    canonical profile, match metrics, sources, shot observations and transfer
    evidence that feed the unified player dossier.
    """
    user = _user(request, db)
    team = db.get(ScoutingTeam, team_id)
    if not team:
        raise HTTPException(404, detail="Scouting team not found")

    players = scouting_player_resources(db, team.id)
    resource_summary = scouting_team_resource_summary(players)
    fixtures = []
    if team.team_type == "club":
        team_token = team.name.split(" — ")[0]
        fixtures = db.scalars(
            select(OfficialFixture)
            .where(
                OfficialFixture.season == "2026-2027",
                OfficialFixture.competition == "Elite Féminine",
                (OfficialFixture.home_team.contains(team_token)) | (OfficialFixture.away_team.contains(team_token)),
            )
            .order_by(OfficialFixture.start_text)
        ).all()

    return TEMPLATES.TemplateResponse(
        request,
        "scouting_detail.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "scout_team": team,
            "players": players,
            "resource_summary": resource_summary,
            "fixtures": fixtures,
        },
    )


# Install enriched routes before main.py's legacy routes. FastAPI resolves the
# first matching route, so the operational match library keeps private workspace
# analysis + official evidence while the universal match-analysis routes stay
# available to the full AquaMetric team catalogue.
router.include_router(analysis_library_router)
router.include_router(analysis_match_router)
