"""Safe runtime seeding for the summer-2026 EU youth scouting shortlist.

This module deliberately reuses the curated data in scouting_eu_2026 while
persisting required ScoutingTeam fields before the first flush. It also keeps
seeding idempotent across application restarts. The original U18 snapshot is
then overlaid with final-tournament evidence now that the event is complete.
"""

from collections import defaultdict

from sqlalchemy import select

from models import ScoutingPlayer, ScoutingTeam
from services.scouting_eu_2026 import COMPETITIONS, PROSPECT_ROWS, SOURCES, _player_note, _status_for
from services.scouting_eu_2026_final import apply_final_u18_updates


def seed_eu_youth_2026_safe(db):
    grouped = defaultdict(list)
    for row in PROSPECT_ROWS:
        grouped[(row[0], row[1], row[2])].append(row)

    for (competition_key, country, nationality), players in grouped.items():
        cfg = COMPETITIONS[competition_key]
        slug = country.lower().replace(" ", "-")
        external_key = f"eu-youth-2026-{competition_key}-{slug}"
        top_score = max(p[5] for p in players)

        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == external_key))
        is_new = team is None
        if is_new:
            team = ScoutingTeam(external_key=external_key)
            db.add(team)

        # Required fields are set before the first flush. This is important
        # because ScoutingTeam.name is NOT NULL.
        team.name = f"{country} — Women {cfg['age']} · EU Scout 2026"
        team.team_type = "national_team"
        team.category = "Women"
        team.age_group = cfg["age"]
        team.country = country
        team.competition = cfg["name"]
        team.season_label = "Summer 2026"
        team.roster_status = cfg["status"]
        team.source_url = SOURCES[cfg["source"]]
        team.source_note = (
            f"EU-eligible youth scouting shortlist · {len(players)} profils · meilleur indice {top_score}/15. "
            f"{cfg['data']}. Filtre conservateur: sélection d’un État membre de l’UE; aucune double nationalité supposée."
        )
        team.priority = 85 + top_score

        if is_new:
            db.flush()

        existing = {
            p.name: p
            for p in db.scalars(
                select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id == team.id)
            ).all()
        }
        for row in players:
            (
                _, _, _, name, role, score, level, total, peak_goals, peak_saves,
                distinction, performance, source_key,
            ) = row
            player = existing.get(name)
            if player is None:
                player = ScoutingPlayer(scouting_team_id=team.id, name=name)
                db.add(player)
            player.cap_number = None
            player.birth_year = None
            player.nationality = nationality
            player.role = f"{role} · {level} · {score}/15"
            player.source_season = "Summer 2026"
            player.source_url = SOURCES[source_key]
            player.source_quality = "official_tournament_report"
            player.current_status = _status_for(level)
            player.note = _player_note(
                total, peak_goals, peak_saves, distinction, performance, score, level
            )

    # Final World Aquatics reporting supersedes the original J1-J2 U18 snapshot
    # for runtime scouting, while the base dataset remains preserved for provenance.
    apply_final_u18_updates(db)
    db.commit()


def install_scouting_seed_patch():
    """Wrap the existing shared scouting seed with the safe EU-youth seed."""
    import services.scouting_data as base

    if getattr(base.seed_scouting, "_eu_youth_2026_safe_patch", False):
        return

    # If the first implementation already wrapped the seed in this process,
    # unwrap it so the legacy buggy EU seeder is not invoked twice.
    original_seed = base.seed_scouting
    wrapped_original = getattr(original_seed, "_eu_youth_2026_original", None)
    if wrapped_original is not None:
        original_seed = wrapped_original

    def seed_with_eu_youth(db):
        original_seed(db)
        seed_eu_youth_2026_safe(db)

    seed_with_eu_youth._eu_youth_2026_safe_patch = True
    seed_with_eu_youth._eu_youth_2026_original = original_seed
    base.seed_scouting = seed_with_eu_youth
