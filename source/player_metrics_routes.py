from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db
from models import Match, User
from services.deep_analysis_sequences import sequence_gallery, sequence_summary
from services.player_deep_metrics import player_deep_metrics, team_player_totals

router = APIRouter()


def _owned_match(match_id: int, request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.get("/api/v122/matches/{match_id}/player-metrics")
def player_metrics(match_id: int, request: Request, db: Session = Depends(get_db)):
    match = _owned_match(match_id, request, db)
    match_events = list(match.events or [])
    sequences = sequence_gallery(db, match, max_total=72)
    event_to_player = {e.id: e.player_id for e in match_events if e.id is not None and e.player_id is not None}
    media_by_player = {}
    for seq in sequences:
        pid = event_to_player.get(seq.get("event_id"))
        if not pid:
            continue
        media_by_player.setdefault(pid, []).append({
            "second": seq.get("second"),
            "title": seq.get("title"),
            "kind": seq.get("kind"),
            "confidence": seq.get("confidence"),
            "clip_url": seq.get("clip_url"),
            "segment_embed": seq.get("segment_embed"),
            "external_url": seq.get("external_url"),
            "screenshot_urls": list(seq.get("screenshot_urls") or [])[:3],
        })

    players = []
    for player in list(match.team.players or []):
        events = [e for e in match_events if e.player_id == player.id]
        row = player_deep_metrics(player, events)
        row["media"] = media_by_player.get(player.id, [])[:12]
        players.append(row)

    players.sort(key=lambda p: (-(p.get("event_count") or 0), p.get("cap") or 999, p.get("name") or ""))
    assigned = sum(1 for e in match_events if e.player_id is not None)
    summary = sequence_summary(sequences)
    return {
        "match": {"id": match.id, "team": match.team.name, "opponent": match.opponent},
        "totals": team_player_totals(players),
        "players": players,
        "attribution": {
            "events_total": len(match_events),
            "events_assigned": assigned,
            "events_unassigned": len(match_events) - assigned,
            "assigned_pct": round(100.0 * assigned / len(match_events), 1) if match_events else None,
        },
        "media": summary,
        "sequences": [
            {
                "second": s.get("second"), "title": s.get("title"), "kind": s.get("kind"),
                "confidence": s.get("confidence"), "clip_url": s.get("clip_url"),
                "segment_embed": s.get("segment_embed"), "external_url": s.get("external_url"),
                "screenshot_urls": list(s.get("screenshot_urls") or [])[:3],
            }
            for s in sequences
        ],
        "truth_policy": {
            "touches": "Comptés uniquement sur événements touch/centre_touch explicitement attribués.",
            "playing_time": "Affiché uniquement si playing_time_s ou minutes_played est explicitement tagué.",
            "distance": "Affichée uniquement si distance_total_m/distance_m est explicitement mesurée ou calibrée.",
            "physical": "Aucune vitesse ou distance absolue n'est inventée à partir d'un simple signal de mouvement vidéo.",
        },
    }
