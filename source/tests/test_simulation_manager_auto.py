from pathlib import Path

from services.simulation import _same_team, simulate_matchup


def test_live_default_upgrades_to_25k_scenarios():
    result = simulate_matchup(
        "Granville Water Polo",
        "Lille UC Métropole Water-Polo",
        n=5000,
        seed=21,
    )
    assert result["n"] == 25000
    assert "confidence" in result
    assert len(result["top_scores"]) >= 3
    assert result["scenarios"]["pessimistic_a"] <= result["scenarios"]["central_a"] <= result["scenarios"]["optimistic_a"]


def test_legacy_manual_performance_inputs_no_longer_control_forecast():
    baseline = simulate_matchup(
        "Granville Water Polo", "Lille UC Métropole Water-Polo",
        n=2400, seed=22, form_a=30, form_b=70, rest_a=0, rest_b=7,
        tactic_a="transition", tactic_b="defence_first", venue="team_a_home",
    )
    inverse = simulate_matchup(
        "Granville Water Polo", "Lille UC Métropole Water-Polo",
        n=2400, seed=22, form_a=70, form_b=30, rest_a=7, rest_b=0,
        tactic_a="defence_first", tactic_b="transition", venue="team_b_home",
    )
    assert baseline["avg_a"] == inverse["avg_a"]
    assert baseline["avg_b"] == inverse["avg_b"]
    assert baseline["win_a"] == inverse["win_a"]
    assert baseline["tactic_a"] == inverse["tactic_a"]
    assert baseline["auto_inputs"] == inverse["auto_inputs"]


def test_absence_availability_is_the_only_primary_manual_performance_correction():
    full = simulate_matchup(
        "Granville Water Polo", "Lille UC Métropole Water-Polo",
        n=4000, seed=23, availability_a=100,
    )
    depleted = simulate_matchup(
        "Granville Water Polo", "Lille UC Métropole Water-Polo",
        n=4000, seed=23, availability_a=82,
    )
    assert depleted["strength_a"] < full["strength_a"]
    assert depleted["win_a"] < full["win_a"]
    assert depleted["auto_inputs"]["availability_a"] == 82


def test_senior_and_u20_labels_are_never_merged():
    assert _same_team("France — Women Senior", "France — Women U20") is False
    assert _same_team("Spain — Women Senior", "Spain — Women U20") is False
    assert _same_team("Granville Water Polo", "Granville") is True


def test_manager_template_exposes_only_teams_and_absence_workflow():
    html = (Path(__file__).parents[1] / "templates" / "match_simulation.html").read_text(encoding="utf-8")
    assert 'name="team_a"' in html and 'name="team_b"' in html
    assert 'name="absences_a"' in html and 'name="absences_b"' in html
    assert 'type="hidden" name="availability_a"' in html
    assert 'name="form_a"' not in html
    assert 'name="rest_a"' not in html
    assert 'name="tactic_a"' not in html
    assert 'name="venue"' not in html
    assert "Le moteur calcule tout" in html
    assert "25K MONTE-CARLO" in html
