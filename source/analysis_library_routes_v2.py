import json
from pathlib import Path

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import get_db
from models import (
    User,
    Match,
    Event,
    MediaArtifact,
    AnalysisJob,
    VisionAnalysis,
    MatchLibraryItem,
    LibraryPlayerMatchStat,
)
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


def _safe_json(raw, fallback):
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, type(fallback)) else fallback
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _quarter_review(quarters):
    rows = []
    cumulative_a = 0
    cumulative_b = 0
    biggest = None
    for index, pair in enumerate(quarters, start=1):
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        try:
            a, b = int(pair[0]), int(pair[1])
        except (TypeError, ValueError):
            continue
        cumulative_a += a
        cumulative_b += b
        diff = a - b
        if diff > 0:
            label = "avantage équipe A"
        elif diff < 0:
            label = "avantage équipe B"
        else:
            label = "quart équilibré"
        row = {
            "quarter": index,
            "a": a,
            "b": b,
            "diff": diff,
            "abs_diff": abs(diff),
            "cumulative_a": cumulative_a,
            "cumulative_b": cumulative_b,
            "label": label,
        }
        rows.append(row)
        if biggest is None or row["abs_diff"] > biggest["abs_diff"]:
            biggest = row
    first_half_a = sum(r["a"] for r in rows[:2])
    first_half_b = sum(r["b"] for r in rows[:2])
    second_half_a = sum(r["a"] for r in rows[2:])
    second_half_b = sum(r["b"] for r in rows[2:])
    if biggest:
        turning = (
            f"Q{biggest['quarter']} est la période la plus déséquilibrée dans la preuve disponible "
            f"({biggest['a']}–{biggest['b']}). Cela identifie une bascule statistique à revoir ; "
            "la cause tactique ne doit être attribuée qu'avec une vidéo ou un rapport qui la documente."
        )
    else:
        turning = "Aucun détail par quart n'est disponible : la lecture reste limitée au score final et aux sources publiées."
    return {
        "quarters": rows,
        "biggest": biggest,
        "first_half": (first_half_a, first_half_b),
        "second_half": (second_half_a, second_half_b),
        "turning": turning,
    }


@router.get("/analysis-library", response_class=HTMLResponse)
def analysis_library_page_v2(
    request: Request,
    competition: str = Query(""),
    team: str = Query(""),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    stmt = select(MatchLibraryItem).order_by(MatchLibraryItem.created_at.desc(), MatchLibraryItem.id.desc())
    if competition.strip():
        stmt = stmt.where(MatchLibraryItem.competition == competition.strip())
    if team.strip():
        token = f"%{team.strip().lower()}%"
        stmt = stmt.where(
            (func.lower(MatchLibraryItem.team_a).like(token)) |
            (func.lower(MatchLibraryItem.team_b).like(token))
        )
    items = db.scalars(stmt).all()
    competitions = db.scalars(
        select(MatchLibraryItem.competition)
        .where(MatchLibraryItem.competition != "")
        .distinct()
        .order_by(MatchLibraryItem.competition)
    ).all()

    workspace_matches = db.scalars(
        select(Match)
        .where(Match.owner_id == user.id)
        .order_by(Match.created_at.desc(), Match.id.desc())
    ).all()
    workspace_rows = []
    for match in workspace_matches:
        events_count = db.scalar(select(func.count(Event.id)).where(Event.match_id == match.id)) or 0
        media_count = db.scalar(select(func.count(MediaArtifact.id)).where(MediaArtifact.match_id == match.id)) or 0
        latest_job = db.scalar(
            select(AnalysisJob)
            .where(AnalysisJob.match_id == match.id)
            .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
        )
        latest_vision = db.scalar(
            select(VisionAnalysis)
            .where(VisionAnalysis.match_id == match.id)
            .order_by(VisionAnalysis.created_at.desc(), VisionAnalysis.id.desc())
        )
        workspace_rows.append({
            "match": match,
            "events_count": events_count,
            "media_count": media_count,
            "latest_job": latest_job,
            "latest_vision": latest_vision,
            "has_owned_video": bool(match.video_path),
        })

    return TEMPLATES.TemplateResponse(
        request,
        "analysis_library.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "items": items,
            "competitions": competitions,
            "selected_competition": competition,
            "selected_team": team,
            "workspace_rows": workspace_rows,
        },
    )


@router.get("/analysis-library/{item_id}", response_class=HTMLResponse)
def analysis_library_detail_v2(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    item = db.get(MatchLibraryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library match not found")

    quarters = _safe_json(item.quarter_scores_json, [])
    raw_stats = _safe_json(item.team_stats_json, {})
    evidence_meta = raw_stats.get("_aquametric", {}) if isinstance(raw_stats, dict) else {}
    team_stats = {
        k: v for k, v in raw_stats.items()
        if k != "_aquametric" and isinstance(v, dict)
    } if isinstance(raw_stats, dict) else {}

    rows = db.scalars(
        select(LibraryPlayerMatchStat)
        .where(LibraryPlayerMatchStat.library_match_id == item.id)
        .order_by(LibraryPlayerMatchStat.team_name, LibraryPlayerMatchStat.goals.desc().nullslast(), LibraryPlayerMatchStat.player_name)
    ).all()
    teams = {}
    for row in rows:
        teams.setdefault(row.team_name or "Équipe non précisée", []).append(row)

    embed_url = youtube_embed(item.video_url) if item.video_url else ""
    review = _quarter_review(quarters)
    return TEMPLATES.TemplateResponse(
        request,
        "analysis_library_detail.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "item": item,
            "quarters": quarters,
            "quarter_review": review,
            "team_stats": team_stats,
            "evidence_meta": evidence_meta,
            "teams": teams,
            "embed_url": embed_url,
        },
    )
