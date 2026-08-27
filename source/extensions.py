import json
from pathlib import Path
from statistics import mean

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db, SessionLocal
from models import (
    User, Match, Player, MediaArtifact, ScoutingTeam, ScoutingPlayer,
    PlayerIntelligenceProfile, PlayerSourceRecord, PlayerMatchMetric, MatchLibraryItem,
)
from intelligence_models import PlayerMatchEvaluation, CoachIntelligenceProfile
from services.ratings import calculate_player_rating
from services.tactical_engine import analyze_match_tactics
from services.video import timestamped_video_url
from services.coach_data import seed_coaches

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _render(request: Request, name: str, **kwargs):
    return TEMPLATES.TemplateResponse(request, name, {"request": request, **kwargs})


def _upsert_evaluation(db: Session, match: Match, player: Player, detail: dict):
    row = db.scalar(select(PlayerMatchEvaluation).where(
        PlayerMatchEvaluation.match_id == match.id,
        PlayerMatchEvaluation.player_id == player.id,
    ))
    if not row:
        row = PlayerMatchEvaluation(match_id=match.id, player_id=player.id)
        db.add(row)
    dims = detail["dimensions"]
    row.overall = detail["overall"]
    row.attack = dims.get("attack") if detail["rated"] else None
    row.defence = dims.get("defence") if detail["rated"] else None
    row.decision = dims.get("decision") if detail["rated"] else None
    row.tactics = dims.get("tactics") if detail["rated"] else None
    row.transition = dims.get("transition") if detail["rated"] else None
    row.discipline = dims.get("discipline") if detail["rated"] else None
    row.technique = dims.get("technique") if detail["rated"] else None
    row.impact = dims.get("impact") if detail["rated"] else None
    row.physical = None
    row.confidence_score = detail["confidence_score"]
    row.confidence_label = detail["confidence_label"]
    row.role_snapshot = player.primary_role or ""
    row.summary = detail["summary"]
    row.strengths_json = json.dumps(detail["strengths"], ensure_ascii=False)
    row.improvements_json = json.dumps(detail["improvements"], ensure_ascii=False)
    row.evidence_json = json.dumps({
        "events": detail["event_counts"],
        "phases": detail["phase_counts"],
        "physical_note": detail["physical_note"],
    }, ensure_ascii=False)
    row.engine_version = detail["engine_version"]
    return row


def _sequence_cards(match: Match, report: dict, artifacts: list[MediaArtifact]):
    cards = []
    for seq in report.get("sequences", []):
        closest = None
        if artifacts:
            candidates = sorted(artifacts, key=lambda a: abs(float(a.second or 0) - float(seq["start"])))
            if candidates and abs(float(candidates[0].second or 0) - float(seq["start"])) <= 10:
                closest = candidates[0]
        open_url = ""
        if closest:
            if closest.external_url:
                open_url = closest.external_url
            elif closest.file_path:
                open_url = f"/matches/{match.id}/evidence/{closest.id}"
        elif match.video_url:
            open_url = timestamped_video_url(match.video_url, seq["start"])
        cards.append({**seq, "artifact": closest, "open_url": open_url})
    return cards


@router.get("/matches/{match_id}/intelligence", response_class=HTMLResponse)
def match_intelligence_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)

    report = analyze_match_tactics(match)
    artifacts = sorted(match.media_artifacts, key=lambda a: float(a.second or 0))
    evaluations = []
    for player in match.team.players:
        events = [e for e in match.events if e.player_id == player.id]
        rating, confidence, evidence = calculate_player_rating(events, role=player.primary_role)
        detail = evidence["__evaluation__"]
        _upsert_evaluation(db, match, player, detail)
        profile = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == player.name))
        evaluations.append({"player": player, "detail": detail, "profile": profile})
    db.commit()

    ranked = [x for x in evaluations if x["detail"]["overall"] is not None]
    ranked.sort(key=lambda x: x["detail"]["overall"], reverse=True)
    top_performers = ranked[:3]
    sequence_cards = _sequence_cards(match, report, artifacts)
    phase_focus = [p for p in report.get("phases", []) if p.get("sequences")]

    return _render(
        request, "match_intelligence.html", user=user, app_name="AquaMetric",
        match=match, report=report, evaluations=evaluations, top_performers=top_performers,
        sequences=sequence_cards, phase_focus=phase_focus, artifacts=artifacts,
    )


@router.get("/intelligence/player")
def player_by_name(request: Request, name: str = Query(...), db: Session = Depends(get_db)):
    _user(request, db)
    profile = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == name.strip()))
    if not profile:
        raise HTTPException(404, detail="Player intelligence profile not found")
    return RedirectResponse(f"/profiles/players/{profile.id}", status_code=303)


