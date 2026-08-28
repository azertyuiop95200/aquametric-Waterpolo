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
OFFICIAL_TIERS = {"federation_official", "official", "official_report", "official_match_sheet", "world_aquatics"}


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
    for alias in ("lille", "granville"):
        if alias in player_team.lower():
            if alias in (match.team_a or "").lower():
                return match.score_a
            if alias in (match.team_b or "").lower():
                return match.score_b
    return None


def _result(match, player_team):
    total = _team_total(match, player_team)
    if total is None or match.score_a is None or match.score_b is None:
        return "unknown"
    if player_team == match.team_a:
        opp = match.score_b
    elif player_team == match.team_b:
        opp = match.score_a
    else:
        opp = None
        for alias in ("lille", "granville"):
            if alias in (player_team or "").lower():
                if alias in (match.team_a or "").lower():
                    opp = match.score_b
                elif alias in (match.team_b or "").lower():
                    opp = match.score_a
                break
        if opp is None:
            return "unknown"
    return "win" if total > opp else ("loss" if total < opp else "draw")


def _public_reliability(coverage, evidence_families, source_tier, scorer_complete):
    # Public box scores are intrinsically partial. Even an official goals-only sheet
    # cannot carry the same amplitude as tagged full-match evidence.
    reliability = .18 + coverage * .34 + min(.24, evidence_families * .07)
    if source_tier in OFFICIAL_TIERS:
        reliability += .07
    if scorer_complete:
        reliability += .06
    return round(min(.82, reliability), 3)


def _confidence(coverage, evidence_families, source_tier, scorer_complete, appearance_verified):
    if not appearance_verified and not evidence_families:
        return 0.0
    value = .10 + coverage * .36 + min(.24, evidence_families * .08)
    if source_tier in OFFICIAL_TIERS:
        value += .10
    if scorer_complete:
        value += .08
    return round(min(.92, value), 2)


def _confidence_label(overall, confidence):
    if overall is None:
        return "PRESENCE"
    if confidence < .35:
        return "LOW SAMPLE"
    if confidence < .60:
        return "MODERATE"
    if confidence < .80:
        return "STRONG"
    return "HIGH"


def _rating_band(overall, confidence):
    if overall is None:
        return "UNRATED"
    if confidence < .35:
        return "PROVISIONAL"
    if overall >= 70:
        return "STRONG PARTIAL EVIDENCE"
    if overall >= 57:
        return "POSITIVE PARTIAL EVIDENCE"
    if overall >= 44:
        return "BALANCED / MIXED"
    return "NEGATIVE PARTIAL EVIDENCE"


