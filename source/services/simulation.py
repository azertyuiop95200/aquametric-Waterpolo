import math
import random
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone

try:
    from sqlalchemy import select
    from db import SessionLocal
    from models import (
        OfficialFixture,
        OfficialStanding,
        OfficialTeamStat,
        MatchLibraryItem,
        LibraryPlayerMatchStat,
        ScoutingTeam,
        ScoutingPlayer,
        PlayerIntelligenceProfile,
    )
except Exception:  # pragma: no cover - isolated unit tests can use priors
    select = None
    SessionLocal = None
    OfficialFixture = OfficialStanding = OfficialTeamStat = MatchLibraryItem = None
    LibraryPlayerMatchStat = ScoutingTeam = ScoutingPlayer = None
    PlayerIntelligenceProfile = None


# Fallback priors are only anchors. As soon as public results, standings and
# roster evidence exist in the database, those signals progressively replace
# the prior. They are not presented as official rankings.
BASE_TEAMS = {
    "Granville Water Polo": {
        "scope": "club", "competition_class": "France · Elite club", "level": 2,
        "strength": 56, "attack": 55, "defence": 54, "goalkeeper": 55,
        "extra_player": 52, "penalty_kill": 52, "transition": 55, "centre": 54,
        "depth": 51, "experience": 50, "cohesion": 61, "discipline": 55,
        "coverage": .48, "pace": 51, "history_score": 61,
        "home_history": 63, "away_history": 56, "roster_continuity": 57,
        "recruitment_delta": 0.0,
        "recruitment_note": "2026-27 recruitment impact is neutral until confirmed additions/departures are linked to player evidence.",
        "roster_status": "PROVISIONAL",
    },
    "Lille UC Métropole Water-Polo": {
        "scope": "club", "competition_class": "France · Elite club", "level": 2,
        "strength": 63, "attack": 64, "defence": 61, "goalkeeper": 62,
        "extra_player": 63, "penalty_kill": 60, "transition": 63, "centre": 60,
        "depth": 63, "experience": 64, "cohesion": 62, "discipline": 58,
        "coverage": .42, "pace": 53, "history_score": 68,
        "home_history": 70, "away_history": 65, "roster_continuity": 62,
        "recruitment_delta": 0.0,
        "recruitment_note": "Current-season recruitment impact remains provisional until confirmed roster evidence is complete.",
        "roster_status": "PROVISIONAL",
    },
    "Union St-Bruno Bordeaux": {
        "scope": "club", "competition_class": "France · Elite club", "level": 2,
        "strength": 60, "attack": 61, "defence": 58, "goalkeeper": 59,
        "extra_player": 60, "penalty_kill": 57, "transition": 60, "centre": 59,
        "depth": 59, "experience": 61, "cohesion": 60, "discipline": 58,
        "coverage": .38, "pace": 52, "history_score": 64,
        "home_history": 66, "away_history": 61, "roster_continuity": 60,
        "recruitment_delta": 0.0,
        "recruitment_note": "Recruitment impact is neutral until confirmed signings/departures are linked to player evidence.",
        "roster_status": "PROVISIONAL",
    },
    "France — Women Senior": {
        "scope": "national", "competition_class": "Senior international", "level": 5,
        "strength": 86, "attack": 83, "defence": 85, "goalkeeper": 86,
        "extra_player": 81, "penalty_kill": 82, "transition": 84, "centre": 82,
        "depth": 88, "experience": 86, "cohesion": 82, "discipline": 79,
        "coverage": .74, "pace": 56, "history_score": 78,
        "home_history": 77, "away_history": 76, "roster_continuity": 80,
        "recruitment_delta": 0.0,
        "recruitment_note": "National teams use selection changes rather than club recruitment.",
        "roster_status": "PARTIAL_CURRENT",
    },
    "Spain — Women Senior": {
        "scope": "national", "competition_class": "Senior international · world elite", "level": 6,
        "strength": 94, "attack": 94, "defence": 92, "goalkeeper": 91,
        "extra_player": 94, "penalty_kill": 91, "transition": 93, "centre": 92,
        "depth": 95, "experience": 95, "cohesion": 94, "discipline": 88,
        "coverage": .82, "pace": 58, "history_score": 94,
        "home_history": 94, "away_history": 93, "roster_continuity": 90,
        "recruitment_delta": 0.0,
        "recruitment_note": "Selection changes are evaluated through roster strength and availability.",
        "roster_status": "PARTIAL_CURRENT",
    },
    "United States — Women Senior": {
        "scope": "national", "competition_class": "Senior international · world elite", "level": 6,
        "strength": 93, "attack": 93, "defence": 92, "goalkeeper": 94,
        "extra_player": 93, "penalty_kill": 92, "transition": 95, "centre": 90,
        "depth": 96, "experience": 94, "cohesion": 91, "discipline": 87,
        "coverage": .82, "pace": 59, "history_score": 93,
        "home_history": 93, "away_history": 92, "roster_continuity": 88,
        "recruitment_delta": 0.0,
        "recruitment_note": "Selection changes are evaluated through roster strength and availability.",
        "roster_status": "PARTIAL_CURRENT",
    },
    "France — Women U20": {
        "scope": "national", "competition_class": "U20 international", "level": 4,
        "strength": 74, "attack": 73, "defence": 73, "goalkeeper": 74,
        "extra_player": 72, "penalty_kill": 72, "transition": 76, "centre": 72,
        "depth": 75, "experience": 67, "cohesion": 73, "discipline": 72,
        "coverage": .45, "pace": 56, "history_score": 70,
        "home_history": 70, "away_history": 69, "roster_continuity": 65,
        "recruitment_delta": 0.0,
        "recruitment_note": "Youth selections are evaluated through generation continuity and confirmed selections.",
        "roster_status": "PROVISIONAL",
    },
    "Spain — Women U20": {
        "scope": "national", "competition_class": "U20 international · elite", "level": 4,
        "strength": 87, "attack": 88, "defence": 85, "goalkeeper": 84,
        "extra_player": 87, "penalty_kill": 85, "transition": 88, "centre": 86,
        "depth": 88, "experience": 80, "cohesion": 86, "discipline": 80,
        "coverage": .68, "pace": 58, "history_score": 88,
        "home_history": 88, "away_history": 87, "roster_continuity": 70,
        "recruitment_delta": 0.0,
        "recruitment_note": "Youth selections are evaluated through generation continuity and confirmed selections.",
        "roster_status": "PROVISIONAL",
    },
    "Hungary — Women U20": {
        "scope": "national", "competition_class": "U20 international · elite", "level": 4,
        "strength": 84, "attack": 84, "defence": 84, "goalkeeper": 83,
        "extra_player": 85, "penalty_kill": 84, "transition": 85, "centre": 84,
        "depth": 85, "experience": 80, "cohesion": 84, "discipline": 80,
        "coverage": .62, "pace": 57, "history_score": 85,
        "home_history": 85, "away_history": 84, "roster_continuity": 70,
        "recruitment_delta": 0.0,
        "recruitment_note": "Youth selections are evaluated through generation continuity and confirmed selections.",
        "roster_status": "PROVISIONAL",
    },
}

