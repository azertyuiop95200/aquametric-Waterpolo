"""Read-only, incremental sporting stats from independently finished AI video clips.

This is an *automatic hypothesis* layer. Never insert these detections into the
human-confirmed event table or imply a complete-match total. All queries are
owner-scoped by the authenticated API route.
"""
from __future__ import annotations

from collections import Counter
from sqlalchemy import select

from models import VideoActionAnalysis
from services.video_action_provider import provider_configuration
from services.video_action_report import action_report, run_progress

SHOT_TYPES = frozenset({"goal", "shot_on_target", "shot_off_target", "shot_blocked"})
FIELDS = ("goals", "shots", "saves", "turnovers", "assists", "exclusions_earned", "exclusions_committed")


def _counts(rows: list[dict]) -> dict:
    counter = Counter(item["event_type"] for item in rows if item.get("counted") is True)
    shots = sum(counter[t] for t in SHOT_TYPES)
    return {
        "goals": counter["goal"],
        "shots": shots,
        "saves": counter["save"],
        "turnovers": counter["turnover"] + counter["bad_pass"],
        "assists": counter["assist"],
        "exclusions_earned": counter["exclusion_earned"],
        "exclusions_committed": counter["exclusion_committed"],
        "efficiency_pct": round(100 * counter["goal"] / shots, 1) if shots else None,
        "actions": sum(counter.values()),
    }


def live_action_dashboard(db, match) -> dict:
    config = provider_configuration()
    all_runs = list(db.scalars(select(VideoActionAnalysis).where(
        VideoActionAnalysis.match_id == match.id
    ).order_by(VideoActionAnalysis.id.desc())).all())
    # A restart on the *same* recording replaces its previous result. Other
    # separate quarter-video recordings remain in the combined view.
    unique = {}
    for run in all_runs:
        unique.setdefault(run.source_path or f"run:{run.id}", run)
    runs = sorted(unique.values(), key=lambda r: r.id)
    all_rows = []
    public_runs = []
    completed, total = 0, 0
    active = False
    revisions = []
    for index, run in enumerate(runs, start=1):
        payload = action_report(db, match, run=run)
        progress = run_progress(db, match, run=run)
        completed += progress["completed"]
        total += progress["total"]
        active = active or progress["active"]
        revisions.append(progress["revision"])
        events = [dict(event, video_part=index, run_id=run.id)
                  for event in payload["events"]]
        all_rows.extend(events)
        public_runs.append({
            "part": index,
            "status": progress["status"],
            "completed": progress["completed"],
            "total": progress["total"],
            "coverage_percent": payload["coverage_percent"],
            "detected": sum(e.get("counted") is True for e in events),
            "message": progress["message"],
        })
    sides = {
        "for": _counts([e for e in all_rows if e.get("side") == "for"]),
        "against": _counts([e for e in all_rows if e.get("side") == "against"]),
        "unknown": _counts([e for e in all_rows if e.get("side") == "unknown"]),
    }
    # A timestamp belongs to its own source/quarter. Never add together
    # local video seconds to invent one continuous global timeline.
    visible_actions = sorted(
        [e for e in all_rows if e.get("counted")],
        key=lambda e: (e["video_part"], e["second"]))[-30:]
    timeline = [{
        "video_part": int(e["video_part"]),
        "second": round(float(e["second"]), 2),
        "event_type": e["event_type"],
        "side": e["side"],
        "confidence": round(float(e["confidence"]), 3),
        "cap_number": e.get("cap_number"),
        "label": str(e.get("label") or e["event_type"])[:80],
    } for e in visible_actions]
    if not config["configured"]:
        status = "unavailable"
        message = config["message"]
    elif not runs:
        status = "awaiting_video"
        message = "Moteur connecté. En attente d'une vidéo importée lisible ou de la fin d'une capture réelle."
    elif active:
        status = "processing"
        message = f"Analyse en cours : {completed}/{total} séquences terminées. Les chiffres sont provisoires."
    else:
        status = "ready" if any(r["status"] == "complete" for r in public_runs) else "partial"
        message = "Résultats automatiques disponibles, à vérifier sur la vidéo." if status == "ready" else (
            "Analyse incomplète : consulte les erreurs des séquences et relance les passages non traités."
        )
    return {
        "status":status, "configured":config["configured"],
        "message":message, "active":active,
        "completed":completed, "total":total,
        "revision":"|".join(revisions) if revisions else "",
        "sources":public_runs, "sides":sides,
        "recent_events":timeline, "counted_events":len([e for e in all_rows if e.get("counted")]),
        "excluded_events":len([e for e in all_rows if not e.get("counted")]),
        "scope":"automatic_provisional_only",
        "verified_events_unchanged":True,
        "accuracy_verified":False,
    }
