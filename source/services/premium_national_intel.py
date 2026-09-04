from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from sqlalchemy import or_, select

from models import LibraryPlayerMatchStat, MatchLibraryItem, ScoutingPlayer, ScoutingTeam

BASE_DIR = Path(__file__).resolve().parents[1]
REFERENCE_FILE = BASE_DIR / "static" / "elite-national-reference.json"

PRIORITY_TEAMS = [
    {
        "key": "nat-fr-w-senior-2026",
        "name": "France — Women Senior 2026",
        "country": "France", "age_group": "Senior", "competition": "European Championships 2026",
        "season": "2026", "status": "current_event_reference_roster_refresh_required",
        "source": "https://europeanaquatics.org/ewpc-2026/funchal/media-center/general-information/media-guide-extended-lists-mis/",
        "note": "Current 2026 senior event card. Use the European Aquatics MIS/start lists for the event roster; do not substitute the Paris 2024 roster.",
        "priority": 120,
    },
    {
        "key": "nat-fr-w-u20-2026",
        "name": "France — Women U20 2026",
        "country": "France", "age_group": "U20", "competition": "European U20 Championships 2026",
        "season": "2026", "status": "current_event_reference_roster_refresh_required",
        "source": "https://europeanaquatics.org/oeiras-2026-hungary-u20s-crowned-european-champions-after-edging-epic-shootout-with-spain/",
        "note": "France finished 11th at the 2026 European U20 Championship. Attach official match sheets before presenting any individual roster as complete.",
        "priority": 119,
    },
    {
        "key": "nat-rus-w-senior-2026",
        "name": "Russia — Women Senior 2026",
        "country": "Russia", "age_group": "Senior", "competition": "World Aquatics World Cup 2026",
        "season": "2026", "status": "current_official_event_roster_partial",
        "source": "https://www.worldaquatics.com/competitions/5133/women-s-water-polo-world-cup-2026-division-2/results",
        "note": "Russia returned to major international competition in 2026, won Division II and finished 4th at the Sydney World Cup Finals. Roster details should stay tied to the official event sheet.",
        "priority": 118,
        "players": [
            (1, "Diana Khamraeva", "Goalkeeper"), (2, "Mariia Makarova", "Driver"),
            (3, "Ekaterina Prokofyeva", "Driver"), (4, "Margarita Pystina", "Driver"),
            (5, "Daria Savchenko", "Center / Forward"), (6, "Polina Popova", "Center / Back"),
            (8, "Olga Lupinogina", "Driver"), (10, "Mariia Borisova", "Center / Forward"),
            (11, "Bella Markoch", "Driver"), (12, "Vladislava Nechaeva", "Center / Forward"),
            (13, "Anastasiia Komarova", "Goalkeeper"),
        ],
    },
    {
        "key": "nat-rus-w-u20-2026",
        "name": "Russia / Neutral Athletes B — Women U20 2026",
        "country": "Russia", "age_group": "U20", "competition": "European U20 Championships 2026",
        "season": "2026", "status": "neutral_athletes_b_event_reference",
        "source": "https://europeanaquatics.org/oeiras-2026-hungary-u20s-crowned-european-champions-after-edging-epic-shootout-with-spain/",
        "note": "2026 U20 European reference is listed by European Aquatics as Neutral Athletes B. The product keeps that competition label visible and does not silently relabel official event records.",
        "priority": 117,
    },
    {
        "key": "nat-isr-w-senior-2026",
        "name": "Israel — Women Senior 2026",
        "country": "Israel", "age_group": "Senior", "competition": "European Championships 2026",
        "season": "2026", "status": "current_event_reference_roster_refresh_required",
        "source": "https://europeanaquatics.org/ewpc-2026/funchal/funchal-2026-israel-and-netherlands-book-their-place-in-the-next-phase-at-european-championships/",
        "note": "Israel finished 7th at Funchal 2026. Current roster must be sourced from the event MIS/start lists before being marked complete.",
        "priority": 116,
    },
    {
        "key": "nat-isr-w-u20-2026",
        "name": "Israel — Women U20 2026",
        "country": "Israel", "age_group": "U20", "competition": "European U20 Championships 2026",
        "season": "2026", "status": "current_event_reference_roster_refresh_required",
        "source": "https://europeanaquatics.org/oeiras-2026-hungary-u20s-crowned-european-champions-after-edging-epic-shootout-with-spain/",
        "note": "Israel finished 9th at the 2026 European U20 Championship. This is the priority youth case study for AquaMetric.",
        "priority": 115,
    },
]


