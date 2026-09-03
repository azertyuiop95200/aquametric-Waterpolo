from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import MatchLibraryItem, LibraryPlayerMatchStat, ScoutingTeam, OfficialStanding
from scorer_models import OfficialScorerStanding


TRACKED_WOMEN_COMPETITIONS = [
    {
        "key": "france-elite",
        "country": "France",
        "competition": "Elite Féminine",
        "level": "Elite",
        "order": 10,
        "aliases": [
            "elite feminine", "élite féminine", "ff natation elite feminine",
            "ff natation — elite feminine", "elite femmes", "pro a feminine",
        ],
    },
    {
        "key": "france-n1",
        "country": "France",
        "competition": "N1 Féminine",
        "level": "N1",
        "order": 20,
        "aliases": [
            "n1 feminine", "n1 féminine", "nationale 1 feminine", "nationale 1 féminine",
            "national 1 women", "championnat de france n1 feminine",
        ],
    },
    {
        "key": "spain-elite",
        "country": "Espagne",
        "competition": "División de Honor Femenina",
        "level": "Elite",
        "order": 30,
        "aliases": ["division de honor femenina", "división de honor femenina", "spain women elite"],
    },
    {
        "key": "italy-elite",
        "country": "Italie",
        "competition": "Serie A1 Femminile",
        "level": "Elite",
        "order": 40,
        "aliases": ["serie a1 femminile", "a1 femminile", "italy women elite"],
    },
    {
        "key": "hungary-elite",
        "country": "Hongrie",
        "competition": "OB I Női",
        "level": "Elite",
        "order": 50,
        "aliases": ["ob i noi", "ob i női", "noi ob i", "hungary women elite"],
    },
    {
        "key": "germany-elite",
        "country": "Allemagne",
        "competition": "Bundesliga Frauen",
        "level": "Elite",
        "order": 60,
        "aliases": ["bundesliga frauen", "bundesliga women", "dwl", "germany women elite"],
    },
    {
        "key": "russia-elite",
        "country": "Russie",
        "competition": "Russian Women's Championship",
        "level": "Elite",
        "order": 70,
        "aliases": ["russian women", "russia women championship", "women championship russia", "женщины"],
    },
]


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", (value or "").lower())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return " ".join(value.replace("—", " ").replace("-", " ").split())


def season_window(reference_date: date | None = None, count: int = 4) -> list[str]:
    """Current season plus N-1/N-2/N-3, assuming European seasons start in August."""
    ref = reference_date or date.today()
    start = ref.year if ref.month >= 8 else ref.year - 1
    return [f"{start-offset}-{start-offset+1}" for offset in range(count)]


def _season_aliases(season: str) -> set[str]:
    if "-" not in season:
        return {season}
    left, right = season.split("-", 1)
    return {season, f"{left[-2:]}/{right[-2:]}", f"{left[-2:]}-{right[-2:]}"}


def _looks_women(value: str) -> bool:
    n = _normalize(value)
    return any(token in n for token in ("women", "woman", "femin", "feminin", "femenina", "femminile", "frauen", "noi", "женщ"))


def _country_label(value: str) -> str:
    n = _normalize(value)
    mapping = {
        "france": "France", "spain": "Espagne", "espagne": "Espagne", "espana": "Espagne",
        "italy": "Italie", "italie": "Italie", "italia": "Italie",
        "hungary": "Hongrie", "hongrie": "Hongrie", "magyar": "Hongrie",
        "germany": "Allemagne", "allemagne": "Allemagne", "deutschland": "Allemagne",
        "russia": "Russie", "russie": "Russie", "россия": "Russie",
    }
    return mapping.get(n, value or "International")


def _registry_copy() -> list[dict]:
    return [{**item, "aliases": list(item["aliases"])} for item in TRACKED_WOMEN_COMPETITIONS]


def _match_registry(registry: list[dict], competition: str, country: str = "") -> dict | None:
    comp_norm = _normalize(competition)
    country_norm = _normalize(country)
    for item in registry:
        candidates = [item["competition"], *item.get("aliases", [])]
        if any(_normalize(alias) and _normalize(alias) in comp_norm for alias in candidates):
            return item
        if country_norm and _normalize(item["country"]) == country_norm:
            if item["level"] == "N1" and any(token in comp_norm for token in ("n1", "nationale 1", "national 1")):
                return item
            if item["level"] == "Elite" and _looks_women(competition) and not any(token in comp_norm for token in ("n1", "nationale 1", "national 1")):
                return item
    return None


def _ensure_dynamic_registry(db: Session, registry: list[dict]) -> list[dict]:
    """Add women's domestic competitions already present in AquaMetric data."""
    seen = {_normalize(item["competition"]) for item in registry}
    candidates: list[tuple[str, str]] = []
    for team in db.scalars(select(ScoutingTeam).where(ScoutingTeam.team_type == "club")).all():
        if (team.category or "").lower() != "women" or not team.competition:
            continue
        candidates.append((team.competition, team.country))
    for standing in db.scalars(select(OfficialStanding)).all():
        if standing.competition and (_looks_women(standing.category) or _looks_women(standing.competition)):
            candidates.append((standing.competition, ""))

    for competition, country in candidates:
        if _match_registry(registry, competition, country):
            continue
        normalized = _normalize(competition)
        if normalized in seen or not _looks_women(competition):
            continue
        seen.add(normalized)
        registry.append({
            "key": f"dynamic-{len(registry)+1}",
            "country": _country_label(country),
            "competition": competition,
            "level": "Elite",
            "order": 100 + len(registry),
            "aliases": [competition],
        })
    return registry


