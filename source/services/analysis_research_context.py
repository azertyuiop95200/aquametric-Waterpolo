from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import defaultdict
from sqlalchemy import select

from models import (
    OfficialDataSource,
    OfficialFixture,
    OfficialStanding,
    OfficialTeamStat,
    ScoutingPlayer,
    ScoutingTeam,
)

OFFICIAL_ANALYSIS_REFERENCES = [
    {
        "name": "World Aquatics — Water Polo Results",
        "url": "https://www.worldaquatics.com/water-polo/results",
        "scope": "results",
        "use": "Calendrier/résultats officiels internationaux lorsqu'ils sont publiés.",
    },
    {
        "name": "World Aquatics — Singapore 2025 Water Polo Results Report",
        "url": "https://www.worldaquatics.com/news/4441220/inside-the-action-water-polo-performance-analysis-at-singapore-2025",
        "scope": "performance_reference",
        "use": "Référence de performance : possession, efficacité, tirs, tendances tactiques, contributions individuelles et gardiennes.",
    },
    {
        "name": "European Aquatics — 2026 Women European Championships MIS",
        "url": "https://europeanaquatics.org/ewpc-2026/funchal/media-center/general-information/media-guide-extended-lists-mis/",
        "scope": "competition_mis",
        "use": "Résultats, start lists/feuilles, classements, effectifs et documents officiels du championnat féminin 2026.",
    },
]


