import math
import random
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone

# The simulation service is deliberately usable in isolation for unit tests.
# Database-backed enrichment is optional and fails closed to documented priors.
try:
    from sqlalchemy import select
    from db import SessionLocal
    from models import (
        OfficialFixture, OfficialStanding, OfficialTeamStat, MatchLibraryItem,
        LibraryPlayerMatchStat, ScoutingTeam, ScoutingPlayer,
        PlayerIntelligenceProfile, TransferSignal,
    )
except Exception:  # pragma: no cover - isolated simulation tests
    select = None
    SessionLocal = None
    OfficialFixture = OfficialStanding = OfficialTeamStat = MatchLibraryItem = None
    LibraryPlayerMatchStat = ScoutingTeam = ScoutingPlayer = None
    PlayerIntelligenceProfile = TransferSignal = None

# Baseline priors are fallback anchors, never presented as official rankings.
# Database results, standings, roster evidence and current match context replace
# these values whenever enough evidence exists.
_BASE_TEAMS = {
    "Granville Water Polo": {
        "scope": "club", "competition_class": "France · Elite club", "level": 2,
        "strength": 56, "attack": 55, "defence": 54, "goalkeeper": 55, "extra_player": 52,
        "penalty_kill": 52, "transition": 55, "centre": 54, "depth": 51, "experience": 50,
        "cohesion": 61, "discipline": 55, "coverage": 0.48, "pace": 51,
        "history_score": 61, "home_history": 63, "away_history": 56, "recruitment_delta": 0.0, "roster_continuity": 57,
        "recruitment_note": "2026-27 recruitment impact not yet quantified; confirmed additions/departures will update this prior.",
        "roster_status": "PROVISIONAL", "note": "Promoted/current Elite context. The 2025-26 10–2 N1 season informs the historical prior, but is discounted for the move to Elite; 2026-27 roster evidence remains incomplete."
    },
    "Lille UC Métropole Water-Polo": {
        "scope": "club", "competition_class": "France · Elite club", "level": 2,
        "strength": 63, "attack": 64, "defence": 61, "goalkeeper": 62, "extra_player": 63,
        "penalty_kill": 60, "transition": 63, "centre": 60, "depth": 63, "experience": 64,
        "cohesion": 62, "discipline": 58, "coverage": 0.42, "pace": 53,
        "history_score": 68, "home_history": 70, "away_history": 65, "recruitment_delta": 0.0, "roster_continuity": 62,
        "recruitment_note": "Current-season recruitment impact remains provisional until confirmed roster sheets and player-strength links are complete.",
        "roster_status": "PROVISIONAL", "note": "Elite-club prior informed by recent seasons. Current-season roster is incomplete and will be refreshed from official sheets/announcements."
    },
    "Union St-Bruno Bordeaux": {
        "scope": "club", "competition_class": "France · Elite club", "level": 2,
        "strength": 60, "attack": 61, "defence": 58, "goalkeeper": 59, "extra_player": 60,
        "penalty_kill": 57, "transition": 60, "centre": 59, "depth": 59, "experience": 61,
        "cohesion": 60, "discipline": 58, "coverage": 0.38, "pace": 52,
        "history_score": 64, "home_history": 66, "away_history": 61, "recruitment_delta": 0.0, "roster_continuity": 60,
        "recruitment_note": "Recruitment impact is neutral until confirmed signings/departures can be linked to player ratings and roles.",
        "roster_status": "PROVISIONAL", "note": "Elite-club prior informed by recent seasons; current roster and 2026-27 competitive sample still incomplete."
    },
    "France — Women Senior": {
        "scope": "national", "competition_class": "Senior international", "level": 5,
        "strength": 86, "attack": 83, "defence": 85, "goalkeeper": 86, "extra_player": 81,
        "penalty_kill": 82, "transition": 84, "centre": 82, "depth": 88, "experience": 86,
        "cohesion": 82, "discipline": 79, "coverage": 0.74, "pace": 56,
        "history_score": 78, "home_history": 77, "away_history": 76, "recruitment_delta": 0.0, "roster_continuity": 80, "recruitment_note": "National teams use selection changes rather than club recruitment; impact is handled through availability and roster quality.",
        "roster_status": "PARTIAL_CURRENT", "note": "Senior-international prior informed by 2022-26 national-team data; exact match roster remains scenario-dependent."
    },
    "Spain — Women Senior": {
        "scope": "national", "competition_class": "Senior international · world elite", "level": 6,
        "strength": 94, "attack": 94, "defence": 92, "goalkeeper": 91, "extra_player": 94,
        "penalty_kill": 91, "transition": 93, "centre": 92, "depth": 95, "experience": 95,
        "cohesion": 94, "discipline": 88, "coverage": 0.82, "pace": 58,
        "history_score": 94, "home_history": 94, "away_history": 93, "recruitment_delta": 0.0, "roster_continuity": 90, "recruitment_note": "Selection changes are evaluated through roster strength/availability rather than transfer-market impact.",
        "roster_status": "PARTIAL_CURRENT", "note": "World-elite senior international prior; exact event roster and form should replace broad values when available."
    },
    "United States — Women Senior": {
        "scope": "national", "competition_class": "Senior international · world elite", "level": 6,
        "strength": 93, "attack": 93, "defence": 92, "goalkeeper": 94, "extra_player": 93,
        "penalty_kill": 92, "transition": 95, "centre": 90, "depth": 96, "experience": 94,
        "cohesion": 91, "discipline": 87, "coverage": 0.82, "pace": 59,
        "history_score": 93, "home_history": 93, "away_history": 92, "recruitment_delta": 0.0, "roster_continuity": 88, "recruitment_note": "Selection changes are evaluated through roster strength/availability rather than transfer-market impact.",
        "roster_status": "PARTIAL_CURRENT", "note": "World-elite senior international prior; current event roster and recent matches should refine it."
    },
    "France — Women U20": {
        "scope": "national", "competition_class": "U20 international", "level": 4,
        "strength": 74, "attack": 73, "defence": 73, "goalkeeper": 74, "extra_player": 72,
        "penalty_kill": 72, "transition": 76, "centre": 72, "depth": 75, "experience": 67,
        "cohesion": 73, "discipline": 72, "coverage": 0.45, "pace": 56,
        "history_score": 70, "home_history": 70, "away_history": 69, "recruitment_delta": 0.0, "roster_continuity": 65, "recruitment_note": "Youth selections use generation/selection changes instead of recruitment; roster turnover increases uncertainty.",
        "roster_status": "PROVISIONAL", "note": "U20 international prior; upcoming roster is provisional until official selection is published."
    },
    "Spain — Women U20": {
        "scope": "national", "competition_class": "U20 international · elite", "level": 4,
        "strength": 87, "attack": 88, "defence": 85, "goalkeeper": 84, "extra_player": 87,
        "penalty_kill": 85, "transition": 88, "centre": 86, "depth": 88, "experience": 80,
        "cohesion": 86, "discipline": 80, "coverage": 0.68, "pace": 58,
        "history_score": 88, "home_history": 88, "away_history": 87, "recruitment_delta": 0.0, "roster_continuity": 70, "recruitment_note": "Youth roster changes are handled through generation continuity and confirmed selections.",
        "roster_status": "PROVISIONAL", "note": "Elite U20 prior based on recent international benchmarks; next roster remains provisional until confirmed."
    },
    "Hungary — Women U20": {
        "scope": "national", "competition_class": "U20 international · elite", "level": 4,
        "strength": 84, "attack": 84, "defence": 84, "goalkeeper": 83, "extra_player": 85,
        "penalty_kill": 84, "transition": 85, "centre": 84, "depth": 85, "experience": 80,
        "cohesion": 84, "discipline": 80, "coverage": 0.62, "pace": 57,
        "history_score": 85, "home_history": 85, "away_history": 84, "recruitment_delta": 0.0, "roster_continuity": 70, "recruitment_note": "Youth roster changes are handled through generation continuity and confirmed selections.",
        "roster_status": "PROVISIONAL", "note": "Elite U20 prior; roster and tournament-specific form to be refreshed when official data is available."
    },
}

