from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import get_db
from models import Match, User, PlayerIntelligenceProfile, VisionAnalysis
from services.advanced_metrics import shot_map_summary
from services.performance_intelligence import team_performance_report, player_match_breakdown, shot_preference_summary
from services.ultimate_analytics import ultimate_match_report, ultimate_event_report
from services.ratings import calculate_player_rating
from services.video import youtube_embed

router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


@router.get("/api/matches/{match_id}/performance")
def match_performance_api(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)

    team_report = team_performance_report(match)
    ultimate = ultimate_match_report(match)
    players = []
    for player in match.team.players:
        events = [e for e in match.events if e.player_id == player.id]
        _, _, evidence = calculate_player_rating(events, role=player.primary_role)
        detail = evidence["__evaluation__"]
        profile = db.scalar(
            select(PlayerIntelligenceProfile).where(
                func.lower(PlayerIntelligenceProfile.canonical_name) == player.name.strip().lower()
            )
        )
        shot_pref = {"available": False, "count": 0, "origin": "Not enough located shots", "target": "Not enough target-zone shots"}
        if profile:
            shot_pref = shot_preference_summary(shot_map_summary(db, profile.id))
        players.append({
            "id": player.id,
            "name": player.name,
            "cap": player.cap_number,
            "role": player.primary_role or "",
            "profile_url": f"/profiles/players/{profile.id}" if profile else f"/players/{player.id}",
            "rating": detail.get("overall"),
            "confidence": detail.get("confidence_label"),
            "confidence_score": detail.get("confidence_score", 0),
            "dimensions": detail.get("dimensions", {}),
            "strengths": detail.get("strengths", []),
            "improvements": detail.get("improvements", []),
            "breakdown": player_match_breakdown(events, detail, role=player.primary_role or ""),
            "ultimate": ultimate_event_report(events, "for"),
            "shot_preference": shot_pref,
        })

    players.sort(key=lambda x: (x["rating"] is not None, x["rating"] or -1), reverse=True)

    media = []
    for artifact in sorted(match.media_artifacts, key=lambda a: (float(a.second or 0), a.id or 0)):
        local_url = f"/matches/{match.id}/evidence/{artifact.id}" if artifact.file_path else ""
        media.append({
            "id": artifact.id,
            "type": artifact.artifact_type,
            "title": artifact.title,
            "note": artifact.note or "",
            "second": float(artifact.second or 0),
            "url": local_url or artifact.external_url or "",
            "local": bool(local_url),
            "mime_type": artifact.mime_type or "",
            "analysis_type": artifact.analysis_type or "",
        })

    vision = db.scalar(
        select(VisionAnalysis).where(VisionAnalysis.match_id == match.id).order_by(VisionAnalysis.id.desc())
    )
    if vision and vision.contact_sheet_file:
        media.insert(0, {
            "id": f"vision-{vision.id}", "type": "contact_sheet", "title": "Vision contact sheet",
            "note": "Sampled frames from the visual baseline scan.", "second": 0,
            "url": f"/matches/{match.id}/vision/contact-sheet", "local": True,
            "mime_type": "image/jpeg", "analysis_type": "vision",
        })

    embed = youtube_embed(match.video_url) if match.video_url else None
    video = {
        "source": match.video_source,
        "embed_url": embed or "",
        "local_url": f"/matches/{match.id}/video" if match.video_source == "upload" and match.video_path else "",
        "external_url": match.video_url if match.video_url and not embed else "",
    }

    return {
        "match": {"id": match.id, "team": match.team.name, "opponent": match.opponent, "competition": match.competition or ""},
        "team_performance": team_report,
        "ultimate": ultimate,
        "players": players,
        "video": video,
        "media": media,
        "policy": {
            "physical_tracking": "Absolute sprint/shot-speed values are shown only when a calibrated measurement is explicitly tagged.",
            "possession": "Exact possession rates require possession=ID tags; otherwise AquaMetric shows only terminal-action proxies.",
            "third_party_video": "Third-party video remains embedded/timestamp-linked; AquaMetric does not copy it.",
            "qualitative": "Coach findings are evidence-linked hypotheses and must be checked against video before being treated as causal conclusions.",
        },
    }


# URL sources use the same Ultimate Analyst contract as uploaded matches.
# Registering the nested router here keeps the URL result path inside the
# already-installed tactical/performance extension tree.
from url_analysis_routes import router as url_analysis_router
router.include_router(url_analysis_router)