WEIGHTS = {
    "attack": .13, "defence": .13, "goalkeeper": .10, "extra_player": .08,
    "penalty_kill": .08, "transition": .08, "centre": .07, "depth": .08,
    "experience": .07, "cohesion": .07, "discipline": .04,
}

TACTICS = {
    "balanced": {"attack": 0.0, "defence": 0.0, "pace": 0.0},
    "transition": {"attack": .35, "defence": -.12, "pace": .7},
    "centre_pressure": {"attack": .28, "defence": -.05, "pace": -.1},
    "zone_plus_focus": {"attack": .24, "defence": -.04, "pace": 0.0},
    "defence_first": {"attack": -.18, "defence": .32, "pace": -.8},
}


def _clamp(value, low, high):
    return max(low, min(high, value))


def _norm(value):
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower().replace("—", " ").replace("-", " ")
    for token in ("water polo", "waterpolo", "wp", "women", "feminin", "feminine", "club"):
        text = text.replace(token, " ")
    return " ".join(text.split())


def _same_team(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Do not merge broad country aliases across age groups (Senior/U20/U18).
    return min(len(na), len(nb)) >= 8 and (na in nb or nb in na)


def _parse_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw[:10], fmt)
        except Exception:
            continue
    return None


def _safe_all(db, model):
    if db is None or model is None or select is None:
        return []
    try:
        return list(db.scalars(select(model)).all())
    except Exception:
        return []


def _generic_prior(name):
    lowered = name.lower()
    national = any(x in lowered for x in (" senior", "u20", "u18", "national", "selection"))
    base = 68 if national else 56
    return {
        "scope": "national" if national else "club",
        "competition_class": "International / database team" if national else "Club / database team",
        "level": 4 if national else 2,
        "strength": base, "attack": base, "defence": base, "goalkeeper": base,
        "extra_player": base, "penalty_kill": base, "transition": base, "centre": base,
        "depth": base, "experience": base, "cohesion": base, "discipline": 58,
        "coverage": .24, "pace": 52, "history_score": base,
        "home_history": 55, "away_history": 52, "roster_continuity": 55,
        "recruitment_delta": 0.0, "roster_status": "RESEARCH_REQUIRED",
        "recruitment_note": "No quantified recruitment/selection impact yet.",
    }


def _fresh_prior(name):
    for canonical, prior in BASE_TEAMS.items():
        if _same_team(canonical, name):
            return dict(prior)
    return _generic_prior(name)