def _safe_json_file():
    try:
        return json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def ensure_priority_national_teams(db):
    for item in PRIORITY_TEAMS:
        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == item["key"]))
        if not team:
            team = ScoutingTeam(
                external_key=item["key"], name=item["name"], team_type="national_team", category="Women",
                age_group=item["age_group"], country=item["country"], competition=item["competition"],
                season_label=item["season"], roster_status=item["status"], source_url=item["source"],
                source_note=item["note"], priority=item["priority"],
            )
            db.add(team); db.flush()
        else:
            team.name = item["name"]; team.age_group = item["age_group"]; team.country = item["country"]
            team.competition = item["competition"]; team.season_label = item["season"]
            team.roster_status = item["status"]; team.source_url = item["source"]; team.source_note = item["note"]
            team.priority = max(team.priority or 0, item["priority"])
        if item.get("players") and not db.scalar(select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id == team.id)):
            for cap, name, role in item["players"]:
                db.add(ScoutingPlayer(
                    scouting_team_id=team.id, name=name, cap_number=cap, nationality="RUS", role=role,
                    source_season="2026", source_url=item["source"], source_quality="world_aquatics_official_result",
                    current_status="current_event_reference", note="Roster entry observed on official World Aquatics 2026 event result sheet.",
                ))
    db.commit()


def _aliases(team: ScoutingTeam):
    values = {team.country.strip(), team.name.strip()}
    values.add(team.name.split("—")[0].strip())
    if team.country == "United States": values.update({"USA", "United States of America"})
    if team.country == "Russia" and team.age_group == "U20": values.update({"Neutral Athletes B", "NAB", "Russia"})
    if team.country == "Great Britain": values.add("GBR")
    return {x.lower() for x in values if x}


def _matches_for(db, team: ScoutingTeam):
    aliases = _aliases(team)
    items = db.scalars(select(MatchLibraryItem).order_by(MatchLibraryItem.id.desc())).all()
    out = []
    for item in items:
        a = (item.team_a or "").lower(); b = (item.team_b or "").lower()
        side = None
        if a in aliases or any(alias == a for alias in aliases): side = "a"
        elif b in aliases or any(alias == b for alias in aliases): side = "b"
        if not side or item.score_a is None or item.score_b is None:
            continue
        gf = int(item.score_a if side == "a" else item.score_b)
        ga = int(item.score_b if side == "a" else item.score_a)
        out.append({
            "id": item.id, "competition": item.competition, "season": item.season,
            "opponent": item.team_b if side == "a" else item.team_a,
            "gf": gf, "ga": ga, "result": "W" if gf > ga else ("D" if gf == ga else "L"),
            "video": bool(item.video_url), "source": bool(item.official_source_url),
        })
    return out[:30]


def _history(rows):
    if not rows:
        return {"matches": 0, "wins": 0, "losses": 0, "draws": 0, "win_pct": None, "avg_for": None, "avg_against": None}
    wins = sum(r["result"] == "W" for r in rows); losses = sum(r["result"] == "L" for r in rows); draws = len(rows)-wins-losses
    return {
        "matches": len(rows), "wins": wins, "losses": losses, "draws": draws,
        "win_pct": round(100*wins/len(rows), 1), "avg_for": round(mean(r["gf"] for r in rows),1),
        "avg_against": round(mean(r["ga"] for r in rows),1),
    }


def _player_snapshot(db, team: ScoutingTeam):
    roster = db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id == team.id).order_by(ScoutingPlayer.cap_number, ScoutingPlayer.name)).all()
    roles = Counter((p.role or "Role to confirm") for p in roster)
    aliases = _aliases(team)
    stats = db.scalars(select(LibraryPlayerMatchStat)).all()
    goals = defaultdict(int); games = defaultdict(set); source_quality = {}
    for row in stats:
        if (row.team_name or "").lower() not in aliases:
            continue
        if row.goals is not None:
            goals[row.player_name] += int(row.goals or 0); games[row.player_name].add(row.library_match_id)
            source_quality[row.player_name] = row.source_quality
    top = sorted(goals.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    return {
        "roster": roster, "roster_count": len(roster), "roles": roles,
        "top_scorers": [{"name": n, "goals": g, "matches": len(games[n]), "source_quality": source_quality.get(n, "")} for n,g in top],
    }


def build_national_team_card(db, team: ScoutingTeam):
    matches = _matches_for(db, team); players = _player_snapshot(db, team)
    history = _history(matches)
    coverage = 0
    coverage += 30 if players["roster_count"] else 0
    coverage += 25 if matches else 0
    coverage += 15 if players["top_scorers"] else 0
    coverage += 15 if team.source_url else 0
    coverage += 15 if any(r["video"] for r in matches) else 0
    readiness = "STRONG" if coverage >= 70 else "USABLE" if coverage >= 50 else "BUILDING" if coverage >= 25 else "SPARSE"
    return {"team": team, "matches": matches[:8], "history": history, "players": players, "coverage": coverage, "readiness": readiness}


def build_national_dashboard(db):
    ensure_priority_national_teams(db)
    teams = db.scalars(
        select(ScoutingTeam).where(ScoutingTeam.team_type == "national_team").order_by(ScoutingTeam.priority.desc(), ScoutingTeam.country, ScoutingTeam.age_group)
    ).all()
    cards = [build_national_team_card(db,t) for t in teams]
    priority = [c for c in cards if c["team"].country in {"France","Russia","Israel"} and c["team"].season_label == "2026"]
    seniors = [c for c in cards if c["team"].age_group == "Senior"]
    u20 = [c for c in cards if c["team"].age_group == "U20"]
    ref = _safe_json_file()
    return {"priority": priority, "seniors": seniors, "u20": u20, "reference": ref}
