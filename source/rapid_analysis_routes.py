"""Operational match-analysis library and rapid long-video workflow."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import get_db
from models import (
    User, Match, Event, AnalysisJob, MediaArtifact, VisionAnalysis, AutonomousAnalysis,
    AutonomousEventCandidate, MatchLibraryItem, LibraryPlayerMatchStat,
)
from services.match_statistics import build_match_statistics, reference_player_stat_payload
from services.rapid_match_analysis import run_rapid_analysis, RapidAnalysisError
from services.tactical_engine import analyze_match_tactics
from services.ratings import calculate_player_rating
from services.scoreboard_ocr import tesseract_available
from services.video import youtube_embed
from analysis_library_routes_v2 import _quarter_review

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", BASE_DIR / "evidence"))
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _json(value: str, fallback):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def _latest(db: Session, model, match_id: int, date_field):
    return db.scalar(
        select(model)
        .where(model.match_id == match_id)
        .order_by(date_field.desc(), model.id.desc())
    )


@router.get("/analysis-library", response_class=HTMLResponse)
def operational_analysis_library(
    request: Request,
    competition: str = "",
    team: str = "",
    db: Session = Depends(get_db),
):
    """Compatibility route: the Ultimate product owns the library presentation.

    Some nested FastAPI routers still reach this historical endpoint before a
    direct app route. Delegating here guarantees the same evidence-rich context
    and template regardless of which compatible route FastAPI resolves first.
    """
    from analysis_library_product_routes import ultimate_analysis_library

    return ultimate_analysis_library(request=request, competition=competition, team=team, db=db)


@router.get("/analysis-library/{item_id}", response_class=HTMLResponse)
def operational_reference_detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    """Compatibility route for old library detail links."""
    from analysis_library_product_routes import published_ultimate_detail

    return published_ultimate_detail(item_id=item_id, request=request, db=db)


@router.get("/match-analysis/{match_id}", response_class=HTMLResponse)
def match_analysis_workspace(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    latest_job = _latest(db, AnalysisJob, match.id, AnalysisJob.created_at)
    latest_vision = _latest(db, VisionAnalysis, match.id, VisionAnalysis.created_at)
    latest_auto = _latest(db, AutonomousAnalysis, match.id, AutonomousAnalysis.created_at)
    candidates = []
    auto_summary = {}
    auto_limitations = []
    periods = []
    if latest_auto:
        candidates = db.scalars(
            select(AutonomousEventCandidate)
            .where(AutonomousEventCandidate.analysis_id == latest_auto.id)
            .order_by(AutonomousEventCandidate.second)
        ).all()
        auto_summary = _json(latest_auto.summary_json, {})
        auto_limitations = _json(latest_auto.limitations_json, [])
        periods = _json(latest_auto.periods_json, [])

    statistics = build_match_statistics(match)
    player_evaluations = []
    for player in match.team.players:
        pevents = [e for e in match.events if e.player_id == player.id]
        rating, confidence, evidence = calculate_player_rating(pevents, role=player.primary_role)
        detail = evidence.get("__evaluation__", {})
        player_evaluations.append({
            "player": player, "rating": rating, "confidence": confidence,
            "detail": detail, "events": len(pevents),
        })
    player_evaluations.sort(key=lambda x: (x["rating"] is None, -(x["rating"] or 0), x["player"].name))

    return TEMPLATES.TemplateResponse(request, "match_analysis_workspace.html", {
        "request": request, "user": user, "app_name": "AquaMetric",
        "match": match, "statistics": statistics, "job": latest_job,
        "vision": latest_vision, "auto": latest_auto, "auto_summary": auto_summary,
        "auto_limitations": auto_limitations, "periods": periods, "candidates": candidates,
        "tactical_report": analyze_match_tactics(match), "player_evaluations": player_evaluations,
        "tesseract_ready": tesseract_available(),
    })


@router.post("/match-analysis/{match_id}/rapid-run")
def rapid_run(
    match_id: int,
    request: Request,
    include_audio: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    if match.video_source != "upload" or not match.video_path:
        raise HTTPException(
            400,
            detail="L'analyse rapide complète nécessite une vidéo détenue et téléversée. Les URL tierces restent des références horodatées.",
        )
    source_path = UPLOAD_DIR / Path(match.video_path).name
    try:
        run_rapid_analysis(
            db, match, source_path, EVIDENCE_DIR,
            include_audio=include_audio.lower() in {"1", "true", "on", "yes"},
        )
    except RapidAnalysisError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    return RedirectResponse(f"/match-analysis/{match_id}", status_code=303)