def _recent_results(db, team_name, limit=10):
    rows = []
    for f in _safe_all(db, OfficialFixture):
        if f.home_score is None or f.away_score is None:
            continue
        if _same_team(f.home_team, team_name):
            rows.append({
                "opponent": f.away_team, "gf": int(f.home_score), "ga": int(f.away_score),
                "date": f.start_text or "", "competition": f.competition or "",
                "season": f.season or "", "venue": "home", "source": "official_fixture",
                "source_url": f.source_url or "",
            })
        elif _same_team(f.away_team, team_name):
            rows.append({
                "opponent": f.home_team, "gf": int(f.away_score), "ga": int(f.home_score),
                "date": f.start_text or "", "competition": f.competition or "",
                "season": f.season or "", "venue": "away", "source": "official_fixture",
                "source_url": f.source_url or "",
            })
    for m in _safe_all(db, MatchLibraryItem):
        if m.score_a is None or m.score_b is None:
            continue
        if _same_team(m.team_a, team_name):
            rows.append({
                "opponent": m.team_b, "gf": int(m.score_a), "ga": int(m.score_b),
                "date": "", "competition": m.competition or "", "season": m.season or "",
                "venue": "neutral", "source": "match_library",
                "source_url": m.official_source_url or "",
            })
        elif _same_team(m.team_b, team_name):
            rows.append({
                "opponent": m.team_a, "gf": int(m.score_b), "ga": int(m.score_a),
                "date": "", "competition": m.competition or "", "season": m.season or "",
                "venue": "neutral", "source": "match_library",
                "source_url": m.official_source_url or "",
            })

    rows.sort(
        key=lambda r: (_parse_date(r["date"]) or datetime.min, r["source"] == "official_fixture"),
        reverse=True,
    )
    out, seen = [], set()
    for row in rows:
        key = (_norm(row["opponent"]), row["gf"], row["ga"], row["date"], row["competition"])
        if key in seen:
            continue
        seen.add(key)
        row["result"] = "W" if row["gf"] > row["ga"] else "L" if row["gf"] < row["ga"] else "D"
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _form_score(results, fallback=50):
    if not results:
        return float(fallback)
    weighted = weight_sum = 0.0
    for idx, row in enumerate(results):
        weight = .84 ** idx
        outcome = 1.0 if row["gf"] > row["ga"] else .5 if row["gf"] == row["ga"] else 0.0
        margin = math.tanh((row["gf"] - row["ga"]) / 4.0)
        score = 50 + (outcome - .5) * 44 + margin * 8
        weighted += score * weight
        weight_sum += weight
    return round(_clamp(weighted / max(.01, weight_sum), 25, 85), 1)


def _standing_for(db, team_name):
    rows = [x for x in _safe_all(db, OfficialStanding) if _same_team(x.team_name, team_name)]
    rows.sort(key=lambda x: (str(x.season or ""), str(x.updated_at or "")), reverse=True)
    return rows[0] if rows else None


def _standing_strength(row, fallback):
    if not row or not row.played:
        return float(fallback)
    played = max(1, int(row.played))
    win_rate = int(row.won or 0) / played
    gd_pg = int(row.goal_diff or 0) / played
    return _clamp(50 + (win_rate - .5) * 32 + _clamp(gd_pg, -6, 6) * 1.6, 28, 92)


def _team_stats(db, team_name):
    rows = [x for x in _safe_all(db, OfficialTeamStat) if _same_team(x.team_name, team_name)]
    rows.sort(key=lambda x: str(x.updated_at or ""), reverse=True)
    values = {}
    for row in rows:
        key = (row.metric or "").strip().lower()
        if key and key not in values:
            values[key] = float(row.value or 0)
    return values


