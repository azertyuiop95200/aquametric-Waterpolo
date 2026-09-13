import json
import re
from collections import defaultdict
from statistics import mean

from sqlalchemy import func, select

from intelligence_models import PlayerMatchEvaluation
from models import (
    Match,
    Player,
    PlayerIntelligenceProfile,
    PlayerShotObservation,
    ScoutingPlayer,
    ScoutingTeam,
)
from services.public_match_ratings import DIMENSIONS, public_profile_evaluations


# Players with documented senior exposure in official/high-trust sources already
# attached to the AquaMetric research set or the 2026 tournament reporting.
SENIOR_EXPERIENCE = {
    "Kata Hajdu",
    "Carlota Penalver",
    "Queralt Anton",
    "Neli Jankovic",
    "Lara Srhoj",
    "Panna Tiba",
}

OFFICIAL_VIDEO_CATALOG = {
    ("U16", "Spain"): [
        ("U16 final vs Greece", "https://www.worldaquatics.com/videos/4539420/gold-medal-match-world-aquatics-womens-u16-water-polo-championships-2026"),
        ("U16 semifinal vs Netherlands", "https://www.worldaquatics.com/videos/4539402/esp-vs-ned-semi-final-1-day-6-world-aquatics-womens-u16-water-polo-championships-2026"),
    ],
    ("U16", "Greece"): [
        ("U16 final vs Spain", "https://www.worldaquatics.com/videos/4539420/gold-medal-match-world-aquatics-womens-u16-water-polo-championships-2026"),
        ("U16 semifinal vs Hungary", "https://www.worldaquatics.com/videos/4539422/hun-vs-gre-semi-final-2-day-6-world-aquatics-womens-u16-water-polo-championships-2026"),
    ],
    ("U16", "Hungary"): [
        ("U16 semifinal vs Greece", "https://www.worldaquatics.com/videos/4539422/hun-vs-gre-semi-final-2-day-6-world-aquatics-womens-u16-water-polo-championships-2026"),
    ],
    ("U16", "Netherlands"): [
        ("U16 semifinal vs Spain", "https://www.worldaquatics.com/videos/4539402/esp-vs-ned-semi-final-1-day-6-world-aquatics-womens-u16-water-polo-championships-2026"),
    ],
    ("U18", "Spain"): [
        ("U18 final vs Australia", "https://www.worldaquatics.com/videos/4557235/gold-medal-match-world-aquatics-womens-u18-water-polo-championships-2026"),
        ("U18 semifinal vs Hungary", "https://www.worldaquatics.com/videos/4557224/semi-final-2-day-7-world-aquatics-womens-u18-water-polo-championships-2026"),
        ("U18 quarterfinal vs Canada", "https://www.worldaquatics.com/videos/4557212/quarter-final-4-day-6-world-aquatics-womens-u18-water-polo-championships-2026"),
    ],
    ("U18", "Hungary"): [
        ("U18 semifinal vs Spain", "https://www.worldaquatics.com/videos/4557224/semi-final-2-day-7-world-aquatics-womens-u18-water-polo-championships-2026"),
        ("U18 quarterfinal vs China", "https://www.worldaquatics.com/videos/4557187/quarter-final-2-day-6-world-aquatics-womens-u18-water-polo-championships-2026"),
    ],
    ("U18", "Greece"): [
        ("U18 quarterfinal vs Australia", "https://www.worldaquatics.com/videos/4557185/quarter-final-1-day-6-world-aquatics-womens-u18-water-polo-championships-2026"),
    ],
    ("U18", "Netherlands"): [
        ("U18 quarterfinal vs USA", "https://www.worldaquatics.com/videos/4557210/quarter-final-3-day-6-world-aquatics-womens-u18-water-polo-championships-2026"),
    ],
}


def _clamp(value, low=25.0, high=95.0):
    return round(max(low, min(high, value)), 1)


def _weighted_mean(pairs):
    pairs = [(float(value), max(0.01, float(weight))) for value, weight in pairs if value is not None]
    if not pairs:
        return None
    den = sum(weight for _, weight in pairs)
    return round(sum(value * weight for value, weight in pairs) / den, 1)


