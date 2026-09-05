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
from services.player_premium_metrics import build_player_premium_metrics
from services.premium_public_analysis import build_public_match_dossier
from services.team_scoring_patterns import build_team_scoring_patterns
from services.video import youtube_embed

router = APIRouter()
TEMPLATES = Jinja2Templates(directory="templates")

FILM_ROOM = [
    {"id":"a5Ja269h5G8","title":"USA – Espagne","context":"World Cup 2026 · finale","focus":"Décision sous pression · finition · sortie gardienne · A→D","teams":["United States","Spain"]},
    {"id":"VvuJSTuuUI8","title":"Russie – Espagne","context":"World Cup 2026 · demi-finale","focus":"Centre · continuité · late game · transition","teams":["Russia","Spain"]},
    {"id":"fWFM4kB8nvw","title":"France – Israël","context":"Senior 2026","focus":"Ailes hautes · entrée centre · sécurité de balle · repli","teams":["France","Israel"]},
    {"id":"bF-Am10VtF4","title":"Espagne – Grèce U20","context":"U20 · benchmark","focus":"Double scan · tempo · duel centre · 3v2","teams":["Spain","Greece"],"u20":True},
    {"id":"HfkCCOpLIBA","title":"Hongrie – Espagne","context":"Mondiaux 2025 · demi-finale","focus":"Sélection de tirs · centre-back · zone→press","teams":["Hungary","Spain"]},
    {"id":"Ek1kBvUjivc","title":"Grèce – USA","context":"Mondiaux 2025 · demi-finale","focus":"Hip advantage · drive · passe +1 · repli","teams":["Greece","United States"]},
    {"id":"TseN9CGbfQw","title":"Grèce – Hongrie","context":"Mondiaux 2025","focus":"Lecture bloc · tempo · possession · late game","teams":["Greece","Hungary"]},
    {"id":"Z-8PwbnKBWU","title":"Espagne – Pays-Bas","context":"Mondiaux 2025 · quart","focus":"Circulation · défense drive · gardienne · réponse après perte","teams":["Spain","Netherlands"]},
]

ALIASES = {
    "usa": "united states", "united states of america": "united states", "us": "united states",
    "espagne": "spain", "russie": "russia", "israël": "israel", "israel": "israel",
    "grèce": "greece", "hongrie": "hungary", "pays-bas": "netherlands", "netherlands": "netherlands",
}


def _norm_team(value: str) -> str:
    key = (value or "").strip().lower()
    return ALIASES.get(key, key)


def _item_context(item: MatchLibraryItem) -> str:
    parts = [
        getattr(item, "competition", "") or "",
        getattr(item, "season", "") or "",
        getattr(item, "source_quality", "") or "",
        getattr(item, "official_source_name", "") or "",
        getattr(item, "video_label", "") or "",
    ]
    return " ".join(str(x) for x in parts).lower()


def _film_room_rows(db: Session):
    library = db.scalars(select(MatchLibraryItem).order_by(MatchLibraryItem.id.desc())).all()
    rows = []
    for reference in FILM_ROOM:
        wanted = {_norm_team(x) for x in reference["teams"]}
        match = None
        for item in library:
            pair = {_norm_team(item.team_a), _norm_team(item.team_b)}
            if pair != wanted:
                continue
            if reference.get("u20") and "u20" not in _item_context(item):
                continue
            match = item
            break
        row = dict(reference)
        row["dossier"] = build_public_match_dossier(db, match) if match else None
        rows.append(row)
    return rows


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _owned_match(match_id: int, request: Request, db: Session):
    user = _user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Match not found")
    return user, match


def _workspace_card(db: Session, match: Match):
    snapshot = analysis_snapshot(db, match)
    report = snapshot.get("ultimate", {}).get("team", {})
    basic = report.get("basic", {})
    coverage = report.get("coverage", {"score": 0, "readiness": "SPARSE"})
    sequences = sequence_gallery(db, match, max_total=72)
    scoring = build_team_scoring_patterns(db, match)
    source_embed = youtube_embed(match.video_url) if match.video_url else ""
    if not source_embed and snapshot.get("reference") and snapshot["reference"].get("video_url"):
        source_embed = youtube_embed(snapshot["reference"]["video_url"]) or ""
    return {
        "match": match,
        "basic": basic,
        "coverage": coverage,
        "sequence_summary": sequence_summary(sequences),
        "sequences": sequences[:6],
        "scoring": scoring,
        "video_embed": source_embed,
        "local_video": match.video_source == "upload" and bool(match.video_path),
        "verified_events": len(snapshot.get("verified_events", []) or []),
        "automatic": len(snapshot.get("automatic", {}).get("candidates", []) or []),
    }