def _roster_info(db, team_name):
    teams = [x for x in _safe_all(db, ScoutingTeam) if _same_team(x.name, team_name)]
    teams.sort(key=lambda x: (str(x.season_label or ""), int(x.priority or 0)), reverse=True)
    chosen = teams[0] if teams else None
    players = []
    if chosen and select is not None:
        try:
            players = list(db.scalars(
                select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id == chosen.id)
            ).all())
        except Exception:
            players = []

    profiles = [
        x for x in _safe_all(db, PlayerIntelligenceProfile)
        if _same_team(x.current_club, team_name) or _same_team(x.current_national_team, team_name)
    ]
    merged = {}
    for p in players:
        merged[_norm(p.name)] = {
            "name": p.name, "role": p.role or "Role to confirm",
            "source": p.source_quality or "roster",
        }
    for p in profiles:
        merged.setdefault(_norm(p.canonical_name), {
            "name": p.canonical_name, "role": p.role or "Role to confirm",
            "source": "player intelligence",
        })

    stat_rows = _safe_all(db, LibraryPlayerMatchStat)
    enriched = []
    for item in merged.values():
        related = [x for x in stat_rows if _norm(x.player_name) == _norm(item["name"])]
        matches = len({x.library_match_id for x in related})
        goals = sum(int(x.goals or 0) for x in related)
        assists = sum(int(x.assists or 0) for x in related)
        steals = sum(int(x.steals or 0) for x in related)
        saves = sum(int(x.saves or 0) for x in related)
        role = item["role"].lower()
        if "goal" in role or "gard" in role:
            impact = 2.6 + min(2.0, saves / max(matches, 1) / 5.0)
        else:
            impact = 1.1 + min(
                2.8,
                goals / max(matches, 1) * .45
                + assists / max(matches, 1) * .22
                + steals / max(matches, 1) * .16,
            )
            if "centre" in role:
                impact += .35
        enriched.append({
            **item, "matches": matches,
            "impact": round(_clamp(impact, 1.0, 4.8), 2),
            "evidence": "documented match stats" if matches else "role/roster estimate",
        })
    enriched.sort(key=lambda x: (-x["impact"], x["name"]))
    status = (
        (chosen.roster_status if chosen else "")
        or ("PARTIAL_CURRENT" if profiles else "RESEARCH_REQUIRED")
    )
    return {"players": enriched, "status": status, "count": len(enriched)}


def _next_fixture(db, team_a, team_b):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    candidates = []
    for f in _safe_all(db, OfficialFixture):
        pair = (
            (_same_team(f.home_team, team_a) and _same_team(f.away_team, team_b))
            or (_same_team(f.home_team, team_b) and _same_team(f.away_team, team_a))
        )
        if not pair or (f.home_score is not None and f.away_score is not None):
            continue
        dt = _parse_date(f.start_text)
        if dt and dt < now:
            continue
        venue = "team_a_home" if _same_team(f.home_team, team_a) else "team_b_home"
        candidates.append((dt or datetime.max, f, venue))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    _, f, venue = candidates[0]
    return {
        "competition": f.competition or "", "season": f.season or "",
        "date": f.start_text or "", "venue": venue,
        "official_venue": f.venue or "", "source_url": f.source_url or "",
        "home": f.home_team, "away": f.away_team,
    }


def _rest_fatigue(results, next_date=None):
    dates = [_parse_date(x.get("date")) for x in results]
    dates = sorted([x for x in dates if x], reverse=True)
    next_dt = _parse_date(next_date)
    if dates and next_dt:
        rest = max(0, (next_dt - dates[0]).days)
    elif len(dates) >= 2:
        rest = max(0, (dates[0] - dates[1]).days)
    else:
        rest = 3
    anchor = next_dt or (dates[0] if dates else None)
    density = sum(1 for d in dates if anchor and 0 <= (anchor - d).days <= 12)
    fatigue = 23 + max(0, 3 - rest) * 8 + max(0, density - 2) * 5
    return int(_clamp(rest, 0, 10)), int(_clamp(fatigue, 8, 72))


def _derive_profile(db, team_name, prior):
    p = dict(prior)
    results = _recent_results(db, team_name, 10)
    standing = _standing_for(db, team_name)
    roster = _roster_info(db, team_name)
    stats = _team_stats(db, team_name)
    form = _form_score(results, p.get("history_score", p.get("strength", 50)))
    table_strength = _standing_strength(standing, p.get("strength", 50))

    avg_for = sum(x["gf"] for x in results) / len(results) if results else None
    avg_against = sum(x["ga"] for x in results) / len(results) if results else None
    margin_signal = (
        _clamp(50 + (avg_for - avg_against) * 2.0, 30, 85)
        if results else float(p.get("strength", 50))
    )

    strength = (
        float(p.get("strength", 50)) * .45
        + table_strength * .22
        + form * .19
        + margin_signal * .14
    )

    attack_signal = _clamp(44 + ((avg_for or 10.5) - 8) * 4, 35, 94)
    defence_signal = _clamp(82 - ((avg_against or 10.5) - 7) * 4.2, 34, 94)
    p["strength"] = round(_clamp(strength, 28, 96), 1)
    p["attack"] = round(_clamp(float(p.get("attack", strength)) * .60 + attack_signal * .40, 28, 96), 1)
    p["defence"] = round(_clamp(float(p.get("defence", strength)) * .60 + defence_signal * .40, 28, 96), 1)
    p["goalkeeper"] = round(_clamp(float(p.get("goalkeeper", strength)) * .75 + defence_signal * .25, 28, 96), 1)
    p["extra_player"] = round(_clamp(float(p.get("extra_player", strength)) * .72 + p["attack"] * .28, 28, 96), 1)
    p["penalty_kill"] = round(_clamp(float(p.get("penalty_kill", strength)) * .72 + p["defence"] * .28, 28, 96), 1)
    p["transition"] = round(_clamp(float(p.get("transition", strength)) * .72 + form * .28, 28, 96), 1)
    p["depth"] = round(_clamp(float(p.get("depth", strength)) * .74 + min(90, 42 + roster["count"] * 3.3) * .26, 28, 96), 1)
    p["recent_form"] = form
    p["avg_for"] = round(avg_for, 2) if avg_for is not None else round(9.4 + p["attack"] / 40, 2)
    p["avg_against"] = round(avg_against, 2) if avg_against is not None else round(13.2 - p["defence"] / 35, 2)
    p["history_score"] = round(table_strength * .58 + margin_signal * .42, 1)

    upcoming = [
        f for f in _safe_all(db, OfficialFixture)
        if (f.home_score is None or f.away_score is None)
        and (_same_team(f.home_team, team_name) or _same_team(f.away_team, team_name))
    ]
    upcoming.sort(key=lambda f: _parse_date(f.start_text) or datetime.max)
    rest, fatigue = _rest_fatigue(results, upcoming[0].start_text if upcoming else None)
    p["rest_days"], p["fatigue"] = rest, fatigue

    evidence = len(results) + (1 if standing else 0) + len(stats) + min(roster["count"], 13) / 3
    p["coverage"] = round(_clamp(max(float(p.get("coverage", .2)), .20 + min(.64, evidence * .035)), .20, .95), 3)
    p["recent_results"] = results
    p["roster_players"] = roster["players"]
    p["roster_status"] = roster["status"] if roster["count"] else p.get("roster_status", "RESEARCH_REQUIRED")
    p["data_status"] = (
        "CONFIRMED_HEAVY" if p["coverage"] >= .78
        else "PARTIAL_PUBLIC" if p["coverage"] >= .48
        else "PROVISIONAL"
    )
    return p