def _parse_number(pattern, text):
    match = re.search(pattern, text or "", flags=re.IGNORECASE)
    return float(match.group(1).replace(",", ".")) if match else None


def _parse_scout_row(row, team):
    text = " ".join([row.role or "", row.note or ""])
    legacy = _parse_number(r"(\d+(?:[.,]\d+)?)\s*/\s*15", text)
    total = _parse_number(r"Total connu à date:\s*(\d+(?:[.,]\d+)?)", text)
    peak_goals = _parse_number(r"Pic buts/match:\s*(\d+(?:[.,]\d+)?)", text)
    peak_saves = _parse_number(r"Pic arrêts/match:\s*(\d+(?:[.,]\d+)?)", text)
    distinction = ""
    match = re.search(r"Distinction:\s*(.+?)(?:\.\s|$)", row.note or "", flags=re.IGNORECASE)
    if match:
        distinction = match.group(1).strip()
    return {
        "row": row,
        "team": team,
        "age_group": team.age_group,
        "country": team.country,
        "legacy": legacy,
        "total": total,
        "peak_goals": peak_goals,
        "peak_saves": peak_saves,
        "distinction": distinction,
        "text": text,
        "source_url": row.source_url or team.source_url or "",
    }


def _production_score(records, goalkeeper=False):
    totals = [r["total"] for r in records if r["total"] is not None]
    peaks = [r["peak_saves"] if goalkeeper else r["peak_goals"] for r in records]
    peaks = [p for p in peaks if p is not None and p > 0]
    total = max(totals) if totals else None
    peak = max(peaks) if peaks else None

    total_score = None
    if total is not None:
        if goalkeeper:
            total_score = _clamp(55 + min(34, total * 1.25))
        elif total >= 23:
            total_score = 92
        elif total >= 20:
            total_score = 89
        elif total >= 16:
            total_score = 85
        elif total >= 12:
            total_score = 80
        elif total >= 8:
            total_score = 74
        elif total >= 5:
            total_score = 68
        else:
            total_score = _clamp(54 + total * 2.2)

    peak_score = None
    if peak is not None:
        if goalkeeper:
            if peak >= 12:
                peak_score = 90
            elif peak >= 10:
                peak_score = 85
            elif peak >= 8:
                peak_score = 79
            elif peak >= 5:
                peak_score = 69
            else:
                peak_score = _clamp(52 + peak * 3.0)
        else:
            if peak >= 7:
                peak_score = 85
            elif peak >= 6:
                peak_score = 81
            elif peak >= 5:
                peak_score = 77
            elif peak >= 4:
                peak_score = 72
            elif peak >= 3:
                peak_score = 67
            elif peak >= 2:
                peak_score = 61
            else:
                peak_score = 56

    if total_score is not None and peak_score is not None:
        return round(total_score * .68 + peak_score * .32, 1)
    return total_score if total_score is not None else peak_score


def _recognition_score(records):
    best = None
    for rec in records:
        d = (rec["distinction"] or "").lower()
        t = rec["text"].lower()
        score = None
        if "mvp officielle" in d or ("mvp" in d and "autre compétition" not in d):
            score = 96
        elif "meilleure gardienne" in d or "best goalkeeper" in d:
            score = 94
        elif "all-star" in d or "all star" in d:
            score = 90
        elif "mvp" in t:
            score = 84
        if score is not None:
            best = max(best or score, score)
    return best


def _clutch_score(records, goalkeeper=False):
    best = None
    for rec in records:
        t = rec["text"].lower()
        signal = rec["peak_saves"] if goalkeeper else rec["peak_goals"]
        signal = signal or 0
        if "finale" in t or "final " in t:
            score = 78 + min(12, signal * 1.5)
        elif "demi" in t or "semi" in t:
            score = 73 + min(12, signal * 1.5)
        elif "quart" in t:
            score = 69 + min(11, signal * 1.4)
        elif signal >= (8 if goalkeeper else 5):
            score = 66 + min(10, signal)
        else:
            score = None
        if score is not None:
            best = max(best or score, score)
    return _clamp(best) if best is not None else None


