from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from db import Base
from models import ScoutingPlayer, ScoutingTeam
from services.scouting_eu_2026 import (
    COMPETITIONS,
    EU_YOUTH_2026_PLAYER_COUNT,
    PROSPECT_ROWS,
)
from services.scouting_eu_2026_final import FINAL_UPDATES
from services.scouting_eu_2026_runtime import seed_eu_youth_2026_safe


def test_eu_youth_2026_base_shortlist_shape():
    assert EU_YOUTH_2026_PLAYER_COUNT == 62
    assert len(PROSPECT_ROWS) == 62
    assert set(COMPETITIONS) == {"u16-world", "u18-world", "u20-europe"}
    assert {row[6] for row in PROSPECT_ROWS} <= {"PRIORITÉ A", "PRIORITÉ B", "À SUIVRE", "PROFIL"}
    assert all(0 <= row[5] <= 15 for row in PROSPECT_ROWS)


def test_reference_priority_profiles_are_present():
    assert any(row[3] == "Afroditi Bitsakou" and row[5] == 13 for row in PROSPECT_ROWS)
    assert any(row[3] == "Julia Teodoro" and row[5] == 13 for row in PROSPECT_ROWS)
    assert any(row[3] == "Kata Hajdu" and row[5] == 13 for row in PROSPECT_ROWS)


def test_base_u18_snapshot_is_preserved_for_provenance():
    assert "partial" in COMPETITIONS["u18-world"]["status"]
    assert "18 août 2026" in COMPETITIONS["u18-world"]["data"]


def test_final_u18_overlay_contains_new_final_tournament_profiles():
    names = {row[2] for row in FINAL_UPDATES}
    assert {"Nefeli Krassa", "Marjolein de Gier", "Orsolya Horvath"} <= names
    assert any(row[2] == "Kincso Kenez" and row[6] == 13 for row in FINAL_UPDATES)


def test_eu_youth_seed_persists_final_overlay_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'eu-youth.db'}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        seed_eu_youth_2026_safe(db)
        seed_eu_youth_2026_safe(db)

        teams = db.scalars(
            select(ScoutingTeam).where(ScoutingTeam.external_key.like("eu-youth-2026-%"))
        ).all()
        team_ids = [team.id for team in teams]
        players = db.scalars(
            select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id.in_(team_ids))
        ).all()

        assert len(teams) == 23
        assert len(players) == 65
        assert all(team.name for team in teams)
        assert all(team.team_type == "national_team" for team in teams)

        u18_teams = [team for team in teams if team.age_group == "U18"]
        assert len(u18_teams) == 8
        assert all(team.roster_status == "completed_official_scouting" for team in u18_teams)

        names = {player.name for player in players}
        assert {"Nefeli Krassa", "Marjolein de Gier", "Orsolya Horvath"} <= names
        assert db.scalar(select(func.count(ScoutingPlayer.id)).where(ScoutingPlayer.scouting_team_id.in_(team_ids))) == 65
