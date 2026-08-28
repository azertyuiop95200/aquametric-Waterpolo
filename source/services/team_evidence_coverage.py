from collections import defaultdict

from sqlalchemy import select

from models import ScoutingTeam, ScoutingPlayer, MatchLibraryItem, LibraryPlayerMatchStat


TEAM_ALIASES = {
    "Union St-Bruno Bordeaux": {"Union St-Bruno Bordeaux", "USB Bordeaux", "Union Saint-Bruno Bordeaux"},
    "Taverny Sports Nautiques 95": {"Taverny Sports Nautiques 95", "Taverny SN95", "Taverny"},
    "Sporting Club des Nageurs de Choisy le Roi": {"Sporting Club des Nageurs de Choisy le Roi", "SCN Choisy-le-Roi", "Choisy-le-Roi"},
    "Lille UC Métropole Water-Polo": {"Lille UC Métropole Water-Polo", "Lille UC", "Lille"},
    "Olympic Nice Natation": {"Olympic Nice Natation", "Nice Natation", "Nice"},
    "Grand Nancy Aquatique Club": {"Grand Nancy Aquatique Club", "Grand Nancy AC", "Nancy"},
    "Toulon Waterpolo": {"Toulon Waterpolo", "Toulon Water Polo", "Toulon"},
    "Granville Water Polo": {"Granville Water Polo", "Granville"},
    "Cercle des Nageurs de Marseille": {"Cercle des Nageurs de Marseille", "CN Marseille", "CNM"},
    "United States — Women Senior": {"United States — Women Senior", "United States", "USA"},
    "Spain — Women Senior": {"Spain — Women Senior", "Spain", "ESP"},
    "France — Women Senior": {"France — Women Senior", "France", "FRA"},
}

COUNTRY_CODES = {
    "United States": {"USA", "US"}, "Spain": {"ESP"}, "France": {"FRA"},
    "Greece": {"GRE", "GRC"}, "Italy": {"ITA"}, "Hungary": {"HUN"},
    "Netherlands": {"NED"}, "Canada": {"CAN"}, "Australia": {"AUS"},
    "China": {"CHN"}, "Croatia": {"CRO"}, "New Zealand": {"NZL"},
    "Israel": {"ISR"}, "Mexico": {"MEX"}, "Brazil": {"BRA"},
    "Argentina": {"ARG"}, "South Africa": {"RSA"},
}

PERFORMANCE_FIELDS = ("goals", "saves", "shots", "assists", "steals", "exclusions")
U20_MARKERS = ("u20", "u-20", "under 20", "under-20", "under20")


def aliases_for(team_or_name) -> set[str]:
    """Return safe aliases without confusing senior and age-group scope.

    Team-name aliases resolve spelling/abbreviation only. Competition/age-group
    separation is enforced independently by ``_match_in_scope``.
    """
    if isinstance(team_or_name, str):
        return set(TEAM_ALIASES.get(team_or_name, {team_or_name}))
    team = team_or_name
    aliases = set(TEAM_ALIASES.get(team.name, {team.name}))
    if team.team_type == "national_team" and team.country:
        aliases.add(team.country)
        aliases.update(COUNTRY_CODES.get(team.country, set()))
    return {a for a in aliases if a}


def _is_u20_match(match: MatchLibraryItem) -> bool:
    text = " ".join([
        match.external_key or "", match.title or "", match.competition or "",
    ]).lower()
    return any(marker in text for marker in U20_MARKERS)


def _match_in_scope(team: ScoutingTeam, match: MatchLibraryItem) -> bool:
    if team.team_type != "national_team":
        return True
    age = (team.age_group or "").strip().lower()
    is_u20 = _is_u20_match(match)
    if age == "u20":
        return is_u20
    if age == "senior":
        return not is_u20
    return True


def _matches_for_team(db, team: ScoutingTeam, aliases: set[str]):
    rows = db.scalars(
        select(MatchLibraryItem).where(
            MatchLibraryItem.team_a.in_(aliases) | MatchLibraryItem.team_b.in_(aliases)
        )
    ).all()
    return [row for row in rows if _match_in_scope(team, row)]


def _has_performance_stat(row: LibraryPlayerMatchStat) -> bool:
    return any(getattr(row, field, None) is not None for field in PERFORMANCE_FIELDS)


def team_evidence_coverage(db):
    teams = db.scalars(
        select(ScoutingTeam).order_by(ScoutingTeam.priority.desc(), ScoutingTeam.name)
    ).all()
    output = []
    for team in teams:
        aliases = aliases_for(team)
        roster = db.scalars(
            select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id == team.id)
        ).all()
        matches = _matches_for_team(db, team, aliases)
        match_ids = [m.id for m in matches]
        stats = []
        if match_ids:
            stats = db.scalars(
                select(LibraryPlayerMatchStat).where(
                    LibraryPlayerMatchStat.library_match_id.in_(match_ids),
                    LibraryPlayerMatchStat.team_name.in_(aliases),
                )
            ).all()

        player_names = {p.name for p in roster}
        evidence_players = {s.player_name for s in stats}
        performance_rows = [s for s in stats if _has_performance_stat(s)]
        performance_players = {s.player_name for s in performance_rows}
        performance_match_ids = {s.library_match_id for s in performance_rows}
        lineup_only_match_ids = {s.library_match_id for s in stats if not _has_performance_stat(s)} - performance_match_ids
        official_matches = [m for m in matches if (m.official_source_url or "").strip()]
        evidence_seasons = sorted({m.season for m in matches if (m.season or "").strip()}, reverse=True)

        if performance_match_ids:
            state = "performance_stats"
        elif stats:
            state = "official_lineups"
        elif matches:
            state = "match_results_only"
        elif roster:
            state = "roster_only"
        else:
            state = "research_required"

        # Coverage is a transparent inventory score, not a performance/quality score.
        # It rewards four independently observable layers: roster, matches, player
        # attribution, and performance stats. It is never used in a player's /100.
        roster_layer = 25 if roster else 0
        match_layer = min(25, len(matches) * 5)
        attribution_layer = min(25, len(evidence_players) * 2)
        performance_layer = min(25, len(performance_match_ids) * 5)
        coverage_score = roster_layer + match_layer + attribution_layer + performance_layer

        output.append({
            "team": team,
            "aliases": sorted(aliases),
            "state": state,
            "coverage_score": coverage_score,
            "roster_players": len(player_names),
            "evidence_players": len(evidence_players),
            "performance_players": len(performance_players),
            "official_matches": len(official_matches),
            "documented_matches": len(matches),
            "performance_matches": len(performance_match_ids),
            "lineup_only_matches": len(lineup_only_match_ids),
            "missing_player_evidence": len(player_names - evidence_players),
            "latest_match_id": max(match_ids) if match_ids else None,
            "evidence_seasons": evidence_seasons,
        })
    return output


def coverage_totals(rows):
    by_state = defaultdict(int)
    for row in rows:
        by_state[row["state"]] += 1
    return {
        "teams": len(rows),
        "with_matches": sum(r["documented_matches"] > 0 for r in rows),
        "with_performance": sum(r["performance_matches"] > 0 for r in rows),
        "documented_matches": sum(r["documented_matches"] for r in rows),
        "performance_matches": sum(r["performance_matches"] for r in rows),
        "states": dict(by_state),
    }
