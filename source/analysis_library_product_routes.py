from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_db
from models import (
    AnalysisJob,
    AutonomousAnalysis,
    AutonomousEventCandidate,
    Event,
    LibraryPlayerMatchStat,
    Match,
    MatchLibraryItem,
    MediaArtifact,
    User,
    VisionAnalysis,
)
from services.analysis_product import analysis_snapshot
from services.video import youtube_embed

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _json(raw, fallback):
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, type(fallback)) else fallback
    except Exception:
        return fallback


def _latest(db, model, match_id: int):
    return db.scalar(select(model).where(model.match_id == match_id).order_by(model.created_at.desc(), model.id.desc()))


def _published_coverage(item, stats, team_stats, quarters):
    signals = {
        "final_score": item.score_a is not None and item.score_b is not None,
        "quarters": bool(quarters),
        "team_stats": bool({k: v for k, v in team_stats.items() if k != "_aquametric"}),
        "player_stats": bool(stats),
        "official_source": bool(item.official_source_url),
        "replay": bool(item.video_url),
    }
    score = round(100 * sum(signals.values()) / len(signals))
    readiness = "PUBLISHED COMPLETE" if score >= 85 else "PUBLISHED STRONG" if score >= 65 else "PUBLISHED PARTIAL" if score >= 35 else "CATALOGUED"
    return {"score": score, "readiness": readiness, "signals": signals}


@router.get("/analysis-library", response_class=HTMLResponse)
def ultimate_analysis_library(
    request: Request,
    competition: str = "",
    team: str = "",
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    workspace_matches = db.scalars(
        select(Match).where(Match.owner_id == user.id).order_by(Match.created_at.desc(), Match.id.desc())
    ).all()
    workspace_rows = []
    for match in workspace_matches:
        if team and team.lower() not in f"{match.team.name} {match.opponent}".lower():
            continue
        if competition and competition.lower() not in (match.competition or "").lower():
            continue
        snapshot = analysis_snapshot(db, match)
        exact_count = sum(1 for a in snapshot["artifacts"] if str(a.get("source") or "").startswith("analysis_exact"))
        workspace_rows.append({
            "match": match,
            "snapshot": snapshot,
            "ultimate": snapshot["ultimate"],
            "coverage": snapshot["ultimate"]["team"]["coverage"],
            "team_basic": snapshot["ultimate"]["team"]["basic"],
            "opponent_basic": snapshot["ultimate"]["opponent"]["basic"],
            "latest_job": _latest(db, AnalysisJob, match.id),
            "latest_vision": _latest(db, VisionAnalysis, match.id),
            "latest_auto": _latest(db, AutonomousAnalysis, match.id),
            "events_count": len(snapshot["verified_events"]),
            "media_count": len(snapshot["artifacts"]),
            "exact_count": exact_count,
            "automatic_count": len(snapshot["automatic"]["candidates"]),
            "has_owned_video": bool(match.video_source == "upload" and match.video_path),
        })

    stmt = select(MatchLibraryItem).order_by(MatchLibraryItem.season.desc(), MatchLibraryItem.id.desc())
    if competition:
        stmt = stmt.where(MatchLibraryItem.competition.contains(competition))
    if team:
        stmt = stmt.where((MatchLibraryItem.team_a.contains(team)) | (MatchLibraryItem.team_b.contains(team)))
    items = db.scalars(stmt).all()
    public_rows = []
    for item in items:
        stats = db.scalars(select(LibraryPlayerMatchStat).where(LibraryPlayerMatchStat.library_match_id == item.id)).all()
        quarters = _json(item.quarter_scores_json, [])
        team_stats = _json(item.team_stats_json, {})
        public_rows.append({
            "item": item,
            "coverage": _published_coverage(item, stats, team_stats, quarters),
            "player_count": len(stats),
            "quarter_count": len(quarters),
            "team_stat_count": len([k for k, v in team_stats.items() if k != "_aquametric" and isinstance(v, dict)]),
            "embed_url": youtube_embed(item.video_url) if item.video_url else "",
        })

    competitions = sorted(
        {x.competition for x in items if x.competition}
        | {x.competition for x in workspace_matches if x.competition}
    )
    return TEMPLATES.TemplateResponse(request, "analysis_library.html", {
        "request": request, "user": user, "app_name": "AquaMetric",
        "workspace_rows": workspace_rows, "items": items, "public_rows": public_rows,
        "competitions": competitions, "selected_competition": competition, "selected_team": team,
    })


@router.get("/analysis-library/{item_id}", response_class=HTMLResponse)
def published_ultimate_detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    item = db.get(MatchLibraryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library match not found")
    stats = db.scalars(
        select(LibraryPlayerMatchStat)
        .where(LibraryPlayerMatchStat.library_match_id == item.id)
        .order_by(LibraryPlayerMatchStat.team_name, LibraryPlayerMatchStat.player_name)
    ).all()
    quarters = _json(item.quarter_scores_json, [])
    team_stats_raw = _json(item.team_stats_json, {})
    evidence_meta = team_stats_raw.get("_aquametric", {}) if isinstance(team_stats_raw, dict) else {}
    team_stats = {k: v for k, v in team_stats_raw.items() if k != "_aquametric" and isinstance(v, dict)}
    coverage = _published_coverage(item, stats, team_stats_raw, quarters)
    teams = {}
    for row in stats:
        teams.setdefault(row.team_name or "Équipe non précisée", []).append(row)

    return TEMPLATES.TemplateResponse(request, "analysis_library_ultimate_detail.html", {
        "request": request, "user": user, "app_name": "AquaMetric",
        "item": item, "stats": stats, "teams": teams, "quarters": quarters,
        "team_stats": team_stats, "evidence_meta": evidence_meta,
        "coverage": coverage, "embed_url": youtube_embed(item.video_url) if item.video_url else "",
    })