WEIGHTS = {
    "attack": .13, "defence": .13, "goalkeeper": .10, "extra_player": .08,
    "penalty_kill": .08, "transition": .08, "centre": .07, "depth": .08,
    "experience": .07, "cohesion": .07, "discipline": .04,
}

TACTICS = {
    "balanced": {"attack": 0.0, "defence": 0.0, "pace": 0.0},
    "transition": {"attack": 0.35, "defence": -0.12, "pace": 0.7},
    "centre_pressure": {"attack": 0.28, "defence": -0.05, "pace": -0.1},
    "zone_plus_focus": {"attack": 0.24, "defence": -0.04, "pace": 0.0},
    "defence_first": {"attack": -0.18, "defence": 0.32, "pace": -0.8},
}


def _clamp(value, low, high):
    return max(low, min(high, value))


def _norm(value):
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    for token in ("water-polo", "water polo", "wp", "women", "feminin", "feminine", "club"):
        text = text.lower().replace(token, " ")
    return " ".join(text.lower().replace("—", " ").replace("-", " ").split())


def _same_team(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Only accept substring aliases when both labels are specific enough.
    # This prevents e.g. "France Senior" from matching "France U20".
    return min(len(na), len(nb)) >= 8 and (na in nb or nb in na)


def _parse_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    cleaned = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw[:10], fmt)
        except Exception:
            continue
    return None


def _safe_query_all(db, model):
    if db is None or model is None or select is None:
        return []
    try:
        return list(db.scalars(select(model)).all())
    except Exception:
        return []


def _result_rows(db, team_name, limit=10):
    rows = []
    for fixture in _safe_query_all(db, OfficialFixture):
        if fixture.home_score is None or fixture.away_score is None:
            continue
        if _same_team(fixture.home_team, team_name):
            rows.append({
                "opponent": fixture.away_team, "gf": int(fixture.home_score), "ga": int(fixture.away_score),
                "date": fixture.start_text or "", "competition": fixture.competition or "", "season": fixture.season or "",
                "venue": "home", "source": "official_fixture", "source_url": fixture.source_url or "",
            })
        elif _same_team(fixture.away_team, team_name):
            rows.append({
                "opponent": fixture.home_team, "gf": int(fixture.away_score), "ga": int(fixture.home_score),
                "date": fixture.start_text or "", "competition": fixture.competition or "", "season": fixture.season or "",
                "venue": "away", "source": "official_fixture", "source_url": fixture.source_url or "",
            })
    for match in _safe_query_all(db, MatchLibraryItem):
        if match.score_a is None or match.score_b is None:
            continue
        if _same_team(match.team_a, team_name):
            rows.append({
                "opponent": match.team_b, "gf": int(match.score_a), "ga": int(match.score_b),
                "date": "", "competition": match.competition or "", "season": match.season or "",
                "venue": "neutral", "source": "match_library", "source_url": match.official_source_url or "",
            })
        elif _same_team(match.team_b, team_name):
            rows.append({
                "opponent": match.team_a, "gf": int(match.score_b), "ga": int(match.score_a),
                "date": "", "competition": match.competition or "", "season": match.season or "",
                "venue": "neutral", "source": "match_library", "source_url": match.official_source_url or "",
            })
    # Prefer dated official results, then documented library matches.
    def _result_sort_key(row):
        dt = _parse_date(row["date"])
        if dt is not None and getattr(dt, "tzinfo", None) is not None:
            dt = dt.replace(tzinfo=None)
        return (dt or datetime.min, row["source"] == "official_fixture")
    rows.sort(key=_result_sort_key, reverse=True)
    deduped, seen = [], set()
    for row in rows:
        key = (_norm(row["opponent"]), row["gf"], row["ga"], row["date"], row["competition"])
        if key in seen:
            continue
        seen.add(key)
        row["result"] = "W" if row["gf"] > row["ga"] else "L" if row["gf"] < row["ga"] else "D"
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped


