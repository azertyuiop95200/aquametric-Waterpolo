import json
from collections import defaultdict
from statistics import mean

from sqlalchemy import select

from models import MatchLibraryItem, PlayerMatchMetric

DIMENSIONS = ("attack", "defence", "decision", "tactics", "transition", "discipline", "technique", "impact")

ROLE_WEIGHTS = {
    "field": {"attack": .18, "defence": .15, "decision": .15, "tactics": .13, "transition": .11, "discipline": .08, "technique": .10, "impact": .10},
    "goalkeeper": {"attack": .02, "defence": .27, "decision": .18, "tactics": .14, "transition": .08, "discipline": .07, "technique": .16, "impact": .08},
}


def _clamp(value, low=25.0, high=95.0):
    return round(max(low, min(high, value)), 1)


def _role_key(role):
    r = (role or "").lower()
    return "goalkeeper" if any(x in r for x in ("goal", "keeper", "gard")) else "field"


def _meta(match):
    try:
        payload = json.loads(match.team_stats_json or "{}")
    except Exception:
        payload = {}
    return payload.get("_aquametric", {}) if isinstance(payload, dict) else {}


def _team_total(match, player_team):
    if not player_team:
        return None
    if player_team == match.team_a:
        return match.score_a
    if player_team == match.team_b:
        return match.score_b
    # Current curated Lille rows can use a shortened alias in older records.
    if "lille" in player_team.lower():
        if "lille" in (match.team_a or "").lower():
            return match.score_a
        if "lille" in (match.team_b or "").lower():
            return match.score_b
    return None


def _result(match, player_team):
    total = _team_total(match, player_team)
    if total is None or match.score_a is None or match.score_b is None:
        return "unknown"
    opp = match.score_b if total == match.score_a and player_team == match.team_a else match.score_a
    if "lille" in (player_team or "").lower():
        if "lille" in (match.team_a or "").lower():
            opp = match.score_b
        elif "lille" in (match.team_b or "").lower():
            opp = match.score_a
    if total > opp:
        return "win"
    if total < opp:
        return "loss"
    return "draw"


def evaluate_public_match(match, metrics, role=""):
    """Rate only what a public source actually documents.

    Missing dimensions are returned as None. A /100 score is still provided so
    matches can be compared, but it is explicitly coverage-adjusted and carries
    a confidence ceiling when the source only publishes scorers.
    """
    by_metric = {m.metric: m for m in metrics}
    values = {k: (by_metric[k].value if k in by_metric else None) for k in ("goals", "shots", "assists", "steals", "saves", "exclusions")}
    meta = _meta(match)
    source_tier = meta.get("source_tier", "official_report")
    scorer_complete = bool(meta.get("scorer_list_complete", False))
    level = int(meta.get("competition_level", 3) or 3)
    player_team = next((getattr(m, "_team_name", None) for m in metrics if getattr(m, "_team_name", None)), None)
    if not player_team:
        # PlayerMatchMetric does not persist team_name; caller may attach it.
        player_team = getattr(metrics[0], "team_name", "") if metrics else ""
    team_total = _team_total(match, player_team)
    goals = values["goals"]
    share = (float(goals) / float(team_total)) if goals is not None and team_total else None
    result = _result(match, player_team)

    dims = {d: None for d in DIMENSIONS}
    evidence_families = 0
    published = []

    if goals is not None:
        evidence_families += 1
        share_bonus = min(12.0, (share or 0.0) * 42.0)
        difficulty = max(-2.0, min(4.0, (level - 3) * 1.6))
        win_bonus = 1.5 if result == "win" else (-0.5 if result == "loss" else 0.0)
        dims["attack"] = _clamp(49 + min(25.0, float(goals) * 4.0) + share_bonus + difficulty + win_bonus)
        dims["impact"] = _clamp(48 + min(24.0, float(goals) * 3.4) + min(13.0, (share or 0.0) * 45.0) + difficulty + win_bonus)
        published.append(f"{int(goals)} goal(s)")

    shots = values["shots"]
    if shots is not None:
        evidence_families += 1
        efficiency = (float(goals or 0) / float(shots)) if shots else 0.0
        dims["technique"] = _clamp(42 + efficiency * 52)
        dims["decision"] = _clamp(44 + efficiency * 40)
        published.append(f"{int(shots)} shot(s)")

    assists = values["assists"]
    if assists is not None:
        evidence_families += 1
        dims["decision"] = _clamp((dims["decision"] or 50) + min(18, assists * 5.0))
        dims["tactics"] = _clamp(50 + min(20, assists * 4.2))
        dims["attack"] = _clamp((dims["attack"] or 50) + min(12, assists * 2.5))
        published.append(f"{int(assists)} assist(s)")

    steals = values["steals"]
    if steals is not None:
        evidence_families += 1
        dims["defence"] = _clamp(50 + min(24, steals * 6.0))
        dims["transition"] = _clamp(50 + min(22, steals * 5.5))
        dims["decision"] = _clamp((dims["decision"] or 50) + min(12, steals * 3.0))
        published.append(f"{int(steals)} steal(s)")

    saves = values["saves"]
    if saves is not None:
        evidence_families += 1
        dims["defence"] = _clamp(48 + min(34, saves * 3.2))
        dims["technique"] = _clamp(48 + min(30, saves * 2.8))
        dims["impact"] = _clamp((dims["impact"] or 50) + min(25, saves * 2.4))
        published.append(f"{int(saves)} save(s)")

    exclusions = values["exclusions"]
    if exclusions is not None:
        evidence_families += 1
        dims["discipline"] = _clamp(60 - exclusions * 8.0)
        published.append(f"{int(exclusions)} exclusion(s)")

    available = [d for d, score in dims.items() if score is not None]
    coverage = round(len(available) / len(DIMENSIONS), 2)
    weights = ROLE_WEIGHTS[_role_key(role)]
    denom = sum(weights[d] for d in available)
    raw_overall = sum(dims[d] * weights[d] for d in available) / denom if denom else None

    # Pull low-coverage ratings gently toward neutral so a goals-only report cannot
    # masquerade as a complete all-round performance evaluation.
    if raw_overall is not None:
        shrink = 0.42 + coverage * 0.58
        overall = round(50 + (raw_overall - 50) * shrink, 1)
    else:
        overall = None

    confidence = .14 + coverage * .34
    if source_tier in {"federation_official", "official", "official_report"}:
        confidence += .08
    if scorer_complete:
        confidence += .10
    if evidence_families >= 2:
        confidence += .12
    confidence = round(min(.92, confidence), 2)
    if confidence < .35:
        confidence_label = "LIMITED"
    elif confidence < .60:
        confidence_label = "PARTIAL"
    elif confidence < .80:
        confidence_label = "SOLID"
    else:
        confidence_label = "HIGH"

    unavailable = [d for d in DIMENSIONS if dims[d] is None]
    scope = "fuller public stat line" if evidence_families >= 3 else ("multi-stat public evidence" if evidence_families >= 2 else "published scoring evidence only")
    return {
        "match": match,
        "overall": overall,
        "dimensions": dims,
        "coverage": coverage,
        "confidence_score": confidence,
        "confidence_label": confidence_label,
        "source_tier": source_tier,
        "scorer_list_complete": scorer_complete,
        "competition_level": level,
        "scope": scope,
        "published": published,
        "unavailable_dimensions": unavailable,
        "team_total": team_total,
        "goal_share": round(share * 100, 1) if share is not None else None,
        "result": result,
        "goals": int(goals) if goals is not None else None,
    }