def _key(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
    aliases = {
        "spain": "spain", "espana": "spain", "espagne": "spain",
        "greece": "greece", "grece": "greece",
        "usa": "usa", "united states": "usa", "united states of america": "usa",
    }
    return aliases.get(value, value)


def _same(a: str, b: str) -> bool:
    ka, kb = _key(a), _key(b)
    return bool(ka and kb and (ka == kb or ka in kb or kb in ka))


def _fixture_row(row, source):
    return {
        "id": row.id,
        "competition": row.competition,
        "season": row.season,
        "category": row.category,
        "start": row.start_text,
        "home": row.home_team,
        "away": row.away_team,
        "home_score": row.home_score,
        "away_score": row.away_score,
        "status": row.status,
        "venue": row.venue,
        "source_url": row.source_url or (source.url if source else ""),
        "source_name": source.name if source else "official fixture",
    }


def build_research_context(db, match) -> dict:
    """Aggregate every sourced database record and high-value official reference useful to one match."""
    team_name = match.team.name
    opponent = match.opponent
    source_rows = db.scalars(select(OfficialDataSource)).all()
    sources = {row.id: row for row in source_rows}
    fixtures = db.scalars(select(OfficialFixture).order_by(OfficialFixture.updated_at.desc(), OfficialFixture.id.desc())).all()

    exact = []
    related = []
    for row in fixtures:
        pair_exact = (
            (_same(row.home_team, team_name) and _same(row.away_team, opponent))
            or (_same(row.home_team, opponent) and _same(row.away_team, team_name))
        )
        competition_ok = not match.competition or not row.competition or _key(match.competition) in _key(row.competition) or _key(row.competition) in _key(match.competition)
        data = _fixture_row(row, sources.get(row.source_id))
        if pair_exact and competition_ok:
            exact.append(data)
        elif _same(row.home_team, team_name) or _same(row.away_team, team_name) or _same(row.home_team, opponent) or _same(row.away_team, opponent):
            related.append(data)
    exact = exact[:8]
    related = related[:24]

    stat_rows = db.scalars(select(OfficialTeamStat).order_by(OfficialTeamStat.updated_at.desc(), OfficialTeamStat.id.desc())).all()
    season_stats = defaultdict(list)
    source_urls = {row.url for row in source_rows if row.enabled and row.url}
    source_urls.update(item["url"] for item in OFFICIAL_ANALYSIS_REFERENCES)
    for row in stat_rows:
        side = "team" if _same(row.team_name, team_name) else "opponent" if _same(row.team_name, opponent) else ""
        if not side:
            continue
        if match.competition and row.competition and not (_key(match.competition) in _key(row.competition) or _key(row.competition) in _key(match.competition)):
            continue
        season_stats[side].append({
            "team_name": row.team_name,
            "metric": row.metric,
            "value": row.value,
            "competition": row.competition,
            "season": row.season,
            "category": row.category,
            "source_url": row.source_url,
        })
        if row.source_url:
            source_urls.add(row.source_url)

    standing_rows = db.scalars(select(OfficialStanding).order_by(OfficialStanding.updated_at.desc(), OfficialStanding.id.desc())).all()
    standings = []
    for row in standing_rows:
        side = "team" if _same(row.team_name, team_name) else "opponent" if _same(row.team_name, opponent) else ""
        if not side:
            continue
        if match.competition and row.competition and not (_key(match.competition) in _key(row.competition) or _key(row.competition) in _key(match.competition)):
            continue
        standings.append({
            "side": side, "team_name": row.team_name, "competition": row.competition,
            "season": row.season, "position": row.position, "points": row.points,
            "played": row.played, "won": row.won, "lost": row.lost,
            "goals_for": row.goals_for, "goals_against": row.goals_against,
            "goal_diff": row.goal_diff, "source_url": row.source_url,
        })
        if row.source_url:
            source_urls.add(row.source_url)
    standings = standings[:12]

    scout_teams = db.scalars(select(ScoutingTeam).order_by(ScoutingTeam.updated_at.desc(), ScoutingTeam.id.desc())).all()
    rosters = {"team": [], "opponent": []}
    roster_meta = {}
    for side, wanted in (("team", team_name), ("opponent", opponent)):
        scout = next((row for row in scout_teams if _same(row.name, wanted)), None)
        if not scout:
            continue
        roster_meta[side] = {
            "team": scout.name, "season": scout.season_label, "status": scout.roster_status,
            "competition": scout.competition, "source_url": scout.source_url,
            "source_note": scout.source_note,
        }
        players = db.scalars(
            select(ScoutingPlayer)
            .where(ScoutingPlayer.scouting_team_id == scout.id)
            .order_by(ScoutingPlayer.cap_number.nullslast(), ScoutingPlayer.name)
        ).all()
        rosters[side] = [
            {
                "name": p.name, "cap": p.cap_number, "role": p.role,
                "nationality": p.nationality, "season": p.source_season,
                "status": p.current_status, "source_quality": p.source_quality,
                "source_url": p.source_url, "note": p.note,
            }
            for p in players
        ]
        if scout.source_url:
            source_urls.add(scout.source_url)
        source_urls.update(p.source_url for p in players if p.source_url)

    for row in exact + related:
        if row.get("source_url"):
            source_urls.add(row["source_url"])

    official_catalog = [
        {
            "name": row.name, "provider": row.provider, "region": row.region,
            "url": row.url, "parser_kind": row.parser_kind,
            "enabled": bool(row.enabled), "last_success_at": row.last_success_at,
            "records_count": row.records_count,
        }
        for row in source_rows if row.enabled
    ] + OFFICIAL_ANALYSIS_REFERENCES

    return {
        "match": {"team": team_name, "opponent": opponent, "competition": match.competition or "", "date": match.match_date or ""},
        "official_match_candidates": exact,
        "related_fixtures": related,
        "season_team_stats": dict(season_stats),
        "standings": standings,
        "rosters": rosters,
        "roster_meta": roster_meta,
        "official_reference_catalog": official_catalog,
        "source_urls": sorted(source_urls),
        "coverage": {
            "exact_official_matches": len(exact),
            "related_fixtures": len(related),
            "team_metrics": len(season_stats.get("team", [])),
            "opponent_metrics": len(season_stats.get("opponent", [])),
            "standing_rows": len(standings),
            "team_roster_players": len(rosters["team"]),
            "opponent_roster_players": len(rosters["opponent"]),
            "official_reference_sources": len(official_catalog),
            "unique_sources": len(source_urls),
        },
        "contract": "Contexte sourcé : ces données enrichissent l'analyse mais ne deviennent jamais automatiquement des événements vidéo.",
    }


def _csv(headers, rows) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def append_research_to_zip(zip_buffer: io.BytesIO, research: dict, root: str):
    zip_buffer.seek(0, io.SEEK_END)
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{root}/06_sources/research_context.json", json.dumps(research, ensure_ascii=False, indent=2, default=str))
        archive.writestr(f"{root}/06_sources/source_urls.txt", "\n".join(research.get("source_urls", [])) + "\n")
        archive.writestr(f"{root}/06_sources/official_reference_catalog.json", json.dumps(research.get("official_reference_catalog", []), ensure_ascii=False, indent=2, default=str))
        archive.writestr(
            f"{root}/02_kpis/official_context.csv",
            _csv(
                ["side", "team_name", "metric", "value", "competition", "season", "category", "source_url"],
                [{"side": side, **row} for side, rows in research.get("season_team_stats", {}).items() for row in rows],
            ),
        )
        archive.writestr(
            f"{root}/07_rosters/team_roster.csv",
            _csv(["name", "cap", "role", "nationality", "season", "status", "source_quality", "source_url", "note"], research.get("rosters", {}).get("team", [])),
        )
        archive.writestr(
            f"{root}/07_rosters/opponent_roster.csv",
            _csv(["name", "cap", "role", "nationality", "season", "status", "source_quality", "source_url", "note"], research.get("rosters", {}).get("opponent", [])),
        )
        archive.writestr(
            f"{root}/08_official_context/official_match_candidates.csv",
            _csv(["id", "competition", "season", "category", "start", "home", "away", "home_score", "away_score", "status", "venue", "source_url", "source_name"], research.get("official_match_candidates", [])),
        )
        archive.writestr(
            f"{root}/08_official_context/related_fixtures.csv",
            _csv(["id", "competition", "season", "category", "start", "home", "away", "home_score", "away_score", "status", "venue", "source_url", "source_name"], research.get("related_fixtures", [])),
        )
        archive.writestr(
            f"{root}/08_official_context/standings.csv",
            _csv(["side", "team_name", "competition", "season", "position", "points", "played", "won", "lost", "goals_for", "goals_against", "goal_diff", "source_url"], research.get("standings", [])),
        )
    zip_buffer.seek(0)
    return zip_buffer