def _form_score(results, fallback=50):
    if not results:
        return float(fallback)
    total, weight_sum = 0.0, 0.0
    for idx, row in enumerate(results):
        weight = 0.84 ** idx
        outcome = 1.0 if row["gf"] > row["ga"] else 0.5 if row["gf"] == row["ga"] else 0.0
        margin = math.tanh((row["gf"] - row["ga"]) / 4.0)
        score = 50.0 + (outcome - 0.5) * 44.0 + margin * 8.0
        total += score * weight
        weight_sum += weight
    return round(_clamp(total / max(weight_sum, 0.01), 25, 85), 1)


def _standing_row(db, team_name):
    candidates = [x for x in _safe_query_all(db, OfficialStanding) if _same_team(x.team_name, team_name)]
    if not candidates:
        return None
    candidates.sort(key=lambda x: (str(x.season or ""), str(getattr(x, "updated_at", "") or "")), reverse=True)
    return candidates[0]


def _standing_strength(row, fallback=50):
    if not row or not row.played:
        return float(fallback)
    played = max(1, int(row.played or 0))
    win_rate = int(row.won or 0) / played
    gd_pg = int(row.goal_diff or 0) / played
    return round(_clamp(50 + (win_rate - 0.5) * 32 + _clamp(gd_pg, -6, 6) * 1.6, 28, 92), 1)


def _team_stats(db, team_name):
    rows = [x for x in _safe_query_all(db, OfficialTeamStat) if _same_team(x.team_name, team_name)]
    rows.sort(key=lambda x: str(getattr(x, "updated_at", "") or ""), reverse=True)
    out = {}
    for row in rows:
        key = (row.metric or "").strip().lower()
        if key and key not in out:
            out[key] = float(row.value or 0)
    return out


def _stat_value(stats, tokens, default=None):
    for key, value in stats.items():
        if all(token in key for token in tokens):
            return value
    return default


def _roster_info(db, team_name):
    scouting_teams = [x for x in _safe_query_all(db, ScoutingTeam) if _same_team(x.name, team_name)]
    scouting_teams.sort(key=lambda x: (str(x.season_label or ""), int(x.priority or 0)), reverse=True)
    chosen = scouting_teams[0] if scouting_teams else None
    players = []
    if chosen and select is not None:
        try:
            players = list(db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id == chosen.id)).all())
        except Exception:
            players = []
    profiles = [x for x in _safe_query_all(db, PlayerIntelligenceProfile) if _same_team(x.current_club, team_name) or _same_team(x.current_national_team, team_name)]
    by_name = {}
    for p in players:
        by_name[_norm(p.name)] = {"name": p.name, "role": p.role or "Role to confirm", "source": p.source_quality or "roster"}
    for p in profiles:
        by_name.setdefault(_norm(p.canonical_name), {"name": p.canonical_name, "role": p.role or "Role to confirm", "source": "player intelligence"})
    stat_rows = _safe_query_all(db, LibraryPlayerMatchStat)
    impact_rows = []
    for item in by_name.values():
        related = [x for x in stat_rows if _norm(x.player_name) == _norm(item["name"])]
        matches = len({x.library_match_id for x in related})
        goals = sum(int(x.goals or 0) for x in related)
        saves = sum(int(x.saves or 0) for x in related)
        assists = sum(int(x.assists or 0) for x in related)
        steals = sum(int(x.steals or 0) for x in related)
        role_l = item["role"].lower()
        if "goal" in role_l or "gard" in role_l:
            impact = 2.6 + min(2.0, (saves / max(matches, 1)) / 5.0)
        else:
            impact = 1.1 + min(2.8, (goals / max(matches, 1)) * 0.45 + (assists / max(matches, 1)) * 0.22 + (steals / max(matches, 1)) * 0.16)
            if "centre" in role_l:
                impact += 0.35
        impact_rows.append({
            **item, "matches": matches, "impact": round(_clamp(impact, 1.0, 4.8), 2),
            "evidence": "documented match stats" if matches else "role/roster estimate",
        })
    impact_rows.sort(key=lambda x: (-x["impact"], x["name"]))
    status = chosen.roster_status if chosen else ("PARTIAL_CURRENT" if profiles else "RESEARCH_REQUIRED")
    return {
        "players": impact_rows,
        "count": len(impact_rows),
        "status": status or "RESEARCH_REQUIRED",
        "source_note": (chosen.source_note if chosen else "") or "Roster evidence is incomplete; provisional depth is used.",
    }


def _next_fixture(db, team_a, team_b):
    now = datetime.now(timezone.utc)
    candidates = []
    for f in _safe_query_all(db, OfficialFixture):
        pair = (_same_team(f.home_team, team_a) and _same_team(f.away_team, team_b)) or (_same_team(f.home_team, team_b) and _same_team(f.away_team, team_a))
        if not pair or (f.home_score is not None and f.away_score is not None):
            continue
        dt = _parse_date(f.start_text)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < now:
                continue
        venue = "team_a_home" if _same_team(f.home_team, team_a) else "team_b_home"
        candidates.append((dt or datetime.max.replace(tzinfo=timezone.utc), f, venue))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    _, f, venue = candidates[0]
    return {
        "competition": f.competition or "", "season": f.season or "", "date": f.start_text or "",
        "venue": venue, "official_venue": f.venue or "", "source_url": f.source_url or "",
        "home": f.home_team, "away": f.away_team,
    }