def evaluate_public_match(match, metrics, role=""):
    """Rate only dimensions directly supported by a public source.

    Missing dimensions stay None. The /100 is a partial-evidence indicator, not a
    full player grade: amplitude is reliability-shrunk toward 50 according to the
    breadth of published statistics and source completeness.
    """
    by_metric = {m.metric: m for m in metrics}
    values = {k: (by_metric[k].value if k in by_metric else None) for k in ("goals", "shots", "assists", "steals", "saves", "exclusions")}
    meta = _meta(match)
    source_tier = meta.get("source_tier", "official_report")
    level = int(meta.get("competition_level", 3) or 3)
    appearance_verified = "appearance" in by_metric or meta.get("evidence_scope") == "official_match_sheet_lineup"
    player_team = next((getattr(m, "_team_name", None) for m in metrics if getattr(m, "_team_name", None)), None)
    if not player_team:
        player_team = getattr(metrics[0], "team_name", "") if metrics else ""
    completeness_by_team = meta.get("scorer_list_complete_by_team") or {}
    scorer_complete = bool(completeness_by_team.get(player_team, meta.get("scorer_list_complete", False)))
    team_total = _team_total(match, player_team)
    goals = values["goals"]
    share = (float(goals) / float(team_total)) if goals is not None and team_total else None
    result = _result(match, player_team)

    dims = {d: None for d in DIMENSIONS}
    evidence_families = 0
    published = []
    if appearance_verified:
        published.append("official match-sheet appearance")

    if goals is not None:
        evidence_families += 1
        share_bonus = min(11.0, (share or 0.0) * 38.0)
        difficulty = max(-1.5, min(3.5, (level - 3) * 1.4))
        win_bonus = 1.0 if result == "win" else (-.4 if result == "loss" else 0.0)
        dims["attack"] = _clamp(49 + min(23.0, float(goals) * 3.7) + share_bonus + difficulty + win_bonus)
        dims["impact"] = _clamp(48 + min(22.0, float(goals) * 3.1) + min(12.0, (share or 0.0) * 42.0) + difficulty + win_bonus)
        published.append(f"{int(goals)} goal(s)")

    shots = values["shots"]
    if shots is not None:
        evidence_families += 1
        efficiency = (float(goals or 0) / float(shots)) if shots else 0.0
        dims["technique"] = _clamp(44 + efficiency * 46)
        dims["decision"] = _clamp(45 + efficiency * 36)
        published.append(f"{int(shots)} shot(s)")

    assists = values["assists"]
    if assists is not None:
        evidence_families += 1
        dims["decision"] = _clamp((dims["decision"] or 50) + min(16, assists * 4.5))
        dims["tactics"] = _clamp(50 + min(18, assists * 3.8))
        dims["attack"] = _clamp((dims["attack"] or 50) + min(10, assists * 2.2))
        published.append(f"{int(assists)} assist(s)")

    steals = values["steals"]
    if steals is not None:
        evidence_families += 1
        dims["defence"] = _clamp(50 + min(22, steals * 5.5))
        dims["transition"] = _clamp(50 + min(20, steals * 5.0))
        dims["decision"] = _clamp((dims["decision"] or 50) + min(10, steals * 2.6))
        published.append(f"{int(steals)} steal(s)")

    saves = values["saves"]
    if saves is not None:
        evidence_families += 1
        dims["defence"] = _clamp(48 + min(32, saves * 3.0))
        dims["technique"] = _clamp(48 + min(28, saves * 2.6))
        dims["impact"] = _clamp((dims["impact"] or 50) + min(23, saves * 2.2))
        published.append(f"{int(saves)} save(s)")

    exclusions = values["exclusions"]
    if exclusions is not None:
        evidence_families += 1
        dims["discipline"] = _clamp(60 - exclusions * 7.0)
        published.append(f"{int(exclusions)} exclusion(s)")

    available = [d for d, score in dims.items() if score is not None]
    coverage = round(len(available) / len(DIMENSIONS), 2)
    weights = ROLE_WEIGHTS[_role_key(role)]
    denom = sum(weights[d] for d in available)
    raw_overall = sum(dims[d] * weights[d] for d in available) / denom if denom else None
    reliability = _public_reliability(coverage, evidence_families, source_tier, scorer_complete)
    overall = round(50 + (raw_overall - 50) * reliability, 1) if raw_overall is not None else None

    confidence = _confidence(coverage, evidence_families, source_tier, scorer_complete, appearance_verified)
    confidence_label = _confidence_label(overall, confidence)
    unavailable = [d for d in DIMENSIONS if dims[d] is None]
    if evidence_families >= 3:
        scope = "fuller public stat line"
    elif evidence_families >= 2:
        scope = "multi-stat public evidence"
    elif evidence_families == 1:
        scope = "single-stat public evidence"
    else:
        scope = "official lineup presence only"
    return {
        "match": match,
        "overall": overall,
        "raw_overall": round(raw_overall, 1) if raw_overall is not None else None,
        "dimensions": dims,
        "coverage": coverage,
        "reliability": reliability,
        "confidence_score": confidence,
        "confidence_label": confidence_label,
        "rating_band": _rating_band(overall, confidence),
        "evidence_families": evidence_families,
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
        "appearance_verified": appearance_verified,
        "engine_version": "public-rating-v3",
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
    goals = sum(r["goals"] or 0 for r in rows)
    summary = {
        "documented_matches": len(rows),
        "rated_matches": len(rated),
        "appearance_only_matches": sum(r["overall"] is None and r["appearance_verified"] for r in rows),
        "goals": goals,
        "goals_per_match": round(goals / len(rated), 2) if rated else None,
        "avg_rating": None,
        "weighted_rating": None,
        "raw_weighted_rating": None,
        "avg_confidence": 0.0,
        "sample_reliability": 0.0,
        "best": None,
        "engine_version": "public-rating-v3",
    }
    if rated:
        weighted_den = sum(max(.05, r["confidence_score"]) * max(1, r["competition_level"]) for r in rated)
        raw_weighted = sum(r["overall"] * max(.05, r["confidence_score"]) * max(1, r["competition_level"]) for r in rated) / weighted_den
        sample_reliability = min(1.0, len(rated) / 8.0)
        profile_shrink = .55 + .45 * sample_reliability
        weighted_rating = 50 + (raw_weighted - 50) * profile_shrink
        summary.update({
            "avg_rating": round(mean(r["overall"] for r in rated), 1),
            "raw_weighted_rating": round(raw_weighted, 1),
            "weighted_rating": round(weighted_rating, 1),
            "avg_confidence": round(mean(r["confidence_score"] for r in rated), 2),
            "sample_reliability": round(sample_reliability, 2),
            "best": max(rated, key=lambda r: r["overall"]),
        })
    return {"matches": rows, "summary": summary}