def _rank(rows: list[dict]) -> list[dict]:
    rows.sort(
        key=lambda row: (
            -int(row.get("goals") or 0),
            -(float(row.get("goals_per_match") or 0.0)),
            _normalize(row.get("player_name", "")),
        )
    )
    previous_goals = None
    previous_rate = None
    previous_position = 0
    for index, row in enumerate(rows, start=1):
        goals = int(row.get("goals") or 0)
        rate = float(row.get("goals_per_match") or 0.0)
        if goals == previous_goals and rate == previous_rate:
            row["position"] = previous_position
        else:
            row["position"] = index
            previous_position = index
            previous_goals = goals
            previous_rate = rate
    return rows


def _persisted_rows(db: Session, seasons: list[str]) -> dict[tuple[str, str], list[dict]]:
    output: dict[tuple[str, str], list[dict]] = defaultdict(list)
    rows = db.scalars(select(OfficialScorerStanding)).all()
    valid_aliases = {alias for season in seasons for alias in _season_aliases(season)}
    for row in rows:
        if row.season not in valid_aliases:
            continue
        output[(row.competition, row.season)].append({
            "player_name": row.player_name,
            "team_name": row.team_name,
            "goals": row.goals,
            "matches_played": row.matches_played,
            "penalties": row.penalties,
            "non_penalty_goals": row.non_penalty_goals,
            "goals_per_match": row.goals_per_match,
            "source_url": row.source_url,
            "source_quality": row.source_quality,
            "coverage_label": row.coverage_label,
            "updated_at": row.updated_at,
        })
    return output


def _canonical_season(raw: str, seasons: list[str]) -> str | None:
    for season in seasons:
        if raw in _season_aliases(season):
            return season
    return None


def _aggregate_library(db: Session, registry: list[dict], seasons: list[str]) -> dict[tuple[str, str], list[dict]]:
    """Fallback scorer totals from officially sourced match-library player rows.

    This is intentionally labelled partial because the library may contain only a subset
    of a championship's matches. It gives useful historical evidence without pretending
    that the ranking is complete.
    """
    grouped: dict[tuple[str, str, str, str], dict] = {}
    rows = db.execute(
        select(LibraryPlayerMatchStat, MatchLibraryItem)
        .join(MatchLibraryItem, LibraryPlayerMatchStat.library_match_id == MatchLibraryItem.id)
        .where(LibraryPlayerMatchStat.goals.is_not(None), MatchLibraryItem.entity_type == "club")
    ).all()
    for stat, match in rows:
        season = _canonical_season(match.season, seasons)
        if not season:
            continue
        reg = _match_registry(registry, match.competition)
        if not reg:
            continue
        key = (reg["competition"], season, stat.player_name, stat.team_name)
        item = grouped.setdefault(key, {
            "player_name": stat.player_name,
            "team_name": stat.team_name,
            "goals": 0,
            "match_ids": set(),
            "source_urls": set(),
        })
        item["goals"] += int(stat.goals or 0)
        item["match_ids"].add(match.id)
        if match.official_source_url:
            item["source_urls"].add(match.official_source_url)

    output: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for (competition, season, _player, _team), item in grouped.items():
        matches = len(item["match_ids"])
        output[(competition, season)].append({
            "player_name": item["player_name"],
            "team_name": item["team_name"],
            "goals": item["goals"],
            "matches_played": matches,
            "penalties": None,
            "non_penalty_goals": None,
            "goals_per_match": round(item["goals"] / matches, 2) if matches else None,
            "source_url": next(iter(item["source_urls"]), ""),
            "source_quality": "official_match_reports",
            "coverage_label": "partial_match_library",
            "updated_at": None,
        })
    return output


def build_scorer_groups(db: Session, reference_date: date | None = None) -> dict:
    seasons = season_window(reference_date)
    registry = _ensure_dynamic_registry(db, _registry_copy())
    persisted = _persisted_rows(db, seasons)
    library = _aggregate_library(db, registry, seasons)

    groups = []
    for reg in sorted(registry, key=lambda item: (item.get("order", 999), item["country"], item["competition"])):
        season_rows = []
        for index, season in enumerate(seasons):
            official_candidates: list[dict] = []
            for (raw_competition, raw_season), rows in persisted.items():
                resolved = _match_registry(registry, raw_competition)
                canonical_season = _canonical_season(raw_season, seasons)
                if resolved and resolved["competition"] == reg["competition"] and canonical_season == season:
                    official_candidates.extend(rows)
            if official_candidates:
                ranked = _rank(official_candidates)
                coverage = "official"
                coverage_text = "Classement buteuses officiel publié"
            else:
                ranked = _rank(list(library.get((reg["competition"], season), [])))
                if ranked:
                    coverage = "partial"
                    coverage_text = "Classement partiel calculé uniquement sur les feuilles/matchs officiels disponibles"
                else:
                    coverage = "awaiting"
                    coverage_text = "Données buteuses officielles en attente"
            season_rows.append({
                "season": season,
                "relative": "Saison en cours" if index == 0 else f"N-{index}",
                "rows": ranked,
                "coverage": coverage,
                "coverage_text": coverage_text,
            })
        aliases = sorted({reg["competition"], *reg.get("aliases", [])})
        groups.append({
            "key": reg["key"],
            "country": reg["country"],
            "competition": reg["competition"],
            "level": reg["level"],
            "aliases": aliases,
            "seasons": season_rows,
        })

    return {
        "seasons": seasons,
        "groups": groups,
        "current_season": seasons[0],
        "policy": (
            "Saison en cours + N-1 + N-2 + N-3. Les classements complets utilisent une source officielle; "
            "les agrégats de matchs isolés restent marqués partiels et aucune statistique manquante n'est inventée."
        ),
    }