def _rest_and_fatigue(results, next_date=None):
    dated = []
    for row in results:
        dt = _parse_date(row.get("date"))
        if dt is not None:
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            dated.append(dt)
    dated.sort(reverse=True)
    if next_date:
        nd = _parse_date(next_date)
        if nd is not None and nd.tzinfo is not None:
            nd = nd.replace(tzinfo=None)
    else:
        nd = None
    if dated and nd:
        rest = max(0, (nd - dated[0]).days)
    elif len(dated) >= 2:
        rest = max(0, (dated[0] - dated[1]).days)
    else:
        rest = 3
    recent_density = 0
    if dated:
        anchor = nd or dated[0]
        recent_density = sum(1 for d in dated if 0 <= (anchor - d).days <= 12)
    fatigue = 23 + max(0, 3 - rest) * 8 + max(0, recent_density - 2) * 5
    return int(_clamp(rest, 0, 10)), int(_clamp(fatigue, 8, 72))


def _generic_prior(name):
    lowered = name.lower()
    national = any(x in lowered for x in ("women senior", "national", "u20", "u18", "selection", "équipe nationale"))
    base = 68 if national else 56
    level = 4 if national else 2
    return {
        "scope": "national" if national else "club", "competition_class": "International / database team" if national else "Club / database team",
        "level": level, "strength": base, "attack": base, "defence": base, "goalkeeper": base,
        "extra_player": base, "penalty_kill": base, "transition": base, "centre": base, "depth": base,
        "experience": base, "cohesion": base, "discipline": 58, "coverage": 0.24, "pace": 52,
        "history_score": base, "home_history": 55, "away_history": 52, "recruitment_delta": 0.0,
        "roster_continuity": 55, "recruitment_note": "No quantified transfer/selection impact yet.",
        "roster_status": "RESEARCH_REQUIRED", "note": "Automatically discovered team. Public evidence progressively replaces the provisional prior."
    }


def _derive_profile(db, team_name, prior):
    profile = dict(prior)
    results = _result_rows(db, team_name, 10)
    form = _form_score(results, profile.get("history_score", 50))
    standing = _standing_row(db, team_name)
    standing_strength = _standing_strength(standing, profile.get("strength", 50))
    stats = _team_stats(db, team_name)
    roster = _roster_info(db, team_name)
    next_match_rows = [x for x in _safe_query_all(db, OfficialFixture) if (x.home_score is None or x.away_score is None) and (_same_team(x.home_team, team_name) or _same_team(x.away_team, team_name))]
    def _upcoming_key(row):
        dt = _parse_date(row.start_text)
        if dt is not None and getattr(dt, "tzinfo", None) is not None:
            dt = dt.replace(tzinfo=None)
        return dt or datetime.max
    next_match_rows.sort(key=_upcoming_key)
    next_date = next_match_rows[0].start_text if next_match_rows else None
    rest, fatigue = _rest_and_fatigue(results, next_date)

    avg_for = sum(x["gf"] for x in results) / len(results) if results else None
    avg_against = sum(x["ga"] for x in results) / len(results) if results else None
    result_signal = _clamp(50 + ((avg_for or 10.5) - (avg_against or 10.5)) * 2.0, 30, 85) if results else profile.get("strength", 50)
    evidence_count = len(results) + (1 if standing else 0) + len(stats) + min(roster["count"], 13) / 3
    coverage = _clamp(max(float(profile.get("coverage", 0.2)), 0.20 + min(0.64, evidence_count * 0.035)), 0.20, 0.95)

    base_strength = float(profile.get("strength", 50))
    strength = base_strength * 0.40 + standing_strength * 0.24 + form * 0.20 + result_signal * 0.16
    attack_metric = _stat_value(stats, ("goal", "for"), avg_for)
    defence_metric = _stat_value(stats, ("goal", "against"), avg_against)
    if attack_metric is not None:
        attack_signal = _clamp(44 + (float(attack_metric) - 8) * 4.0, 35, 94)
    else:
        attack_signal = strength
    if defence_metric is not None:
        defence_signal = _clamp(82 - (float(defence_metric) - 7) * 4.2, 34, 94)
    else:
        defence_signal = strength

    profile["strength"] = round(_clamp(strength, 28, 96), 1)
    profile["attack"] = round(_clamp(float(profile.get("attack", strength)) * .56 + attack_signal * .44, 28, 96), 1)
    profile["defence"] = round(_clamp(float(profile.get("defence", strength)) * .56 + defence_signal * .44, 28, 96), 1)
    profile["goalkeeper"] = round(_clamp(float(profile.get("goalkeeper", strength)) * .72 + defence_signal * .28, 28, 96), 1)
    profile["extra_player"] = round(_clamp(float(profile.get("extra_player", strength)) * .70 + profile["attack"] * .30, 28, 96), 1)
    profile["penalty_kill"] = round(_clamp(float(profile.get("penalty_kill", strength)) * .70 + profile["defence"] * .30, 28, 96), 1)
    profile["transition"] = round(_clamp(float(profile.get("transition", strength)) * .72 + form * .28, 28, 96), 1)
    profile["depth"] = round(_clamp(float(profile.get("depth", strength)) * .70 + min(90, 42 + roster["count"] * 3.3) * .30, 28, 96), 1)
    profile["history_score"] = round(standing_strength * .58 + result_signal * .42, 1)
    profile["recent_form"] = form
    profile["avg_for"] = round(avg_for, 2) if avg_for is not None else round(9.4 + profile["attack"] / 40, 2)
    profile["avg_against"] = round(avg_against, 2) if avg_against is not None else round(13.2 - profile["defence"] / 35, 2)
    profile["rest_days"] = rest
    profile["fatigue"] = fatigue
    profile["coverage"] = round(coverage, 3)
    profile["recent_results"] = results
    profile["roster_players"] = roster["players"]
    profile["roster_status"] = roster["status"] if roster["count"] else profile.get("roster_status", "RESEARCH_REQUIRED")
    profile["data_status"] = "CONFIRMED_HEAVY" if coverage >= .78 else "PARTIAL_PUBLIC" if coverage >= .48 else "PROVISIONAL"
    profile["note"] = f"Auto profile: {len(results)} recent documented results; standing {'found' if standing else 'not found'}; roster {roster['status']}."
    return profile