class SimulationTeamRegistry(dict):
    """Cached DB-backed registry that keeps every known team selectable."""

    def __init__(self, initial):
        super().__init__({k: dict(v) for k, v in initial.items()})
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

            def add(name):
                name = str(name or "").strip()
                if name and not any(_same_team(name, existing) for existing in names):
                    names.add(name)

            for row in _safe_all(db, ScoutingTeam):
                add(row.name)
            for row in _safe_all(db, OfficialStanding):
                add(row.team_name)
            for row in _safe_all(db, OfficialFixture):
                add(row.home_team)
                add(row.away_team)
            for row in _safe_all(db, MatchLibraryItem):
                add(row.team_a)
                add(row.team_b)

            # Always derive from an immutable prior. Never feed a previously
            # enriched profile back as a new prior: that created forecast drift.
            for name in sorted(names):
                dict.__setitem__(self, name, _derive_profile(db, name, _fresh_prior(name)))
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
        return any(_same_team(name, key) for name in dict.keys(self))

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
        return list(iter(self))


SIM_TEAMS = SimulationTeamRegistry(BASE_TEAMS)


def _poisson(lam, rng):
    threshold = math.exp(-max(.05, lam))
    k, product = 0, 1.0
    while product > threshold:
        k += 1
        product *= rng.random()
    return k - 1


def _metric_strength(team):
    return sum(float(team.get(k, 50)) * weight for k, weight in WEIGHTS.items()) / sum(WEIGHTS.values())


def _effective_strength(team, availability, form, rest, home=False, away=False):
    metric = _metric_strength(team)
    score = (
        float(team.get("strength", 50)) * .52
        + metric * .29
        + float(team.get("history_score", 50)) * .11
        + float(team.get("roster_continuity", 60)) * .04
        + float(form) * .04 - 2.0
        + _clamp(float(team.get("recruitment_delta", 0)), -3, 3)
    )
    score += (int(_clamp(availability, 50, 100)) - 100) * .11
    score -= max(0, float(team.get("fatigue", 30)) - 28) * .045
    if rest <= 0:
        score -= 1.5
    elif rest == 1:
        score -= .8
    elif rest >= 5:
        score += .15
    if home:
        score += (float(team.get("home_history", 55)) - 50) * .045
    elif away:
        score += (float(team.get("away_history", 50)) - 50) * .035
    return score


def _plan_bonus(team, opponent, tactic):
    base = TACTICS.get(tactic, TACTICS["balanced"])
    bonus = base["attack"] + base["defence"]
    if tactic == "transition":
        bonus += (float(team.get("transition", 50)) - float(opponent.get("transition", 50))) * .0055
    elif tactic == "centre_pressure":
        bonus += (float(team.get("centre", 50)) - float(opponent.get("defence", 50))) * .0055
    elif tactic == "zone_plus_focus":
        bonus += (float(team.get("extra_player", 50)) - float(opponent.get("penalty_kill", 50))) * .0055
    elif tactic == "defence_first":
        bonus += (
            float(team.get("defence", 50)) + float(team.get("goalkeeper", 50))
            - float(opponent.get("attack", 50)) * 2
        ) * .0025
    return _clamp(bonus, -.55, .55)


