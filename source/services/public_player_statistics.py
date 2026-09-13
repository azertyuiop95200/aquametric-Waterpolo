"""Public totals scoped to a team/person and distinct match, with coverage."""
from collections import defaultdict, Counter

FIELDS = ("goals", "shots", "saves", "assists", "steals", "exclusions")


def public_player_rows(stats, roster, team_names):
    groups = defaultdict(list)
    for row in stats:
        groups[(row.team_name, row.player_name)].append(row)
    identities = {(team_names.get(p.scouting_team_id, ""), p.name): p for p in roster}
    rows = []
    for key in sorted(set(groups) | set(identities)):
        team, name = key
        matches = defaultdict(list)
        for stat in groups[key]:
            matches[stat.library_match_id].append(stat)
        totals, coverage = {}, {}
        conflicts = 0
        for field in FIELDS:
            values = []
            for entries in matches.values():
                candidates = {getattr(row, field, None) for row in entries} - {None}
                if len(candidates) == 1:
                    values.append(candidates.pop())
                elif len(candidates) > 1:
                    conflicts += 1
            totals[field] = sum(values) if values else None
            coverage[field] = len(values)
        person = identities.get(key)
        rows.append({"name": name, "team": team, "nationality": getattr(person, "nationality", ""),
            "role": getattr(person, "role", ""), "matches": len(matches), **totals,
            "metric_coverage": coverage, "conflicts": conflicts, "has_data": any(coverage.values()),
            "coverage": "Données publiques partielles" if any(coverage.values()) else "Effectif ou données non renseignées"})
    names = Counter(row["name"] for row in rows)
    for row in rows:
        row["ambiguous_name"] = names[row["name"]] > 1
    return sorted(rows, key=lambda row: (-row["matches"], row["name"], row["team"]))