class SimulationTeamRegistry(dict):
    """Lazy registry: every team already present in official/scouting data becomes selectable."""

    def __init__(self, initial):
        super().__init__({k: dict(v) for k, v in initial.items()})
        self._base_names = set(initial)
        self._last_refresh = 0.0
        self._refreshing = False

    def _refresh(self, force=False):
        if self._refreshing or SessionLocal is None or select is None:
            return
        if not force and time.monotonic() - self._last_refresh < 45:
            return
        self._refreshing = True
        db = None
        try:
            db = SessionLocal()
            names = set(dict.keys(self))
            def add_name(candidate):
                candidate = (candidate or "").strip()
                if not candidate:
                    return
                if any(_same_team(candidate, existing) for existing in names):
                    return
                names.add(candidate)
            for row in _safe_query_all(db, ScoutingTeam):
                add_name(row.name)
            for row in _safe_query_all(db, OfficialStanding):
                add_name(row.team_name)
            for row in _safe_query_all(db, OfficialFixture):
                add_name(row.home_team)
                add_name(row.away_team)
            for row in _safe_query_all(db, MatchLibraryItem):
                add_name(row.team_a)
                add_name(row.team_b)
            for name in sorted(names):
                current = dict.get(self, name)
                if current is None:
                    current = next((dict(v) for k, v in _BASE_TEAMS.items() if _same_team(k, name)), _generic_prior(name))
                dict.__setitem__(self, name, _derive_profile(db, name, current))
            self._last_refresh = time.monotonic()
        except Exception:
            self._last_refresh = time.monotonic()
        finally:
            if db is not None:
                db.close()
            self._refreshing = False

    def __contains__(self, key):
        self._refresh()
        if dict.__contains__(self, key):
            return True
        normalized = _norm(key)
        return any(_norm(k) == normalized for k in dict.keys(self))

    def __getitem__(self, key):
        self._refresh()
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        for name in dict.keys(self):
            if _same_team(name, key):
                return dict.__getitem__(self, name)
        raise KeyError(key)

    def __iter__(self):
        self._refresh()
        return iter(sorted(dict.keys(self), key=lambda x: (0 if "Granville" in x else 1, x.lower())))

    def keys(self):
        self._refresh()
        return list(iter(self))


SIM_TEAMS = SimulationTeamRegistry(_BASE_TEAMS)


def _poisson(lam, rng):
    L = math.exp(-max(0.05, lam))
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


def _metric_strength(team):
    return sum(float(team.get(k, 50)) * w for k, w in WEIGHTS.items()) / sum(WEIGHTS.values())


def _effective_strength(team, availability=100, form=50, rest=3, home=False, away=False):
    metric = _metric_strength(team)
    history = float(team.get("history_score", team.get("strength", 50)))
    continuity = float(team.get("roster_continuity", 60))
    recruitment = _clamp(float(team.get("recruitment_delta", 0.0)), -3.0, 3.0)
    s = float(team.get("strength", 50)) * 0.52 + metric * 0.29 + history * 0.11 + continuity * 0.04
    s += float(form) * .04 - 2.0
    s += recruitment
    s += (max(50, min(100, availability)) - 100) * 0.11
    fatigue = float(team.get("fatigue", 30))
    s -= max(0, fatigue - 28) * .045
    if rest <= 0:
        s -= 1.5
    elif rest == 1:
        s -= 0.8
    elif rest >= 5:
        s += 0.15
    if home:
        s += (float(team.get("home_history", 55)) - 50) * 0.045
    elif away:
        s += (float(team.get("away_history", 50)) - 50) * 0.035
    return s


def _recommend_tactic(team, opponent):
    candidates = {}
    for tactic in TACTICS:
        candidates[tactic] = _plan_matchup_bonus(team, opponent, tactic)
    # Balanced remains preferred when another plan has no meaningful edge.
    best = max(candidates, key=candidates.get)
    return best if candidates[best] >= candidates["balanced"] + .06 else "balanced"


def _plan_matchup_bonus(team, opponent, tactic):
    base = TACTICS.get(tactic, TACTICS["balanced"])
    bonus = base["attack"] + base["defence"]
    if tactic == "transition":
        bonus += (float(team.get("transition", 50)) - float(opponent.get("transition", 50))) / 100 * 0.55
    elif tactic == "centre_pressure":
        bonus += (float(team.get("centre", 50)) - float(opponent.get("defence", 50))) / 100 * 0.55
    elif tactic == "zone_plus_focus":
        bonus += (float(team.get("extra_player", 50)) - float(opponent.get("penalty_kill", 50))) / 100 * 0.55
    elif tactic == "defence_first":
        bonus += (float(team.get("defence", 50)) + float(team.get("goalkeeper", 50)) - float(opponent.get("attack", 50)) * 2) / 200 * 0.50
    return _clamp(bonus, -0.55, 0.55)


def _refresh_pair_from_db(team_a, team_b):
    if isinstance(SIM_TEAMS, SimulationTeamRegistry):
        SIM_TEAMS._refresh(force=True)
    if SessionLocal is None:
        return None
    db = None
    try:
        db = SessionLocal()
        return _next_fixture(db, team_a, team_b)
    except Exception:
        return None
    finally:
        if db is not None:
            db.close()


