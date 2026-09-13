from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_db
from models import AnalysisJob, Club, Event, EventContext, Match, Player, Team, User
from services.performance_intelligence import team_performance_report
from services.ultimate_analytics import ultimate_event_report, ultimate_match_report
from services.video import is_http_url, youtube_embed

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()

QUICK_EVENT_TYPES = (
    "goal", "shot_on_target", "shot_off_target", "shot_blocked",
    "pass_complete", "assist", "key_pass", "bad_pass", "turnover",
    "interception", "recovery", "block", "save", "duel_won", "duel_lost",
    "centre_touch", "exclusion_earned", "exclusion_committed",
    "counterattack_start", "defensive_recovery_start", "fast_recovery", "late_recovery",
)
VALID_PERSPECTIVES = {"for", "against", "neutral"}
VALID_PHASES = {"auto", "even_attack", "even_defence", "power_play", "penalty_kill", "counterattack", "defensive_recovery", "centre_play", "restart"}


def _user(request: Request, db: Session) -> User:
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _match(match_id: int, user: User, db: Session) -> Match:
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    if not match.video_url:
        raise HTTPException(400, detail="This analysis mode requires a video URL.")
    return match


def _analysis_team(db: Session, user: User, team_name: str, competition: str = "") -> Team:
    name = (team_name or "").strip()[:160]
    if not name:
        raise HTTPException(400, detail="Team is required.")
    team = db.scalar(select(Team).where(Team.owner_id == user.id, func.lower(Team.name) == name.lower()))
    if team:
        return team
    club = db.scalar(select(Club).where(Club.owner_id == user.id, func.lower(Club.name) == name.lower()))
    if not club:
        club = Club(name=name, country="Analysis", division=(competition or "Video analysis")[:120], category="Women", owner_id=user.id)
        db.add(club)
        db.flush()
    team = Team(name=name, club_id=club.id, owner_id=user.id, category="Women")
    db.add(team)
    db.flush()
    return team


def _mark_framework_ready(match: Match, db: Session) -> AnalysisJob:
    existing = db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.match_id == match.id, AnalysisJob.stage == "ultimate_url_analysis")
        .order_by(AnalysisJob.id.desc())
    )
    message = (
        "Ultimate URL analysis framework generated. All verified tags feed the same team, player, "
        "possession, shot, pass, turnover, phase, pressure, decision and transition reports as an upload. "
        "Third-party pixels are not copied or treated as automatically observed evidence."
    )
    if existing:
        existing.status = "framework_ready"
        existing.progress = 100
        existing.message = message
        return existing
    job = AnalysisJob(match_id=match.id, stage="ultimate_url_analysis", progress=100, status="framework_ready", message=message)
    db.add(job)
    return job


def _tag(parts: list[str], key: str, value: str):
    value = (value or "").strip()
    if value:
        parts.append(f"{key}={value[:60]}")


@router.post("/analysis/url/create")
def create_url_analysis(
    request: Request,
    team_name: str = Form(""),
    opponent: str = Form(...),
    competition: str = Form(""),
    match_date: str = Form(""),
    video_url: str = Form(...),
    db: Session = Depends(get_db),
):
    """One-click 'analyze from URL' path from the new-match form."""
    user = _user(request, db)
    video_url = (video_url or "").strip()
    if not video_url or not is_http_url(video_url):
        raise HTTPException(400, detail="A valid http/https video URL is required.")
    team = _analysis_team(db, user, team_name, competition)
    opponent = (opponent or "").strip()[:160]
    if not opponent:
        raise HTTPException(400, detail="Opponent is required.")
    match = Match(
        owner_id=user.id, team_id=team.id, opponent=opponent,
        competition=(competition or "")[:160], match_date=(match_date or "")[:32],
        video_source="youtube" if youtube_embed(video_url) else "url",
        video_url=video_url, video_path="", status="url_analysis_ready",
    )
    db.add(match)
    db.flush()
    _mark_framework_ready(match, db)
    db.commit()
    return RedirectResponse(f"/matches/{match.id}/url-analysis", status_code=303)