def _recommend_tactic(team, opponent):
    values = {name: _plan_bonus(team, opponent, name) for name in TACTICS}
    best = max(values, key=values.get)
    return best if values[best] >= values["balanced"] + .06 else "balanced"


def _pair_context(team_a, team_b):
    # Normal simulation calls use the 45-second registry cache so identical
    # requests remain deterministic and do not re-query every table repeatedly.
    if isinstance(SIM_TEAMS, SimulationTeamRegistry):
        SIM_TEAMS._refresh(force=False)
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
    rows = [x for x in _safe_all(db, OfficialFixture) if x.home_score is not None and x.away_score is not None]
    if competition:
        same = [x for x in rows if x.competition == competition]
        if len(same) >= 6:
            rows = same
    tested = correct = 0
    for f in rows[-limit:]:
        try:
            h, a = SIM_TEAMS[f.home_team], SIM_TEAMS[f.away_team]
        except Exception:
            continue
        predicted = float(h.get("strength", 50)) + 1 - float(a.get("strength", 50))
        actual = int(f.home_score) - int(f.away_score)
        if actual == 0:
            continue
        tested += 1
        correct += bool((predicted > 0 and actual > 0) or (predicted < 0 and actual < 0))
    accuracy = round(correct / tested * 100, 1) if tested else None
    return {
        "sample": tested, "direction_accuracy": accuracy,
        "label": f"Contrôle rétrospectif sur {tested} résultats publics" if tested else "Contrôle rétrospectif indisponible.",
    }


def _season_projection(db, focus_team, context, n=1200, seed=313):
    if not context or not context.get("competition") or not context.get("season"):
        return {"available": False, "reason": "Aucun calendrier officiel commun suffisamment identifié."}
    competition, season = context["competition"], context["season"]
    fixtures = [
        x for x in _safe_all(db, OfficialFixture)
        if x.competition == competition and x.season == season
    ]
    standings = [
        x for x in _safe_all(db, OfficialStanding)
        if x.competition == competition and x.season == season
    ]
    names = set()
    for f in fixtures:
        names.update([f.home_team, f.away_team])
    for s in standings:
        names.add(s.team_name)
    if len(names) < 3:
        return {"available": False, "reason": "Calendrier/participants incomplets pour projeter la compétition."}

    focus = next((name for name in names if _same_team(name, focus_team)), focus_team)
    points = {name: 0 for name in names}
    if standings:
        for row in standings:
            points[row.team_name] = int(row.points or 0)
    else:
        for f in fixtures:
            if f.home_score is None or f.away_score is None:
                continue
            if f.home_score > f.away_score:
                points[f.home_team] += 3
            elif f.away_score > f.home_score:
                points[f.away_team] += 3
            else:
                points[f.home_team] += 1
                points[f.away_team] += 1

    remaining = [f for f in fixtures if f.home_score is None or f.away_score is None]
    strengths = {}
    for name in names:
        try:
            strengths[name] = float(SIM_TEAMS[name].get("strength", 50))
        except Exception:
            strengths[name] = 50.0

    if not remaining:
        ordered = sorted(points, key=lambda x: (-points[x], -strengths.get(x, 50), x))
        rank = ordered.index(focus) + 1 if focus in ordered else len(ordered)
        return {
            "available": True, "competition": competition, "season": season,
            "simulations": 0, "title": 100.0 if rank == 1 else 0.0,
            "top3": 100.0 if rank <= 3 else 0.0,
            "playoffs": 100.0 if rank <= min(4, len(ordered)) else 0.0,
            "survival": 100.0 if rank <= max(1, len(ordered) - 2) else 0.0,
            "average_rank": float(rank), "remaining_matches": 0,
        }

    rng = random.Random(seed)
    title = top3 = playoffs = survival = rank_sum = 0
    playoff_cut, survival_cut = min(4, len(names)), max(1, len(names) - 2)
    for _ in range(n):
        sim_points = dict(points)
        for f in remaining:
            sh, sa = strengths.get(f.home_team, 50), strengths.get(f.away_team, 50)
            p_home = 1 / (1 + math.exp(-(sh - sa + 1.1) / 7.2))
            draw_p = .08 + max(0, .06 - abs(sh - sa) * .004)
            roll = rng.random()
            if roll < draw_p:
                sim_points[f.home_team] += 1
                sim_points[f.away_team] += 1
            elif roll < draw_p + (1 - draw_p) * p_home:
                sim_points[f.home_team] += 3
            else:
                sim_points[f.away_team] += 3
        ordered = sorted(sim_points, key=lambda x: (-sim_points[x], -strengths.get(x, 50), x))
        rank = ordered.index(focus) + 1 if focus in ordered else len(ordered)
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


