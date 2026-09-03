from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import AnalysisJob, Match, User
from services.performance_intelligence import team_performance_report
from services.ultimate_analytics import ultimate_event_report, ultimate_match_report
from services.video import youtube_embed

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


@router.post("/matches/{match_id}/url-analysis/start")
def start_url_analysis(match_id: int, request: Request, db: Session = Depends(get_db)):
    """Generate the complete Ultimate Analyst result shell for a remote URL.

    Third-party video is never copied. The result is populated immediately from
    every verified event already attached to the match, while unsupported metrics
    remain explicitly unavailable instead of being fabricated.
    """
    user = _user(request, db)
    match = _match(match_id, user, db)

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
        job = existing
    else:
        job = AnalysisJob(
            match_id=match.id,
            stage="ultimate_url_analysis",
            progress=100,
            status="framework_ready",
            message=message,
        )
        db.add(job)
    match.status = "url_analysis_ready"
    db.commit()
    return RedirectResponse(f"/matches/{match.id}/url-analysis", status_code=303)


@router.get("/matches/{match_id}/url-analysis", response_class=HTMLResponse)
def url_analysis_result(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    match = _match(match_id, user, db)
    ultimate = ultimate_match_report(match)
    performance = team_performance_report(match)
    player_rows = []
    for player in match.team.players:
        events = [e for e in match.events if e.player_id == player.id]
        player_rows.append({
            "player": player,
            "report": ultimate_event_report(events, "all"),
        })

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
        request,
        "url_analysis.html",
        {
            "request": request,
            "app_name": "AquaMetric",
            "user": user,
            "match": match,
            "embed": youtube_embed(match.video_url),
            "ultimate": ultimate,
            "performance": performance,
            "player_rows": player_rows,
            "minimum_contract": minimum_contract,
            "quick_event_types": QUICK_EVENT_TYPES,
            "job": job,
        },
    )
