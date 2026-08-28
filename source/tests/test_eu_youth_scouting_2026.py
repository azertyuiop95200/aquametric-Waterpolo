from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from db import Base
from models import ScoutingPlayer, ScoutingTeam
from services.scouting_eu_2026 import (
    COMPETITIONS,
    EU_YOUTH_2026_PLAYER_COUNT,
    PROSPECT_ROWS,
)
from services.scouting_eu_2026_runtime import seed_eu_youth_2026_safe


def test_eu_youth_2026_shortlist_shape():
    assert EU_YOUTH_2026_PLAYER_COUNT == 62
    assert len(PROSPECT_ROWS) == 62
    assert set(COMPETITIONS) == {"u16-world", "u18-world", "u20-europe"}
    assert {row[6] for row in PROSPECT_ROWS} <= {"PRIORITÉ A", "PRIORITÉ B", "À SUIVRE", "PROFIL"}
    assert all(0 <= row[5] <= 15 for row in PROSPECT_ROWS)


def test_reference_priority_profiles_are_present():
    assert any(row[3] == "Afroditi Bitsakou" and row[5] == 13 for row in PROSPECT_ROWS)
    assert any(row[3] == "Julia Teodoro" and row[5] == 13 for row in PROSPECT_ROWS)
    assert any(row[3] == "Kata Hajdu" and row[5] == 13 for row in PROSPECT_ROWS)


def test_u18_snapshot_is_explicitly_partial():
    assert "partial" in COMPETITIONS["u18-world"]["status"]
    assert "18 août 2026" in COMPETITIONS["u18-world"]["data"]


def test_eu_youth_seed_persists_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'eu-youth.db'}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        seed_eu_youth_2026_safe(db)
        # A second pass must update the same reference rows, not duplicate them.
        seed_eu_youth_2026_safe(db)

        teams = db.scalars(
            select(ScoutingTeam).where(ScoutingTeam.external_key.like("eu-youth-2026-%"))
        ).all()
        team_ids = [team.id for team in teams]
        player_count = db.scalar(
            select(func.count(ScoutingPlayer.id)).where(ScoutingPlayer.scouting_team_id.in_(team_ids))
        )

        assert len(teams) == 22
        assert player_count == 62
        assert all(team.name for team in teams)
        assert all(team.team_type == "national_team" for team in teams)
