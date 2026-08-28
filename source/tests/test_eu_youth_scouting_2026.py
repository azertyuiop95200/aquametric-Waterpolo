from services.scouting_eu_2026 import (
    COMPETITIONS,
    EU_YOUTH_2026_PLAYER_COUNT,
    PROSPECT_ROWS,
)


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