@router.post("/matches/{match_id}/url-analysis/start")
def start_url_analysis(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    match = _match(match_id, user, db)
    _mark_framework_ready(match, db)
    match.status = "url_analysis_ready"
    db.commit()
    return RedirectResponse(f"/matches/{match.id}/url-analysis", status_code=303)


@router.post("/matches/{match_id}/url-analysis/events")
def add_url_analysis_event(
    match_id: int,
    request: Request,
    second: float = Form(0),
    event_type: str = Form(...),
    player_id: str = Form(""),
    perspective: str = Form("for"),
    phase_tag: str = Form("auto"),
    period: str = Form(""),
    possession: str = Form(""),
    zone: str = Form(""),
    pressure: str = Form(""),
    decision: str = Form(""),
    cause: str = Form(""),
    pass_type: str = Form(""),
    shot_type: str = Form(""),
    hand: str = Form(""),
    distance_m: str = Form(""),
    shot_speed_kmh: str = Form(""),
    release_time_s: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    match = _match(match_id, user, db)
    if event_type not in QUICK_EVENT_TYPES:
        raise HTTPException(400, detail="Unsupported URL review event type.")
    if second < 0 or second > 12 * 60 * 60:
        raise HTTPException(400, detail="Event time is outside the supported range.")
    pid = None
    if player_id:
        if not player_id.isdigit():
            raise HTTPException(400, detail="Invalid player.")
        player = db.get(Player, int(player_id))
        if not player or player.team_id != match.team_id:
            raise HTTPException(400, detail="Player does not belong to this match team.")
        pid = player.id
    perspective = perspective if perspective in VALID_PERSPECTIVES else "neutral"
    phase_tag = phase_tag if phase_tag in VALID_PHASES else "auto"

    parts: list[str] = []
    for key, value in (
        ("period", period), ("possession", possession), ("zone", zone), ("pressure", pressure),
        ("decision", decision), ("cause", cause), ("pass_type", pass_type), ("shot_type", shot_type),
        ("hand", hand), ("distance_m", distance_m), ("shot_speed_kmh", shot_speed_kmh), ("release_time_s", release_time_s),
    ):
        _tag(parts, key, value)
    event = Event(
        match_id=match.id, player_id=pid, second=second, event_type=event_type,
        confidence="CONFIRMED", note=" ".join(parts)[:500], source="manual_url_review",
    )
    db.add(event)
    db.flush()
    db.add(EventContext(event_id=event.id, perspective=perspective, phase_tag=phase_tag, quality_tag=decision[:40]))
    db.commit()
    return RedirectResponse(f"/matches/{match.id}/url-analysis#team-results", status_code=303)


@router.get("/matches/{match_id}/url-analysis", response_class=HTMLResponse)
def url_analysis_result(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    match = _match(match_id, user, db)
    ultimate = ultimate_match_report(match)
    performance = team_performance_report(match)
    player_rows = []
    for player in match.team.players:
        events = [e for e in match.events if e.player_id == player.id]
        player_rows.append({"player": player, "report": ultimate_event_report(events, "all")})

    job = db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.match_id == match.id, AnalysisJob.stage == "ultimate_url_analysis")
        .order_by(AnalysisJob.id.desc())
    )
    team = ultimate["team"]
    minimum_contract = [
        {"key": "shots", "label": "Tirs", "detail": "cadrés · non cadrés · bloqués · buts · précision · efficacité", "available": team["basic"]["shots"] > 0},
        {"key": "passes", "label": "Passes", "detail": "réussies · ratées · % · types · pression · décision", "available": team["basic"]["pass_attempts"] > 0},
        {"key": "losses", "label": "Possession / pertes", "detail": "turnovers · cause · zone · phase · pression · % par cause", "available": team["losses"]["total"] > 0},
        {"key": "possessions", "label": "Possessions", "detail": "but/possession · tir/possession · perte/possession · durée observée", "available": bool(team["possessions"].get("available"))},
        {"key": "transition", "label": "Transitions", "detail": "D→A première passe/tir · A→D reconstruction · sprint si mesuré", "available": any(performance["transition_timing"]["samples"].values())},
        {"key": "periods", "label": "Quarts / phases", "detail": "Q1–Q4 · 6v6 · 6v5 · 5v6 · contre · repli · centre", "available": bool(team["periods"]["rows"] or team["phases"])},
        {"key": "decision", "label": "Décision / pression", "detail": "good/neutral/poor · faible/moyenne/forte · impact sur passe/tir/perte", "available": bool(team["decisions"]["total"] or team["pressure"]["tagged"])},
        {"key": "players", "label": "Joueuses / postes", "detail": "mêmes métriques individuellement + lecture qualitative par poste", "available": any(row["report"]["basic"]["events"] for row in player_rows)},
    ]

    return TEMPLATES.TemplateResponse(
        request, "url_analysis.html",
        {"request": request, "app_name": "AquaMetric", "user": user, "match": match,
         "embed": youtube_embed(match.video_url), "ultimate": ultimate, "performance": performance,
         "player_rows": player_rows, "minimum_contract": minimum_contract,
         "quick_event_types": QUICK_EVENT_TYPES, "job": job},
    )