def public_profile_evaluations(db, profile, role=""):
    metrics = db.scalars(
        select(PlayerMatchMetric)
        .where(PlayerMatchMetric.profile_id == profile.id, PlayerMatchMetric.library_match_id.is_not(None))
        .order_by(PlayerMatchMetric.library_match_id.desc())
    ).all()
    grouped = defaultdict(list)
    for metric in metrics:
        grouped[metric.library_match_id].append(metric)

    rows = []
    for library_id, group in grouped.items():
        match = db.get(MatchLibraryItem, library_id)
        if not match:
            continue
        # Recover team name from the canonical library stat if available without
        # adding a duplicate persistence field to PlayerMatchMetric.
        from models import LibraryPlayerMatchStat
        stat = db.scalar(select(LibraryPlayerMatchStat).where(
            LibraryPlayerMatchStat.library_match_id == library_id,
            LibraryPlayerMatchStat.player_name == profile.canonical_name,
        ))
        for metric in group:
            metric._team_name = stat.team_name if stat else ""
        rows.append(evaluate_public_match(match, group, role=role))

    rows.sort(key=lambda r: r["match"].id, reverse=True)
    rated = [r for r in rows if r["overall"] is not None]
    if not rated:
        return {"matches": rows, "summary": {"rated_matches": 0, "goals": 0, "avg_rating": None, "weighted_rating": None, "avg_confidence": 0.0, "best": None}}

    goals = sum(r["goals"] or 0 for r in rated)
    weighted_den = sum(max(.05, r["confidence_score"]) * max(1, r["competition_level"]) for r in rated)
    weighted_rating = round(sum(r["overall"] * max(.05, r["confidence_score"]) * max(1, r["competition_level"]) for r in rated) / weighted_den, 1)
    return {
        "matches": rows,
        "summary": {
            "rated_matches": len(rated),
            "goals": goals,
            "goals_per_match": round(goals / len(rated), 2),
            "avg_rating": round(mean(r["overall"] for r in rated), 1),
            "weighted_rating": weighted_rating,
            "avg_confidence": round(mean(r["confidence_score"] for r in rated), 2),
            "best": max(rated, key=lambda r: r["overall"]),
        },
    }