def _sequence_payload(card: dict) -> dict:
    return {
        "event_id": card.get("event_id"),
        "second": card.get("second"),
        "start_second": card.get("start_second"),
        "end_second": card.get("end_second"),
        "title": card.get("title"),
        "summary": card.get("summary"),
        "kind": card.get("kind"),
        "confidence": card.get("confidence"),
        "confidence_label": card.get("confidence_label"),
        "phase": card.get("phase"),
        "clip_url": card.get("clip_url"),
        "segment_embed": card.get("segment_embed"),
        "local_segment_url": card.get("local_segment_url"),
        "external_url": card.get("external_url"),
        "screenshot_urls": card.get("screenshot_urls", [])[:3],
        "downloadable": card.get("downloadable", False),
    }


@router.get("/api/premium/matches/{match_id}/brief")
def premium_match_brief(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    snapshot = analysis_snapshot(db, match)
    scoring = build_team_scoring_patterns(db, match)
    sequences = sequence_gallery(db, match, max_total=72)
    sequence_by_event = {}
    for card in sequences:
        event_id = card.get("event_id")
        if event_id:
            sequence_by_event.setdefault(int(event_id), []).append(card)

    players = []
    for player in list(match.team.players or []):
        events = [e for e in list(match.events or []) if e.player_id == player.id]
        breakdown = build_player_premium_metrics(events, role=player.primary_role)
        board = breakdown.get("statboard", {})
        if not events and not any(board.get(k) for k in ("goals", "shots", "passes_completed", "turnovers", "saves", "ball_touches")):
            continue
        evidence = []
        seen = set()
        for event in events:
            for card in sequence_by_event.get(int(event.id), []):
                key = (card.get("kind"), card.get("second"))
                if key in seen:
                    continue
                seen.add(key)
                evidence.append(_sequence_payload(card))
                if len(evidence) >= 8:
                    break
            if len(evidence) >= 8:
                break
        players.append({
            "id": player.id,
            "name": player.name,
            "cap": player.cap_number,
            "role": player.primary_role,
            "event_count": len(events),
            "position_family": breakdown.get("position_family"),
            "statboard": board,
            "losses": breakdown.get("loss_breakdown", {}),
            "transition": breakdown.get("transition_timing", {}),
            "physical": breakdown.get("physical", {}),
            "observed_action_span": breakdown.get("observed_action_span"),
            "measurement_contract": breakdown.get("measurement_contract", {}),
            "measurement_tags": breakdown.get("measurement_tags", []),
            "checklist": breakdown.get("qualitative_checklist", []),
            "phases": breakdown.get("phases", {}),
            "evidence": evidence,
        })
    players.sort(key=lambda p: (-(p["statboard"].get("goals") or 0), -(p["statboard"].get("ball_touches") or 0), -p["event_count"], p["name"]))

    team = snapshot.get("ultimate", {}).get("team", {})
    opponent = snapshot.get("ultimate", {}).get("opponent", {})
    team_scoring = scoring.get("team", {}) if isinstance(scoring, dict) else {}
    opp_scoring = scoring.get("opponent", {}) if isinstance(scoring, dict) else {}
    summary = sequence_summary(sequences)
    return {
        "match": {"id": match.id, "team": match.team.name, "opponent": match.opponent, "competition": match.competition, "date": match.match_date},
        "coverage": team.get("coverage", {}),
        "basic": team.get("basic", {}),
        "opponent_basic": opponent.get("basic", {}),
        "qualitative": team.get("qualitative", [])[:12],
        "losses": team.get("losses", {}),
        "shots": team.get("shots", {}),
        "passes": team.get("passes", {}),
        "phases": team.get("phases", [])[:16],
        "periods": team.get("periods", [])[:8],
        "decisions": team.get("decisions", {}),
        "pressure": team.get("pressure", {}),
        "possessions": team.get("possessions", {}),
        "positive_habits": team_scoring.get("positive_habits", [])[:8],
        "negative_habits": team_scoring.get("negative_habits", [])[:8],
        "tendencies": team_scoring.get("tendencies", [])[:8],
        "phase_scoring": team_scoring.get("phase_rows", [])[:12],
        "top_scorers": team_scoring.get("top_scorers", [])[:10],
        "repeated_routes": team_scoring.get("repeated_routes", [])[:10],
        "opponent_habits": {
            "positive": opp_scoring.get("positive_habits", [])[:6],
            "negative": opp_scoring.get("negative_habits", [])[:6],
            "tendencies": opp_scoring.get("tendencies", [])[:6],
        },
        "players": players[:24],
        "sequence_summary": summary,
        "sequences": [_sequence_payload(card) for card in sequences[:36]],
        "evidence_contract": {
            "max_sequences": 72,
            "visible_wall": min(36, len(sequences)),
            "local_video": match.video_source == "upload" and bool(match.video_path),
            "third_party_policy": "Les sources tierces restent embarquées/horodatées ; aucune fausse capture n'est fabriquée.",
        },
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
    public_rows = [build_public_match_dossier(db, item) for item in items]
    film_room = _film_room_rows(db)

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
            "film_room": film_room, "video_count": video_count, "strong_count": strong_count,
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
