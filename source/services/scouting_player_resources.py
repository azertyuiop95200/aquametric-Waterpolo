from collections import Counter, defaultdict
import re
import unicodedata
from urllib.parse import quote_plus

from sqlalchemy import select

from models import (
    MatchLibraryItem,
    PlayerIntelligenceProfile,
    PlayerMatchMetric,
    PlayerShotObservation,
    PlayerSourceRecord,
    ScoutingPlayer,
    TransferSignal,
)


CARD_METRICS = (
    "goals",
    "assists",
    "shots",
    "steals",
    "saves",
    "exclusion_earned",
    "penalty_earned",
)

METRIC_LABELS = {
    "goals": "Buts",
    "assists": "Passes décisives",
    "shots": "Tirs",
    "steals": "Interceptions / steals",
    "saves": "Arrêts",
    "exclusion_earned": "Exclusions obtenues",
    "penalty_earned": "Penalties obtenus",
}


def _name_key(value: str) -> str:
    """Normalize roster/profile spellings without changing the displayed identity."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.casefold()).strip()


def _confidence_label(score: float) -> str:
    if score >= 0.90:
        return "très élevée"
    if score >= 0.75:
        return "élevée"
    if score >= 0.55:
        return "moyenne"
    return "limitée"


def _coverage_state(score: int) -> str:
    if score >= 75:
        return "riche"
    if score >= 50:
        return "intermédiaire"
    return "partielle"


def _metric_totals(metrics: list[PlayerMatchMetric]) -> dict[str, float]:
    totals = {name: 0.0 for name in CARD_METRICS}
    for metric in metrics:
        if metric.metric in totals and metric.value is not None:
            totals[metric.metric] += float(metric.value)
    return totals


def _shot_summary(shots: list[PlayerShotObservation]) -> dict:
    located = [s for s in shots if s.pool_x is not None or s.pool_y is not None or s.goal_x is not None or s.goal_y is not None]
    known_side = [s.shooter_side for s in shots if s.shooter_side and s.shooter_side != "unknown"]
    side = None
    side_share = None
    if len(known_side) >= 3:
        counts = Counter(known_side)
        leader, leader_count = counts.most_common(1)[0]
        share = round(leader_count / len(known_side) * 100)
        if share >= 60:
            side = leader
            side_share = share

    known_outcomes = [s.outcome for s in shots if s.outcome and s.outcome != "unknown"]
    goals = sum(1 for outcome in known_outcomes if outcome == "goal")
    efficiency = round(goals / len(known_outcomes) * 100) if len(known_outcomes) >= 3 else None
    contexts = Counter(s.shot_context for s in shots if s.shot_context and s.shot_context != "unknown")

    return {
        "observations": len(shots),
        "located": len(located),
        "known_outcomes": len(known_outcomes),
        "goals": goals,
        "efficiency": efficiency,
        "side_preference": side,
        "side_share": side_share,
        "top_contexts": [name for name, _ in contexts.most_common(3)],
    }


def scouting_player_resources(db, scouting_team_id: int) -> list[dict]:
    roster = db.scalars(
        select(ScoutingPlayer)
        .where(ScoutingPlayer.scouting_team_id == scouting_team_id)
        .order_by(ScoutingPlayer.cap_number.nullslast(), ScoutingPlayer.name)
    ).all()
    if not roster:
        return []

    roster_keys = {_name_key(row.name) for row in roster}

    # The registry is intentionally canonical. Resolve in Python with an accent/
    # punctuation-insensitive key so scouting aliases do not silently lose the
    # richer dossier (e.g. Rozic/Rožić variants).
    profiles = [
        p for p in db.scalars(select(PlayerIntelligenceProfile)).all()
        if _name_key(p.canonical_name) in roster_keys
    ]
    profile_by_name = {_name_key(p.canonical_name): p for p in profiles}
    profile_ids = [p.id for p in profiles]

    sources_by_profile = defaultdict(list)
    metrics_by_profile = defaultdict(list)
    shots_by_profile = defaultdict(list)
    if profile_ids:
        for row in db.scalars(select(PlayerSourceRecord).where(PlayerSourceRecord.profile_id.in_(profile_ids))).all():
            sources_by_profile[row.profile_id].append(row)
        for row in db.scalars(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id.in_(profile_ids))).all():
            metrics_by_profile[row.profile_id].append(row)
        for row in db.scalars(select(PlayerShotObservation).where(PlayerShotObservation.profile_id.in_(profile_ids))).all():
            shots_by_profile[row.profile_id].append(row)

    transfers_by_name = defaultdict(list)
    for row in db.scalars(select(TransferSignal)).all():
        key = _name_key(row.player_name)
        if key in roster_keys:
            transfers_by_name[key].append(row)

    all_match_ids = {
        metric.library_match_id
        for rows in metrics_by_profile.values()
        for metric in rows
        if metric.library_match_id is not None
    }
    matches_by_id = {}
    if all_match_ids:
        matches_by_id = {
            match.id: match
            for match in db.scalars(select(MatchLibraryItem).where(MatchLibraryItem.id.in_(all_match_ids))).all()
        }

    cards = []
    for roster_player in roster:
        key = _name_key(roster_player.name)
        profile = profile_by_name.get(key)
        sources = sources_by_profile.get(profile.id, []) if profile else []
        metrics = metrics_by_profile.get(profile.id, []) if profile else []
        shots = shots_by_profile.get(profile.id, []) if profile else []
        transfers = sorted(
            transfers_by_name.get(key, []),
            key=lambda row: (row.published_date or "", row.id),
            reverse=True,
        )

        documented_match_ids = {m.library_match_id for m in metrics if m.library_match_id is not None}
        performance_match_ids = {
            m.library_match_id
            for m in metrics
            if m.library_match_id is not None and m.metric != "appearance"
        }
        competitions = sorted({
            matches_by_id[mid].competition
            for mid in documented_match_ids
            if mid in matches_by_id and matches_by_id[mid].competition
        })
        evidence_seasons = sorted({s.season for s in sources if s.season}, reverse=True)
        metric_names = sorted({m.metric for m in metrics if m.metric != "appearance"})
        metric_totals = _metric_totals(metrics)
        shot = _shot_summary(shots)
        video_sources = [s for s in sources if "video" in (s.source_type or "").lower()]
        video_metrics = [m for m in metrics if "video" in (m.provenance or "").lower()]
        pathway_sources = [
            s for s in sources
            if s.source_type in {
                "club_announcement", "media_transfer", "official_competition",
                "federation_roster", "historical_roster",
            }
        ]

        coverage_dimensions = {
            "identité": profile is not None,
            "sources": bool(sources),
            "matchs": bool(documented_match_ids),
            "statistiques": bool(performance_match_ids),
            "tirs localisés": shot["located"] >= 3,
            "vidéo attribuée": bool(video_sources or video_metrics),
            "carrière / parcours": len(evidence_seasons) >= 2 or bool(pathway_sources) or bool(transfers),
            "mouvements": bool(transfers),
        }
        coverage_score = round(sum(coverage_dimensions.values()) / len(coverage_dimensions) * 100)
        confidence = float(profile.confidence_score or 0) if profile else 0.0

        cards.append({
            "id": roster_player.id,
            "name": roster_player.name,
            "cap_number": roster_player.cap_number,
            "birth_year": roster_player.birth_year,
            "nationality": (profile.nationality if profile and profile.nationality else roster_player.nationality) or "",
            "role": (profile.role if profile and profile.role else roster_player.role) or "Role to confirm",
            "current_status": roster_player.current_status,
            "note": roster_player.note,
            "profile": profile,
            "profile_url": f"/intelligence/player?name={quote_plus(profile.canonical_name if profile else roster_player.name)}",
            "confidence": confidence,
            "confidence_label": _confidence_label(confidence),
            "coverage_score": coverage_score,
            "coverage_state": _coverage_state(coverage_score),
            "coverage_dimensions": coverage_dimensions,
            "sources_count": len(sources),
            "source_tiers": sorted({s.trust_level for s in sources if s.trust_level}),
            "documented_matches": len(documented_match_ids),
            "performance_matches": len(performance_match_ids),
            "competitions": competitions,
            "metrics_count": len(metrics),
            "metric_names": metric_names,
            "metric_totals": metric_totals,
            "metric_labels": METRIC_LABELS,
            "shot": shot,
            "video_evidence_count": len(video_sources) + len(video_metrics),
            "transfer_count": len(transfers),
            "recent_transfers": transfers[:2],
            "evidence_seasons": evidence_seasons,
        })
    return cards


def scouting_team_resource_summary(cards: list[dict]) -> dict:
    if not cards:
        return {
            "players": 0,
            "linked_profiles": 0,
            "sources": 0,
            "metrics": 0,
            "documented_player_matches": 0,
            "performance_player_matches": 0,
            "located_shots": 0,
            "video_evidence": 0,
            "leaders": [],
        }

    leaders = []
    leader_specs = (
        ("goals", "Buts documentés"),
        ("assists", "Passes décisives documentées"),
        ("saves", "Arrêts documentés"),
        ("steals", "Interceptions / steals documentés"),
    )
    for metric, label in leader_specs:
        candidates = [c for c in cards if c["metric_totals"].get(metric, 0) > 0]
        if not candidates:
            continue
        best = max(candidates, key=lambda c: c["metric_totals"][metric])
        value = best["metric_totals"][metric]
        leaders.append({
            "metric": metric,
            "label": label,
            "name": best["name"],
            "value": int(value) if float(value).is_integer() else round(value, 1),
            "profile_url": best["profile_url"],
        })

    return {
        "players": len(cards),
        "linked_profiles": sum(1 for c in cards if c["profile"] is not None),
        "sources": sum(c["sources_count"] for c in cards),
        "metrics": sum(c["metrics_count"] for c in cards),
        "documented_player_matches": sum(c["documented_matches"] for c in cards),
        "performance_player_matches": sum(c["performance_matches"] for c in cards),
        "located_shots": sum(c["shot"]["located"] for c in cards),
        "video_evidence": sum(c["video_evidence_count"] for c in cards),
        "leaders": leaders,
    }
