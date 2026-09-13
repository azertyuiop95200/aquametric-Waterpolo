"""Final U18 2026 enrichment for the EU youth scouting shortlist.

The first scouting import was intentionally frozen after the opening U18 group
matches. The tournament finished on 23 August 2026, so this overlay promotes the
U18 cards to completed evidence and adds final-tournament totals / awards from
World Aquatics without rewriting the historical base dataset.
"""

from sqlalchemy import select

from models import ScoutingPlayer, ScoutingTeam
from services.scouting_eu_2026 import _player_note, _status_for

U18_FINAL = "https://www.worldaquatics.com/news/4565141/all-conquering-australia-upsets-spain-with-first-u18-crown"
U18_SEMIFINALS = "https://www.worldaquatics.com/news/4564707/spain-to-defend-u18-crown-against-australia"
U18_DAY3 = "https://www.worldaquatics.com/news/4561792/greece-and-spain-emerge-top-in-u18-major-groups"

SOURCES = {"final": U18_FINAL, "semifinals": U18_SEMIFINALS, "day3": U18_DAY3}

# country, ISO3, player, role, score/15, level, total, peak goals, peak saves,
# distinction, reference performance, source key
FINAL_UPDATES = [
    ("Hungary","HUN","Kincso Kenez","Captain / field player",11,"PRIORITÉ B",13,4,0,"Media All-Star Team","13 buts au tournoi; 2 buts dans le match pour le bronze","final"),
    ("Greece","GRE","Nefeli Krassa","Captain / field player",11,"PRIORITÉ B",15,3,0,"Media All-Star Team","15 buts, meilleur total grec; 3 buts en demi de classement puis 2 pour la 5e place","final"),
    ("Netherlands","NED","Marjolein de Gier","Field player",11,"PRIORITÉ B",23,6,0,"Media All-Star Team","23 buts au tournoi; 6 buts dans le match pour la 7e place","final"),
    ("Italy","ITA","Malika Bovo","Field player",9,"PRIORITÉ B",20,5,0,"","20 buts au tournoi; 5 en demi de classement et 4 contre la Croatie","final"),
    ("Croatia","CRO","Neli Jankovic","Senior international / field player",9,"PRIORITÉ B",16,5,0,"","16 buts au tournoi; 5 contre l'Italie dans le match pour la 9e place","final"),
    ("Croatia","CRO","Lara Srhoj","Senior international / field player",9,"PRIORITÉ B",17,5,0,"","17 buts au tournoi; 5 en demi de classement et 4 contre l'Italie","final"),
    ("Spain","ESP","Queralt Anton","Senior international / captain",10,"PRIORITÉ B",12,3,0,"","12 buts au tournoi; 2 en finale mondiale et responsabilités de capitaine","final"),
    ("Spain","ESP","Ona Jurado","Field player",9,"PRIORITÉ B",12,4,0,"","12 buts au tournoi; 2 en finale mondiale","final"),
    ("Greece","GRE","Androniki Karagianni","Field player",8,"À SUIVRE",11,4,0,"","11 buts au tournoi; 4 buts dans le match pour la 5e place","final"),
    ("Hungary","HUN","Orsolya Horvath","Goalkeeper",8,"À SUIVRE",None,0,11,"","11 arrêts dans le match pour le bronze contre les États-Unis","final"),
    ("Hungary","HUN","Mandula Mihok","Centre",9,"PRIORITÉ B",None,4,0,"All-Star U16 2026 (autre compétition)","But de centre dans le match pour le bronze; présence jusqu'au Final Four U18","final"),
    ("Spain","ESP","Martina Fernandez","Field player",8,"À SUIVRE",None,3,0,"","Hat-tricks contre Croatie, USA, Chine et Hongrie; médaille d'argent U18","semifinals"),
    ("Spain","ESP","Marina Munoz","Field player",8,"À SUIVRE",None,4,0,"","4 buts contre Croatie puis 4 contre USA; encore buteuse en demi-finale","semifinals"),
]


def _u18_key(country):
    return f"eu-youth-2026-u18-world-{country.lower().replace(' ', '-')}"


def apply_final_u18_updates(db):
    """Apply final U18 evidence idempotently and return the number of player rows touched."""
    # Promote every already-seeded U18 team to a completed tournament status,
    # including teams for which no individual final-tournament enrichment is added.
    existing_u18 = db.scalars(
        select(ScoutingTeam).where(ScoutingTeam.external_key.like("eu-youth-2026-u18-world-%"))
    ).all()
    for team in existing_u18:
        team.roster_status = "completed_official_scouting"
        team.source_url = U18_FINAL
        team.source_note = (
            "EU-eligible youth scouting shortlist · U18 tournament completed 23 Aug 2026. "
            "Final World Aquatics reporting is now the reference layer; unknown individual metrics remain unknown."
        )

    touched = 0
    for country, nationality, name, role, score, level, total, peak_goals, peak_saves, distinction, performance, source_key in FINAL_UPDATES:
        key = _u18_key(country)
        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == key))
        if team is None:
            team = ScoutingTeam(
                external_key=key,
                name=f"{country} — Women U18 · EU Scout 2026",
                team_type="national_team",
                category="Women",
                age_group="U18",
                country=country,
                competition="World Aquatics Women's U18 Water Polo Championships 2026",
                season_label="Summer 2026",
                roster_status="completed_official_scouting",
                source_url=U18_FINAL,
                source_note=(
                    "EU-eligible youth scouting shortlist · U18 tournament completed 23 Aug 2026. "
                    "Final World Aquatics reporting is the reference layer."
                ),
                priority=85 + score,
            )
            db.add(team)
            db.flush()
        else:
            team.roster_status = "completed_official_scouting"
            team.source_url = U18_FINAL
            team.priority = max(team.priority or 0, 85 + score)

        player = db.scalar(
            select(ScoutingPlayer).where(
                ScoutingPlayer.scouting_team_id == team.id,
                ScoutingPlayer.name == name,
            )
        )
        if player is None:
            player = ScoutingPlayer(scouting_team_id=team.id, name=name)
            db.add(player)
        player.nationality = nationality
        player.role = f"{role} · {level} · {score}/15"
        player.source_season = "Summer 2026"
        player.source_url = SOURCES[source_key]
        player.source_quality = "official_tournament_report"
        player.current_status = _status_for(level)
        player.note = _player_note(total, peak_goals, peak_saves, distinction, performance, score, level)
        touched += 1

    return touched