def _consistency_score(records):
    if not records:
        return None
    score = 54 + min(18, (len(records) - 1) * 8)
    if any(r["total"] is not None and r["total"] >= 12 for r in records):
        score += 9
    text = " ".join(r["text"].lower() for r in records)
    if text.count(";") >= 2 or "puis" in text or "deux matches" in text:
        score += 7
    if len({r["age_group"] for r in records}) >= 2:
        score += 7
    return _clamp(score)


def _progression_score(profile, records):
    ages = {r["age_group"] for r in records}
    name = profile.canonical_name
    role_text = " ".join(r["text"].lower() for r in records)
    if name in SENIOR_EXPERIENCE or "senior international" in role_text:
        return 92
    if len(ages) >= 2:
        return 84
    if "U20" in ages:
        return 68
    if "U18" in ages:
        return 64
    return 59


def _context_score(profile, records):
    role = (profile.role or "") + " " + " ".join(r["row"].role or "" for r in records)
    goalkeeper = any(k in role.lower() for k in ("goalkeeper", "keeper", "gard"))
    legacy = [r["legacy"] for r in records if r["legacy"] is not None]
    legacy_prior = _clamp(45 + max(legacy) * 3.2) if legacy else None
    components = {
        "production": _production_score(records, goalkeeper=goalkeeper),
        "recognition": _recognition_score(records),
        "big_match_impact": _clutch_score(records, goalkeeper=goalkeeper),
        "consistency": _consistency_score(records),
        "progression": _progression_score(profile, records),
        "legacy_prior": legacy_prior,
    }
    weights = {
        "production": .25,
        "recognition": .20,
        "big_match_impact": .18,
        "consistency": .17,
        "progression": .12,
        "legacy_prior": .08,
    }
    available = [(components[k], weights[k]) for k in components if components[k] is not None]
    raw = _weighted_mean(available)
    confidence = .34 + min(.16, len(records) * .045)
    if components["recognition"] is not None:
        confidence += .10
    if any(r["total"] is not None for r in records):
        confidence += .08
    if len({r["age_group"] for r in records}) >= 2 or profile.canonical_name in SENIOR_EXPERIENCE:
        confidence += .10
    return raw, round(min(.80, confidence), 2), components, goalkeeper


def _public_dimension_means(public):
    pairs = defaultdict(list)
    for row in public["matches"]:
        if row["overall"] is None:
            continue
        weight = max(.05, row["confidence_score"]) * max(1, row["competition_level"])
        for name, value in row["dimensions"].items():
            if value is not None:
                pairs[name].append((value, weight))
    return {name: _weighted_mean(pairs.get(name, [])) for name in DIMENSIONS}


def _video_evaluations(db, profile, user_id):
    rows = db.execute(
        select(PlayerMatchEvaluation, Match)
        .join(Player, PlayerMatchEvaluation.player_id == Player.id)
        .join(Match, PlayerMatchEvaluation.match_id == Match.id)
        .where(
            func.lower(Player.name) == profile.canonical_name.lower(),
            Match.owner_id == user_id,
            PlayerMatchEvaluation.overall.is_not(None),
        )
        .order_by(PlayerMatchEvaluation.generated_at.desc())
    ).all()
    if not rows:
        return {
            "overall": None,
            "confidence": 0.0,
            "matches": 0,
            "dimensions": {d: None for d in DIMENSIONS},
        }
    overall = _weighted_mean([
        (evaluation.overall, max(.05, evaluation.confidence_score))
        for evaluation, _ in rows
    ])
    dimensions = {}
    for dim in DIMENSIONS:
        dimensions[dim] = _weighted_mean([
            (getattr(evaluation, dim), max(.05, evaluation.confidence_score))
            for evaluation, _ in rows
            if getattr(evaluation, dim) is not None
        ])
    avg_conf = mean(max(0.0, evaluation.confidence_score) for evaluation, _ in rows)
    sample = min(1.0, len(rows) / 4.0)
    confidence = round(min(.96, avg_conf * (.70 + .30 * sample)), 2)
    return {
        "overall": overall,
        "confidence": confidence,
        "matches": len(rows),
        "dimensions": dimensions,
    }