def _validation_snapshot(db, competition="", limit=28):
    rows = [x for x in _safe_query_all(db, OfficialFixture) if x.home_score is not None and x.away_score is not None]
    if competition:
        same = [x for x in rows if x.competition == competition]
        if len(same) >= 6:
            rows = same
    rows = rows[-limit:]
    correct = tested = 0
    for f in rows:
        try:
            home = SIM_TEAMS[f.home_team]
            away = SIM_TEAMS[f.away_team]
        except Exception:
            continue
        predicted = float(home.get("strength", 50)) + 1.0 - float(away.get("strength", 50))
        actual = int(f.home_score) - int(f.away_score)
        if actual == 0:
            continue
        tested += 1
        correct += (predicted > 0 and actual > 0) or (predicted < 0 and actual < 0)
    accuracy = round(correct / tested * 100, 1) if tested else None
    return {
        "sample": tested, "direction_accuracy": accuracy,
        "label": f"Contrôle rétrospectif sur {tested} résultats publics" if tested else "Contrôle rétrospectif indisponible.",
    }


def _season_projection(db, focus_team, context, n=1200, seed=313):
    if not context or not context.get("competition") or not context.get("season"):
        return {"available": False, "reason": "Aucun calendrier officiel commun suffisamment identifié."}
    competition, season = context["competition"], context["season"]
    fixtures = [x for x in _safe_query_all(db, OfficialFixture) if x.competition == competition and x.season == season]
    standings = [x for x in _safe_query_all(db, OfficialStanding) if x.competition == competition and x.season == season]
    team_names = set()
    for f in fixtures:
        team_names.update([f.home_team, f.away_team])
    for s in standings:
        team_names.add(s.team_name)
    if len(team_names) < 3:
        return {"available": False, "reason": "Calendrier/participants incomplets pour projeter la compétition."}
    canonical_focus = next((x for x in team_names if _same_team(x, focus_team)), focus_team)
    base_points = {name: 0 for name in team_names}
    if standings:
        for row in standings:
            base_points[row.team_name] = int(row.points or 0)
    else:
        for f in fixtures:
            if f.home_score is None or f.away_score is None:
                continue
            if f.home_score > f.away_score:
                base_points[f.home_team] += 3
            elif f.away_score > f.home_score:
                base_points[f.away_team] += 3
            else:
                base_points[f.home_team] += 1
                base_points[f.away_team] += 1
    remaining = [f for f in fixtures if f.home_score is None or f.away_score is None]
    if not remaining:
        ordered = sorted(base_points, key=lambda x: (-base_points[x], x))
        rank = ordered.index(canonical_focus) + 1 if canonical_focus in ordered else None
        return {
            "available": True, "competition": competition, "season": season, "simulations": 0,
            "title": 100.0 if rank == 1 else 0.0, "top3": 100.0 if rank and rank <= 3 else 0.0,
            "playoffs": 100.0 if rank and rank <= min(4, len(ordered)) else 0.0,
            "survival": 100.0 if rank and rank <= max(1, len(ordered) - 2) else 0.0,
            "average_rank": float(rank) if rank else None, "remaining_matches": 0,
        }
    strengths = {}
    for name in team_names:
        try:
            strengths[name] = float(SIM_TEAMS[name]["strength"])
        except Exception:
            strengths[name] = 50.0
    rng = random.Random(seed)
    title = top3 = playoffs = survival = 0
    rank_sum = 0
    playoff_cut = min(4, len(team_names))
    survival_cut = max(1, len(team_names) - 2)
    for _ in range(n):
        pts = dict(base_points)
        for f in remaining:
            sh, sa = strengths.get(f.home_team, 50), strengths.get(f.away_team, 50)
            p_home = 1.0 / (1.0 + math.exp(-(sh - sa + 1.1) / 7.2))
            draw_p = 0.08 + max(0.0, 0.06 - abs(sh - sa) * 0.004)
            roll = rng.random()
            if roll < draw_p:
                pts[f.home_team] += 1
                pts[f.away_team] += 1
            elif roll < draw_p + (1 - draw_p) * p_home:
                pts[f.home_team] += 3
            else:
                pts[f.away_team] += 3
        ordered = sorted(pts, key=lambda x: (-pts[x], -strengths.get(x, 50), x))
        rank = ordered.index(canonical_focus) + 1 if canonical_focus in ordered else len(ordered)
        rank_sum += rank
        title += rank == 1
        top3 += rank <= 3
        playoffs += rank <= playoff_cut
        survival += rank <= survival_cut
    return {
        "available": True, "competition": competition, "season": season, "simulations": n,
        "title": round(title / n * 100, 1), "top3": round(top3 / n * 100, 1),
        "playoffs": round(playoffs / n * 100, 1), "survival": round(survival / n * 100, 1),
        "average_rank": round(rank_sum / n, 2), "remaining_matches": len(remaining),
    }