@router.get("/profiles/players/{profile_id}", response_class=HTMLResponse)
def unified_player_profile(profile_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    profile = db.get(PlayerIntelligenceProfile, profile_id)
    if not profile:
        raise HTTPException(404)
    sources = db.scalars(select(PlayerSourceRecord).where(PlayerSourceRecord.profile_id == profile.id).order_by(PlayerSourceRecord.observed_at.desc())).all()
    metrics = db.scalars(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id == profile.id).order_by(PlayerMatchMetric.library_match_id.desc().nullslast())).all()
    library_ids = sorted({m.library_match_id for m in metrics if m.library_match_id}, reverse=True)
    library_matches = {mid: db.get(MatchLibraryItem, mid) for mid in library_ids}

    local_players = db.scalars(select(Player).where(Player.name == profile.canonical_name)).all()
    local_ids = [p.id for p in local_players]
    evaluations = []
    if local_ids:
        evaluations = db.scalars(select(PlayerMatchEvaluation).where(PlayerMatchEvaluation.player_id.in_(local_ids)).order_by(PlayerMatchEvaluation.generated_at.desc())).all()
    valid = [e for e in evaluations if e.overall is not None]
    aggregate = round(mean([e.overall for e in valid]), 1) if valid else None
    confidence = round(mean([e.confidence_score for e in valid]), 2) if valid else 0.0

    scout_rows = db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.name == profile.canonical_name)).all()
    return _render(
        request, "unified_player_profile.html", user=user, app_name="AquaMetric", profile=profile,
        sources=sources, metrics=metrics, library_matches=library_matches, evaluations=evaluations,
        aggregate=aggregate, aggregate_confidence=confidence, scout_rows=scout_rows,
    )


@router.get("/coaches", response_class=HTMLResponse)
def coaches_page(request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    coaches = db.scalars(select(CoachIntelligenceProfile).order_by(CoachIntelligenceProfile.team_name, CoachIntelligenceProfile.canonical_name)).all()
    return _render(request, "coaches.html", user=user, app_name="AquaMetric", coaches=coaches)


@router.get("/coach-intelligence/{coach_id}", response_class=HTMLResponse)
def coach_profile_page(coach_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    coach = db.get(CoachIntelligenceProfile, coach_id)
    if not coach:
        raise HTTPException(404)
    dimensions = [
        ("Tactical identity", coach.tactical_score),
        ("Game management", coach.game_management_score),
        ("Special teams", coach.special_teams_score),
        ("Player development", coach.development_score),
    ]
    return _render(request, "coach_intelligence_detail.html", user=user, app_name="AquaMetric", coach=coach, dimensions=dimensions)


@router.get("/api/scouting/{team_id}/coaches")
def scouting_coaches(team_id: int, request: Request, db: Session = Depends(get_db)):
    _user(request, db)
    team = db.get(ScoutingTeam, team_id)
    if not team:
        raise HTTPException(404)
    rows = db.scalars(select(CoachIntelligenceProfile).where(CoachIntelligenceProfile.team_name == team.name).order_by(CoachIntelligenceProfile.season.desc())).all()
    return {
        "team": team.name,
        "coaches": [
            {
                "id": c.id, "name": c.canonical_name, "role": c.role, "season": c.season,
                "status": c.status, "source_tier": c.source_tier, "confidence": c.confidence_score,
                "profile_url": f"/coach-intelligence/{c.id}",
            }
            for c in rows
        ],
    }


def install_extensions(app):
    """Install V12 routes and seed evidence-backed coach records.

    FastAPI's router include is the normal path. The explicit route registration
    below is an idempotent fallback: it guarantees the four public V12 pages and
    helper/API endpoints are present even if a host/import sequence leaves the
    APIRouter detached. Existing paths are never duplicated.
    """
    db = SessionLocal()
    try:
        seed_coaches(db)
    finally:
        db.close()

    app.include_router(router)
    existing = {getattr(route, "path", None) for route in app.routes}
    registrations = [
        ("/matches/{match_id}/intelligence", match_intelligence_page, HTMLResponse),
        ("/intelligence/player", player_by_name, None),
        ("/profiles/players/{profile_id}", unified_player_profile, HTMLResponse),
        ("/coaches", coaches_page, HTMLResponse),
        ("/coach-intelligence/{coach_id}", coach_profile_page, HTMLResponse),
        ("/api/scouting/{team_id}/coaches", scouting_coaches, None),
    ]
    for path, endpoint, response_class in registrations:
        if path in existing:
            continue
        kwargs = {"methods": ["GET"]}
        if response_class is not None:
            kwargs["response_class"] = response_class
        app.add_api_route(path, endpoint, **kwargs)
        existing.add(path)