def _shot_evidence(db, profile_id):
    rows = db.scalars(
        select(PlayerShotObservation).where(PlayerShotObservation.profile_id == profile_id)
    ).all()
    located = [r for r in rows if r.outcome in {"goal", "save", "block", "miss"}]
    if len(located) < 3:
        return {"score": None, "confidence": 0.0, "shots": len(located)}
    goals = sum(r.outcome == "goal" for r in located)
    conversion = goals / len(located)
    avg_conf = mean(max(0.0, r.confidence_score) for r in located)
    score = _clamp(45 + conversion * 38 + min(8, len(located) * .6))
    confidence = round(min(.90, avg_conf * min(1.0, len(located) / 8.0)), 2)
    return {"score": score, "confidence": confidence, "shots": len(located)}


def stars_for_score(score):
    if score is None:
        return 0.0
    if score >= 90:
        return 5.0
    if score >= 85:
        return 4.5
    if score >= 80:
        return 4.0
    if score >= 75:
        return 3.5
    if score >= 70:
        return 3.0
    if score >= 65:
        return 2.5
    if score >= 60:
        return 2.0
    if score >= 55:
        return 1.5
    return 1.0


def _star_text(stars):
    full = int(stars)
    half = stars - full >= .5
    return "★" * full + ("½" if half else "") + "☆" * (5 - full - (1 if half else 0))


def _band(score):
    if score is None:
        return "NON ÉVALUÉE"
    if score >= 88:
        return "PROSPECT ÉLITE"
    if score >= 82:
        return "TRÈS HAUT POTENTIEL"
    if score >= 76:
        return "HAUT POTENTIEL"
    if score >= 69:
        return "FORTE À SUIVRE"
    if score >= 62:
        return "À SUIVRE"
    return "PROFIL À ENRICHIR"


def _available_videos(records):
    seen = set()
    items = []
    for rec in records:
        for label, url in OFFICIAL_VIDEO_CATALOG.get((rec["age_group"], rec["country"]), []):
            if url in seen:
                continue
            seen.add(url)
            items.append({"label": label, "url": url})
    return items