def simulate_matchup(team_a, team_b, tactic_a="balanced", tactic_b="balanced", n=5000, seed=17,
                     availability_a=100, availability_b=100, form_a=50, form_b=50,
                     rest_a=3, rest_b=3, venue="neutral"):
    """
    Automatic manager simulation.

    The public UI only asks for teams and absences. `availability_a/b` are the
    machine-readable consequence of those absences; form, rest, venue and
    tactics are recalculated from the database and the old manual parameters
    are intentionally ignored.
    """
    # The legacy route still passes 5,000; upgrade the live product to 25,000
    # without slowing unit tests that explicitly request another sample size.
    if int(n) == 5000:
        n = 25000
    n = int(_clamp(int(n), 1000, 50000))

    context = _refresh_pair_from_db(team_a, team_b)
    a = SIM_TEAMS[team_a]
    b = SIM_TEAMS[team_b]

    # All performance/context parameters are automatic.
    auto_venue = context["venue"] if context else "neutral"
    auto_form_a = float(a.get("recent_form", a.get("history_score", 50)))
    auto_form_b = float(b.get("recent_form", b.get("history_score", 50)))
    auto_rest_a = int(a.get("rest_days", 3))
    auto_rest_b = int(b.get("rest_days", 3))
    tactic_a = _recommend_tactic(a, b)
    tactic_b = _recommend_tactic(b, a)
    availability_a = int(_clamp(availability_a, 50, 100))
    availability_b = int(_clamp(availability_b, 50, 100))

    sa = _effective_strength(a, availability_a, auto_form_a, auto_rest_a, auto_venue == "team_a_home", auto_venue == "team_b_home")
    sb = _effective_strength(b, availability_b, auto_form_b, auto_rest_b, auto_venue == "team_b_home", auto_venue == "team_a_home")

    level_gap = int(a.get("level", 2)) - int(b.get("level", 2))
    if abs(level_gap) >= 2:
        gate = math.copysign(1.35 * (abs(level_gap) ** 1.35), level_gap)
        sa += max(0.0, gate)
        sb += max(0.0, -gate)

    ta = _plan_matchup_bonus(a, b, tactic_a)
    tb = _plan_matchup_bonus(b, a, tactic_b)
    rating_diff = sa - sb
    expected_margin = 11.8 * math.tanh(rating_diff / 25.5) + (ta - tb) * 0.85

    pace = (float(a.get("pace", 52)) + float(b.get("pace", 52))) / 2
    total = 20.5 + (pace - 52) * 0.16 + (TACTICS[tactic_a]["pace"] + TACTICS[tactic_b]["pace"]) * 0.28
    total = _clamp(total, 15.5, 25.5)
    structural_a = _clamp((total + expected_margin) / 2, 2.0, 20.0)
    structural_b = _clamp((total - expected_margin) / 2, 2.0, 20.0)

    recent_a = _clamp((float(a.get("avg_for", structural_a)) + float(b.get("avg_against", structural_a))) / 2, 3.0, 19.0)
    recent_b = _clamp((float(b.get("avg_for", structural_b)) + float(a.get("avg_against", structural_b))) / 2, 3.0, 19.0)
    form_goal_a = _clamp(10.3 + (auto_form_a - auto_form_b) / 18.0, 4.0, 17.0)
    form_goal_b = _clamp(10.3 + (auto_form_b - auto_form_a) / 18.0, 4.0, 17.0)

    # Ensemble: structural class model + empirical scoring + recent-form model.
    lam_a = structural_a * 0.54 + recent_a * 0.31 + form_goal_a * 0.15
    lam_b = structural_b * 0.54 + recent_b * 0.31 + form_goal_b * 0.15
    if auto_venue == "team_a_home":
        lam_a += 0.28
        lam_b -= 0.10
    elif auto_venue == "team_b_home":
        lam_b += 0.28
        lam_a -= 0.10
    lam_a, lam_b = _clamp(lam_a, 1.6, 21.0), _clamp(lam_b, 1.6, 21.0)

    coverage = min(float(a.get("coverage", .25)), float(b.get("coverage", .25)))
    uncertainty = 0.06 + (1 - coverage) * 0.15
    uncertainty += (float(a.get("fatigue", 30)) + float(b.get("fatigue", 30))) / 2000.0
    rng = random.Random(seed)
    scores, aw, bw, draws = [], 0, 0, 0
    score_counts = Counter()
    for _ in range(n):
        shared = _clamp(rng.gauss(1.0, uncertainty * 0.55), 0.70, 1.32)
        shock_a = _clamp(rng.gauss(1.0, uncertainty), 0.68, 1.34)
        shock_b = _clamp(rng.gauss(1.0, uncertainty), 0.68, 1.34)
        xa = _poisson(lam_a * shared * shock_a, rng)
        xb = _poisson(lam_b * shared * shock_b, rng)
        scores.append((xa, xb))
        score_counts[(xa, xb)] += 1
        if xa > xb:
            aw += 1
        elif xb > xa:
            bw += 1
        else:
            draws += 1

    avg_a = sum(x[0] for x in scores) / n
    avg_b = sum(x[1] for x in scores) / n
    diffs = sorted(x[0] - x[1] for x in scores)
    lo, med, hi = diffs[int(.10 * n)], diffs[int(.50 * n)], diffs[min(n - 1, int(.90 * n))]
    cross_level = abs(int(a.get("level", 2)) - int(b.get("level", 2))) >= 2
    top_scores = [
        {"score": f"{sa_}–{sb_}", "probability": round(count / n * 100, 2), "count": count}
        for (sa_, sb_), count in score_counts.most_common(8)
    ]
    context_penalty = 0 if context else 5
    confidence = int(round(_clamp(46 + coverage * 47 - context_penalty + min(5, len(a.get("recent_results", [])) + len(b.get("recent_results", []))) * .5, 42, 93)))

    factor_rows = [
        ("Classe / niveau", a.get("competition_class", "—"), b.get("competition_class", "—"), round(rating_diff, 1)),
        ("Historical results prior", a.get("history_score", "—"), b.get("history_score", "—"), round((float(a.get("history_score", 50)) - float(b.get("history_score", 50))) * .10, 1)),
        ("Home/away history", a.get("home_history" if auto_venue == "team_a_home" else "away_history", "—"), b.get("home_history" if auto_venue == "team_b_home" else "away_history", "—"), 0.0),
        ("Recruitment / selection impact", a.get("recruitment_delta", 0.0), b.get("recruitment_delta", 0.0), round(float(a.get("recruitment_delta", 0.0)) - float(b.get("recruitment_delta", 0.0)), 1)),
        ("Roster continuity", a.get("roster_continuity", "—"), b.get("roster_continuity", "—"), round((float(a.get("roster_continuity", 60)) - float(b.get("roster_continuity", 60))) * .04, 1)),
        ("Forme automatique (10 derniers max)", auto_form_a, auto_form_b, round((auto_form_a - auto_form_b) * .09, 1)),
        ("Buts marqués récents / match", a.get("avg_for", "—"), b.get("avg_for", "—"), round(float(a.get("avg_for", 10.5)) - float(b.get("avg_for", 10.5)), 1)),
        ("Buts encaissés récents / match", a.get("avg_against", "—"), b.get("avg_against", "—"), round(float(b.get("avg_against", 10.5)) - float(a.get("avg_against", 10.5)), 1)),
        ("Repos calculé", f"{auto_rest_a} j", f"{auto_rest_b} j", round((auto_rest_a - auto_rest_b) * .18, 1)),
        ("Fatigue calculée", f"{a.get('fatigue', 30)} /100", f"{b.get('fatigue', 30)} /100", round((float(b.get("fatigue", 30)) - float(a.get("fatigue", 30))) * .025, 1)),
        ("Absences / disponibilité", f"{availability_a}%", f"{availability_b}%", round((availability_a - availability_b) * .11, 1)),
        ("Gardienne", a.get("goalkeeper", 50), b.get("goalkeeper", 50), round((float(a.get("goalkeeper", 50)) - float(b.get("goalkeeper", 50))) * .10, 1)),
        ("Supériorité numérique", a.get("extra_player", 50), b.get("extra_player", 50), round((float(a.get("extra_player", 50)) - float(b.get("extra_player", 50))) * .08, 1)),
        ("Infériorité numérique", a.get("penalty_kill", 50), b.get("penalty_kill", 50), round((float(a.get("penalty_kill", 50)) - float(b.get("penalty_kill", 50))) * .08, 1)),
        ("Transition", a.get("transition", 50), b.get("transition", 50), round((float(a.get("transition", 50)) - float(b.get("transition", 50))) * .08, 1)),
        ("Profondeur d'effectif", a.get("depth", 50), b.get("depth", 50), round((float(a.get("depth", 50)) - float(b.get("depth", 50))) * .08, 1)),
        ("Couverture des données", f"{round(float(a.get('coverage', 0))*100)}%", f"{round(float(b.get('coverage', 0))*100)}%", 0.0),
    ]

    validation = {"sample": 0, "direction_accuracy": None, "label": "Contrôle rétrospectif indisponible."}
    season_a = {"available": False, "reason": "Projection compétition indisponible."}
    season_b = {"available": False, "reason": "Projection compétition indisponible."}
    if SessionLocal is not None:
        db = None
        try:
            db = SessionLocal()
            competition = context.get("competition", "") if context else ""
            validation = _validation_snapshot(db, competition)
            season_a = _season_projection(db, team_a, context, n=1200, seed=seed + 101)
            season_b = _season_projection(db, team_b, context, n=1200, seed=seed + 202)
        except Exception:
            pass
        finally:
            if db is not None:
                db.close()

    return {
        "team_a": team_a, "team_b": team_b,
        "avg_a": round(avg_a, 1), "avg_b": round(avg_b, 1),
        "win_a": round(aw / n * 100, 2), "win_b": round(bw / n * 100, 2), "draw": round(draws / n * 100, 2),
        "diff_interval": [lo, hi], "median_diff": med, "coverage": round(coverage * 100), "confidence": confidence, "n": n,
        "strength_a": round(sa, 1), "strength_b": round(sb, 1), "class_gap": abs(int(a.get("level", 2)) - int(b.get("level", 2))),
        "cross_level": cross_level, "factor_rows": factor_rows,
        "tactic_a": tactic_a, "tactic_b": tactic_b,
        "roster_status_a": a.get("roster_status", "RESEARCH_REQUIRED"), "roster_status_b": b.get("roster_status", "RESEARCH_REQUIRED"),
        "recruitment_note_a": a.get("recruitment_note", "No recruitment context available."),
        "recruitment_note_b": b.get("recruitment_note", "No recruitment context available."),
        "top_scores": top_scores,
        "scenarios": {
            "pessimistic_a": lo, "central_a": med, "optimistic_a": hi,
            "label": "Écart de buts équipe A aux percentiles 10 / 50 / 90."
        },
        "context": context,
        "auto_inputs": {
            "form_a": auto_form_a, "form_b": auto_form_b,
            "rest_a": auto_rest_a, "rest_b": auto_rest_b,
            "fatigue_a": a.get("fatigue", 30), "fatigue_b": b.get("fatigue", 30),
            "venue": auto_venue, "availability_a": availability_a, "availability_b": availability_b,
        },
        "recent_results_a": a.get("recent_results", []), "recent_results_b": b.get("recent_results", []),
        "roster_a": a.get("roster_players", []), "roster_b": b.get("roster_players", []),
        "data_status_a": a.get("data_status", "PROVISIONAL"), "data_status_b": b.get("data_status", "PROVISIONAL"),
        "validation": validation, "season_a": season_a, "season_b": season_b,
        "disclaimer": (
            "Projection probabiliste de management, pas une certitude ni un conseil de pari. "
            "Forme, fatigue, repos, contexte, niveau et plan tactique sont calculés automatiquement à partir des résultats "
            "et données disponibles. La seule correction utilisateur principale est l'absence d'une ou plusieurs joueuses. "
            "Les valeurs provisoires sont explicitement signalées et l'incertitude augmente lorsque les données publiques sont partielles."
        ),
    }
