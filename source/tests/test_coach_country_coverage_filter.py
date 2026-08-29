from pathlib import Path


def _coach_directory_js():
    return (Path(__file__).resolve().parents[1] / "static" / "coach-directory.js").read_text(encoding="utf-8")


def test_coach_country_dropdown_only_uses_covered_data():
    js = _coach_directory_js()
    assert "NATIONAL_COUNTRIES" not in js
    assert "function availableCountries()" in js
    assert "Tous les pays couverts" in js
    assert "r.team_type === 'national_team'" in js


def test_country_options_refresh_when_scope_changes():
    js = _coach_directory_js()
    assert "state.season = btn.dataset.season" in js
    assert "state.view = btn.dataset.view" in js
    assert "state.gender=genderSelect.value;countryOptions();render();" in js
    assert js.count("countryOptions();") >= 4
