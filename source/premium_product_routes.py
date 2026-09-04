from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_db
from models import Match, MatchLibraryItem, User
from services.analysis_product import analysis_snapshot
from services.deep_analysis_sequences import sequence_gallery, sequence_summary
from services.premium_public_analysis import build_public_match_dossier
from services.team_scoring_patterns import build_team_scoring_patterns
from services.video import youtube_embed

router = APIRouter()
TEMPLATES = Jinja2Templates(directory="templates")

FILM_ROOM = [
    {"id":"a5Ja269h5G8","title":"USA – Espagne","context":"World Cup 2026 · finale","focus":"Décision sous pression · finition · sortie gardienne · A→D"},
    {"id":"VvuJSTuuUI8","title":"Russie – Espagne","context":"World Cup 2026 · demi-finale","focus":"Centre · continuité · late game · transition"},
    {"id":"fWFM4kB8nvw","title":"France – Israël","context":"Senior 2026","focus":"Ailes hautes · entrée centre · sécurité de balle · repli"},
    {"id":"bF-Am10VtF4","title":"Espagne – Grèce U20","context":"U20 · benchmark","focus":"Double scan · tempo · duel centre · 3v2"},
    {"id":"HfkCCOpLIBA","title":"Hongrie – Espagne","context":"Mondiaux 2025 · demi-finale","focus":"Sélection de tirs · centre-back · zone→press"},
    {"id":"Ek1kBvUjivc","title":"Grèce – USA","context":"Mondiaux 2025 · demi-finale","focus":"Hip advantage · drive · passe +1 · repli"},
    {"id":"TseN9CGbfQw","title":"Grèce – Hongrie","context":"Mondiaux 2025","focus":"Lecture bloc · tempo · possession · late game"},
    {"id":"Z-8PwbnKBWU","title":"Espagne – Pays-Bas","context":"Mondiaux 2025 · quart","focus":"Circulation · défense drive · gardienne · réponse après perte"},
]


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _workspace_card(db: Session, match: Match):
    snapshot = analysis_snapshot(db, match)
    report = snapshot.get("ultimate", {}).get("team", {})
    basic = report.get("basic", {})
    coverage = report.get("coverage", {"score": 0, "readiness": "SPARSE"})
    sequences = sequence_gallery(db, match, max_total=12)
    scoring = build_team_scoring_patterns(db, match)
    source_embed = youtube_embed(match.video_url) if match.video_url else ""
    if not source_embed and snapshot.get("reference") and snapshot["reference"].get("video_url"):
        source_embed = youtube_embed(snapshot["reference"]["video_url"]) or ""
    return {
        "match": match,
        "basic": basic,
        "coverage": coverage,
        "sequence_summary": sequence_summary(sequences),
        "sequences": sequences[:4],
        "scoring": scoring,
        "video_embed": source_embed,
        "local_video": match.video_source == "upload" and bool(match.video_path),
        "verified_events": len(snapshot.get("verified_events", []) or []),
        "automatic": len(snapshot.get("automatic", {}).get("candidates", []) or []),
    }


@router.get("/analysis-library", response_class=HTMLResponse)
def premium_analysis_library(
    request: Request,
    competition: str = Query(""),
    team: str = Query(""),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    workspace = db.scalars(
        select(Match).where(Match.owner_id == user.id).order_by(Match.created_at.desc(), Match.id.desc()).limit(24)
    ).all()
    workspace_rows = [_workspace_card(db, m) for m in workspace]

    stmt = select(MatchLibraryItem).order_by(MatchLibraryItem.created_at.desc(), MatchLibraryItem.id.desc())
    if competition.strip():
        stmt = stmt.where(MatchLibraryItem.competition == competition.strip())
    if team.strip():
        token = f"%{team.strip().lower()}%"
        stmt = stmt.where((func.lower(MatchLibraryItem.team_a).like(token)) | (func.lower(MatchLibraryItem.team_b).like(token)))
    items = db.scalars(stmt.limit(80)).all()
    public_rows = []
    for item in items:
        dossier = build_public_match_dossier(db, item)
        public_rows.append(dossier)

    competitions = db.scalars(
        select(MatchLibraryItem.competition).where(MatchLibraryItem.competition != "").distinct().order_by(MatchLibraryItem.competition)
    ).all()
    video_count = sum(1 for d in public_rows if d["video"]["embed"])
    strong_count = sum(1 for d in public_rows if d["coverage"]["score"] >= 60)
    return TEMPLATES.TemplateResponse(
        request,
        "premium_analysis_library.html",
        {
            "request": request, "user": user, "app_name": "AquaMetric",
            "workspace_rows": workspace_rows, "public_rows": public_rows,
            "competitions": competitions, "selected_competition": competition, "selected_team": team,
            "film_room": FILM_ROOM, "video_count": video_count, "strong_count": strong_count,
        },
    )


@router.get("/analysis-library/{item_id}", response_class=HTMLResponse)
def premium_analysis_library_detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    item = db.get(MatchLibraryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library match not found")
    dossier = build_public_match_dossier(db, item)
    return TEMPLATES.TemplateResponse(
        request,
        "premium_analysis_library_detail.html",
        {"request": request, "user": user, "app_name": "AquaMetric", "d": dossier, "item": item},
    )