def simulate_matchup(
    team_a, team_b, tactic_a="balanced", tactic_b="balanced", n=5000, seed=17,
    availability_a=100, availability_b=100, form_a=50, form_b=50,
    rest_a=3, rest_b=3, venue="neutral",
):
    """
    Automatic Football-Manager-style forecast.

    `form_*`, `rest_*`, `tactic_*` and `venue` are legacy-compatible arguments
    but intentionally do not control the forecast anymore. The engine derives
    them from results, calendar and matchup. `availability_*` is retained as
    the machine-readable consequence of the user's absent-player list.
    """
    if int(n) == 5000:
        n = 25000
    n = int(_clamp(int(n), 1000, 50000))

    context = _pair_context(team_a, team_b)
    a, b = SIM_TEAMS[team_a], SIM_TEAMS[team_b]
    auto_venue = context["venue"] if context else "neutral"
    auto_form_a = float(a.get("recent_form", a.get("history_score", 50)))
    auto_form_b = float(b.get("recent_form", b.get("history_score", 50)))
    auto_rest_a = int(a.get("rest_days", 3))
    auto_rest_b = int(b.get("rest_days", 3))
    tactic_a = _recommend_tactic(a, b)
    tactic_b = _recommend_tactic(b, a)
    availability_a = int(_clamp(availability_a, 50, 100))
    availability_b = int(_clamp(availability_b, 50, 100))

    sa = _effective_strength(
        a, availability_a, auto_form_a, auto_rest_a,
        home=auto_venue == "team_a_home", away=auto_venue == "team_b_home",
    )
    sb = _effective_strength(
        b, availability_b, auto_form_b, auto_rest_b,
        home=auto_venue == "team_b_home", away=auto_venue == "team_a_home",
    )

    level_gap = int(a.get("level", 2)) - int(b.get("level", 2))
    # Reality gate: a club-vs-senior-international class jump must not be
    # erased by noisy recent form or incomplete public club data.
    if abs(level_gap) >= 2:
        rating_gate = math.copysign(1.35 * (abs(level_gap) ** 1.35), level_gap)
        sa += max(0.0, rating_gate)
        sb += max(0.0, -rating_gate)

    rating_diff = sa - sb
    matchup = _plan_bonus(a, b, tactic_a) - _plan_bonus(b, a, tactic_b)
    expected_margin = 11.8 * math.tanh(rating_diff / 25.5) + matchup * .85
    if abs(level_gap) >= 2:
        # Minimum goal-space separation for large competition-class gaps.
        # Senior-international gaps get a stronger floor than youth gaps.
        class_multiplier = 5.5 if abs(level_gap) >= 3 else 4.0
        target_margin = level_gap * class_multiplier
        if level_gap > 0:
            expected_margin = max(expected_margin, target_margin)
        else:
            expected_margin = min(expected_margin, target_margin)

    pace = (float(a.get("pace", 52)) + float(b.get("pace", 52))) / 2
    total = _clamp(
        20.5 + (pace - 52) * .16
        + (TACTICS[tactic_a]["pace"] + TACTICS[tactic_b]["pace"]) * .28,
        15.5, 25.5,
    )
    structural_a = _clamp((total + expected_margin) / 2, 2.0, 20.0)
    structural_b = _clamp((total - expected_margin) / 2, 2.0, 20.0)

    recent_a = _clamp(
        (float(a.get("avg_for", structural_a)) + float(b.get("avg_against", structural_a))) / 2,
        3.0, 19.0,
    )
    recent_b = _clamp(
        (float(b.get("avg_for", structural_b)) + float(a.get("avg_against", structural_b))) / 2,
        3.0, 19.0,
    )
    form_goal_a = _clamp(10.3 + (auto_form_a - auto_form_b) / 18, 4.0, 17.0)
    form_goal_b = _clamp(10.3 + (auto_form_b - auto_form_a) / 18, 4.0, 17.0)

    # Ensemble of structural class, recent scoring and current form.
    lam_a = structural_a * .62 + recent_a * .25 + form_goal_a * .13
    lam_b = structural_b * .62 + recent_b * .25 + form_goal_b * .13
    if auto_venue == "team_a_home":
        lam_a += .28
        lam_b -= .10
    elif auto_venue == "team_b_home":
        lam_b += .28
        lam_a -= .10
    lam_a, lam_b = _clamp(lam_a, 1.6, 21.0), _clamp(lam_b, 1.6, 21.0)

    coverage = min(float(a.get("coverage", .25)), float(b.get("coverage", .25)))
    uncertainty = .055 + (1 - coverage) * .13
    uncertainty += (float(a.get("fatigue", 30)) + float(b.get("fatigue", 30))) / 2400

    rng = random.Random(seed)
    wins_a = wins_b = draws = 0
    sum_a = sum_b = 0
    diffs = []
    counts = Counter()
    for _ in range(n):
        shared = _clamp(rng.gauss(1.0, uncertainty * .5), .74, 1.28)
        xa = _poisson(lam_a * shared * _clamp(rng.gauss(1.0, uncertainty), .72, 1.30), rng)
        xb = _poisson(lam_b * shared * _clamp(rng.gauss(1.0, uncertainty), .72, 1.30), rng)
        sum_a += xa
        sum_b += xb
        diffs.append(xa - xb)
        counts[(xa, xb)] += 1
        if xa > xb:
            wins_a += 1
        elif xb > xa:
            wins_b += 1
        else:
            draws += 1

    diffs.sort()
    lo = diffs[int(.10 * n)]
    med = diffs[int(.50 * n)]
    hi = diffs[min(n - 1, int(.90 * n))]
    avg_a, avg_b = sum_a / n, sum_b / n
    cross_level = abs(level_gap) >= 2
    top_scores = [
        {"score": f"{x}–{y}", "probability": round(c / n * 100, 2), "count": c}
        for (x, y), c in counts.most_common(8)
    ]
    confidence = int(round(_clamp(
        48 + coverage * 44 - (0 if context else 4)
        + min(8, len(a.get("recent_results", [])) + len(b.get("recent_results", []))) * .45,
        44, 93,
    )))

    factor_rows = [
        ("Classe / niveau", a.get("competition_class", "—"), b.get("competition_class", "—"), round(rating_diff, 1)),
        ("Historical results prior", a.get("history_score", "—"), b.get("history_score", "—"), round((float(a.get("history_score", 50)) - float(b.get("history_score", 50))) * .10, 1)),
        ("Home/away history", a.get("home_history" if auto_venue == "team_a_home" else "away_history", "—"), b.get("home_history" if auto_venue == "team_b_home" else "away_history", "—"), 0.0),
        ("Recruitment / selection impact", a.get("recruitment_delta", 0), b.get("recruitment_delta", 0), round(float(a.get("recruitment_delta", 0)) - float(b.get("recruitment_delta", 0)), 1)),
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
            validation = _validation_snapshot(db, context.get("competition", "") if context else "")
            season_a = _season_projection(db, team_a, context, seed=seed + 101)
            season_b = _season_projection(db, team_b, context, seed=seed + 202)
        except Exception:
            pass
        finally:
            if db is not None:
                db.close()

    return {
        "team_a": team_a, "team_b": team_b,
        "avg_a": round(avg_a, 1), "avg_b": round(avg_b, 1),
        "win_a": round(wins_a / n * 100, 2), "win_b": round(wins_b / n * 100, 2),
        "draw": round(draws / n * 100, 2),
        "diff_interval": [lo, hi], "median_diff": med,
        "coverage": round(coverage * 100), "confidence": confidence, "n": n,
        "strength_a": round(sa, 1), "strength_b": round(sb, 1),
        "class_gap": abs(level_gap), "cross_level": cross_level,
        "factor_rows": factor_rows, "tactic_a": tactic_a, "tactic_b": tactic_b,
        "roster_status_a": a.get("roster_status", "RESEARCH_REQUIRED"),
        "roster_status_b": b.get("roster_status", "RESEARCH_REQUIRED"),
        "recruitment_note_a": a.get("recruitment_note", "No recruitment context available."),
        "recruitment_note_b": b.get("recruitment_note", "No recruitment context available."),
        "top_scores": top_scores,
        "scenarios": {
            "pessimistic_a": lo, "central_a": med, "optimistic_a": hi,
            "label": "Écart de buts équipe A aux percentiles 10 / 50 / 90.",
        },
        "context": context,
        "auto_inputs": {
            "form_a": auto_form_a, "form_b": auto_form_b,
            "rest_a": auto_rest_a, "rest_b": auto_rest_b,
            "fatigue_a": a.get("fatigue", 30), "fatigue_b": b.get("fatigue", 30),
            "venue": auto_venue,
            "availability_a": availability_a, "availability_b": availability_b,
        },
        "recent_results_a": a.get("recent_results", []),
        "recent_results_b": b.get("recent_results", []),
        "roster_a": a.get("roster_players", []),
        "roster_b": b.get("roster_players", []),
        "data_status_a": a.get("data_status", "PROVISIONAL"),
        "data_status_b": b.get("data_status", "PROVISIONAL"),
        "validation": validation, "season_a": season_a, "season_b": season_b,
        "disclaimer": (
            "Exploratory probabilistic manager projection — not a certainty and not a betting model. "
            "Form, fatigue, rest, level, venue and tactical plan are calculated automatically "
            "from documented results and available data. The user's primary manual correction "
            "is the absence of one or more players. Partial public data increases uncertainty."
        ),
    }
