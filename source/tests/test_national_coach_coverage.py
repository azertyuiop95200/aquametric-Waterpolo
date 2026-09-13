from types import SimpleNamespace

from services.coach_data import COACH_SEEDS
from services.coach_biography import coach_biography_for


def _seed(name):
    return next(row for row in COACH_SEEDS if row["name"] == name)


def test_current_national_staff_use_federation_sources():
    for name in ("Lorène Derenty", "Stefania Giuliani", "Jordi Valls", "Maurizio Mirarchi"):
        row = _seed(name)
        assert row["team_type"] == "national_team"
        assert row["status"] == "federation_official_current"
        assert row["source"].startswith("http")
        assert row["confidence"] >= .99


def test_national_coach_history_is_separate_from_match_rating():
    for name in ("Lorène Derenty", "Stefania Giuliani", "Jordi Valls", "Maurizio Mirarchi"):
        coach = SimpleNamespace(canonical_name=name, source_url=_seed(name)["source"], evaluation_overall=None)
        bio = coach_biography_for(coach)
        assert bio["career"]
        assert bio["verified_fact_count"] >= 1
        assert any("non notée" in gap for gap in bio["research_gaps"])


def test_jordi_valls_world_medal_is_explicitly_sourced():
    coach = SimpleNamespace(canonical_name="Jordi Valls", source_url=_seed("Jordi Valls")["source"], evaluation_overall=None)
    bio = coach_biography_for(coach)
    assert any("bronze" in item["title"].lower() for item in bio["honours"])
    assert all(item["url"].startswith("http") for item in bio["career"] + bio["honours"])