def build_prospect_evaluation(db, profile, scout_rows, user_id):
    team_ids = {row.scouting_team_id for row in scout_rows}
    teams = {
        team.id: team for team in db.scalars(
            select(ScoutingTeam).where(ScoutingTeam.id.in_(team_ids))
        ).all()
    } if team_ids else {}
    records = [
        _parse_scout_row(row, teams[row.scouting_team_id])
        for row in scout_rows
        if row.scouting_team_id in teams
        and teams[row.scouting_team_id].external_key.startswith("eu-youth-2026-")
    ]
    if not records:
        return None

    context_raw, context_conf, context_components, goalkeeper = _context_score(profile, records)
    public = public_profile_evaluations(db, profile, role=profile.role)
    pub = public["summary"]
    public_score = pub.get("weighted_rating")
    public_conf = 0.0
    if public_score is not None:
        public_conf = round(
            min(.92, (pub.get("avg_confidence", 0.0) * .65) + (pub.get("sample_reliability", 0.0) * .35)),
            2,
        )
    video = _video_evaluations(db, profile, user_id)
    shot = _shot_evidence(db, profile.id)

    blocks = []
    if context_raw is not None:
        blocks.append(("context", context_raw, .35, context_conf))
    if public_score is not None:
        blocks.append(("public", public_score, .25, public_conf))
    if video["overall"] is not None:
        blocks.append(("video", video["overall"], .35, video["confidence"]))
    if shot["score"] is not None:
        blocks.append(("shot", shot["score"], .05, shot["confidence"]))

    raw_overall = _weighted_mean([(score, weight) for _, score, weight, _ in blocks])
    confidence = _weighted_mean([(conf * 100, weight) for _, _, weight, conf in blocks])
    confidence = (confidence or 0) / 100
    evidence_count = len(records) + int(pub.get("documented_matches", 0)) + video["matches"]
    confidence = round(min(.96, confidence + min(.10, evidence_count * .012)), 2)
    shrink = .64 + .36 * confidence
    overall = round(50 + ((raw_overall or 50) - 50) * shrink, 1) if raw_overall is not None else None

    public_dims = _public_dimension_means(public)
    dimensions = {}
    dimension_sources = {}
    for dim in DIMENSIONS:
        candidates = []
        if public_dims.get(dim) is not None:
            candidates.append((public_dims[dim], max(.10, public_conf), "public stats"))
        if video["dimensions"].get(dim) is not None:
            candidates.append((video["dimensions"][dim], max(.10, video["confidence"]) * 1.25, "tagged/video"))
        if dim == "technique" and shot["score"] is not None:
            candidates.append((shot["score"], max(.08, shot["confidence"]), "shot map"))
        if dim == "attack" and not goalkeeper and context_components["production"] is not None:
            candidates.append((context_components["production"], .18, "tournament production"))
        if dim == "defence" and goalkeeper and context_components["production"] is not None:
            candidates.append((context_components["production"], .25, "goalkeeper production"))
        if dim == "impact" and context_components["big_match_impact"] is not None:
            candidates.append((context_components["big_match_impact"], .18, "big-match context"))
        dimensions[dim] = _weighted_mean([(value, weight) for value, weight, _ in candidates])
        dimension_sources[dim] = [source for _, _, source in candidates]

    covered_dimensions = sum(value is not None for value in dimensions.values())
    videos = _available_videos(records)
    source_urls = []
    for rec in records:
        if rec["source_url"] and rec["source_url"] not in source_urls:
            source_urls.append(rec["source_url"])

    stars = stars_for_score(overall)
    return {
        "profile_id": profile.id,
        "name": profile.canonical_name,
        "nationality": profile.nationality,
        "role": profile.role,
        "overall": overall,
        "raw_overall": raw_overall,
        "stars": stars,
        "star_text": _star_text(stars),
        "band": _band(overall),
        "confidence_score": confidence,
        "confidence_label": "ÉLEVÉE" if confidence >= .78 else ("SOLIDE" if confidence >= .60 else ("MODÉRÉE" if confidence >= .42 else "FAIBLE")),
        "age_groups": sorted({r["age_group"] for r in records}),
        "countries": sorted({r["country"] for r in records}),
        "context_components": context_components,
        "dimensions": dimensions,
        "dimension_sources": dimension_sources,
        "covered_dimensions": covered_dimensions,
        "public_matches": int(pub.get("documented_matches", 0)),
        "public_rated_matches": int(pub.get("rated_matches", 0)),
        "video_analyzed_matches": video["matches"],
        "official_video_sources": videos,
        "shot_observations": shot["shots"],
        "scouting_records": len(records),
        "evidence_count": evidence_count,
        "source_urls": source_urls,
        "public_summary": pub,
        "engine_version": "prospect-rating-v4",
        "physical": None,
        "physical_note": "Non noté sans tracking calibré: vitesse de nage, distance, répétition d'efforts et fatigue ne sont pas déduites de la réputation.",
    }


def eu_youth_prospect_rows(db, user_id):
    scout_rows = db.execute(
        select(ScoutingPlayer, ScoutingTeam)
        .join(ScoutingTeam, ScoutingPlayer.scouting_team_id == ScoutingTeam.id)
        .where(ScoutingTeam.external_key.like("eu-youth-2026-%"))
    ).all()
    grouped = defaultdict(list)
    for player, team in scout_rows:
        grouped[player.name].append(player)

    profiles = {
        profile.canonical_name: profile
        for profile in db.scalars(
            select(PlayerIntelligenceProfile).where(
                PlayerIntelligenceProfile.canonical_name.in_(list(grouped))
            )
        ).all()
    }
    result = []
    for name, rows in grouped.items():
        profile = profiles.get(name)
        if not profile:
            continue
        evaluation = build_prospect_evaluation(db, profile, rows, user_id)
        if evaluation:
            result.append(evaluation)
    result.sort(key=lambda row: (row["overall"] is not None, row["overall"] or 0, row["confidence_score"]), reverse=True)
    for idx, row in enumerate(result, start=1):
        row["rank"] = idx
    return result
