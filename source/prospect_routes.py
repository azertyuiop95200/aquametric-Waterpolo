from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import PlayerIntelligenceProfile, ScoutingPlayer, ScoutingTeam, User
from services.deep_scouting_review import enrich_with_deep_review
from services.game_reading import add_game_reading_score
from services.prospect_ratings import _band, build_prospect_evaluation, eu_youth_prospect_rows

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _jsonable(row):
    return {key: value for key, value in row.items() if key != "public_summary"}


def _enrich(row):
    row = enrich_with_deep_review(row)
    row["band"] = _band(row.get("overall"))
    row = add_game_reading_score(row)
    return row


def _deep_rows(db: Session, user_id: int):
    rows = [_enrich(row) for row in eu_youth_prospect_rows(db, user_id)]
    rows.sort(
        key=lambda row: (
            row.get("overall") is not None,
            row.get("overall") or 0,
            row.get("confidence_score") or 0,
        ),
        reverse=True,
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


@router.get("/api/scouting/eu-youth-ranking")
def eu_youth_ranking(
    request: Request,
    age: str = Query("all"),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    rows = _deep_rows(db, user.id)
    normalized_age = age.upper()
    if normalized_age in {"U16", "U18", "U20"}:
        rows = [row for row in rows if normalized_age in row["age_groups"]]
        for idx, row in enumerate(rows, start=1):
            row["rank"] = idx
    return {
        "age": normalized_age if normalized_age in {"U16", "U18", "U20"} else "all",
        "engine_version": "prospect-rating-v4.2-game-reading",
        "count": len(rows),
        "players": [_jsonable(row) for row in rows],
        "policy": {
            "video": "Linked official videos are review material only. They affect the score only when AquaMetric has player-attributed/tagged match evidence.",
            "play_by_play": "Detailed official match reports may add a low-weight tactical signal (15%) for explicitly described actions.",
            "game_reading": "Game-reading is a separate /100 grade built from evidence-bound decision, tactics, anticipation/transition, impact and role-specific defensive signals; weak samples are shrunk toward neutral.",
            "physical": "Physical output is not scored without calibrated tracking.",
        },
    }


@router.get("/api/prospects/{profile_id}")
def prospect_api(profile_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    profile = db.get(PlayerIntelligenceProfile, profile_id)
    if not profile:
        raise HTTPException(404, detail="Player profile not found")
    scout_rows = db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.name == profile.canonical_name)).all()
    evaluation = build_prospect_evaluation(db, profile, scout_rows, user.id)
    if not evaluation:
        raise HTTPException(404, detail="EU youth prospect evaluation not available")
    evaluation = _enrich(evaluation)
    return _jsonable(evaluation)


@router.get("/prospects/{profile_id}", response_class=HTMLResponse)
def prospect_detail(profile_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    profile = db.get(PlayerIntelligenceProfile, profile_id)
    if not profile:
        raise HTTPException(404, detail="Player profile not found")
    scout_rows = db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.name == profile.canonical_name)).all()
    evaluation = build_prospect_evaluation(db, profile, scout_rows, user.id)
    if not evaluation:
        raise HTTPException(404, detail="EU youth prospect evaluation not available")
    evaluation = _enrich(evaluation)
    ranking = _deep_rows(db, user.id)
    rank = next((row["rank"] for row in ranking if row["profile_id"] == profile.id), None)
    evaluation["rank"] = rank
    return TEMPLATES.TemplateResponse(
        request,
        "prospect_detail.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "profile": profile,
            "evaluation": evaluation,
        },
    )


def install_prospect_routes_patch():
    """Wrap the existing extension installer so prospect routes are registered once."""
    import extensions

    if getattr(extensions.install_extensions, "_prospect_v4_patch", False):
        return
    original = extensions.install_extensions

    def install_with_prospects(app):
        original(app)
        existing = {getattr(route, "path", None) for route in app.routes}
        if "/api/scouting/eu-youth-ranking" not in existing:
            app.include_router(router)

    install_with_prospects._prospect_v4_patch = True
    extensions.install_extensions = install_with_prospects
