from types import SimpleNamespace

from services.player_biography import CURATED
from services.coach_biography import coach_biography_for
from services.ratings import build_detailed_evaluation


def event(kind, phase="auto"):
    return SimpleNamespace(event_type=kind, context_meta=SimpleNamespace(phase_tag=phase))


def test_priority_player_profiles_have_verified_history_and_honours():
    for name in ("Emily Ausmus", "Elena Ruiz", "Iva Rozic", "Isabel Piralkova", "Rumina Edgerton", "Morgane Le Berre", "Capucine Pillais"):
        row = CURATED[name]
        assert row.get("career")
        assert row.get("honours")
        assert all(f.get("url", "").startswith("http") for f in row["career"] + row["honours"])


def test_coach_biographies_separate_career_and_honours_from_performance_rating():
    for name in ("Veronika Lapina", "Tristan Colaço", "Thomas Michaeli"):
        coach = SimpleNamespace(canonical_name=name, source_url="", evaluation_overall=None)
        bio = coach_biography_for(coach)
        assert bio["career"]
        assert bio["honours"]
        assert bio["completeness"] >= 60
        assert any("non notée" in gap for gap in bio["research_gaps"])


def test_rating_v3_shrinks_tiny_samples_toward_neutral():
    one_goal = build_detailed_evaluation([event("goal", "even_attack")], role="Field player")
    rich_sample = build_detailed_evaluation([
        event("goal", "power_play"), event("goal", "counterattack"), event("assist", "power_play"),
        event("key_pass", "even_attack"), event("interception", "even_defence"), event("block", "penalty_kill"),
        event("recovery", "even_defence"), event("fast_recovery", "defensive_recovery"), event("duel_won", "even_defence"),
        event("pass_complete", "even_attack"), event("shot_on_target", "even_attack"), event("exclusion_earned", "centre_play"),
    ], role="Field player")
    assert one_goal["engine_version"] == "rating-v3"
    assert one_goal["overall"] is not None
    assert abs(one_goal["overall"] - 50) < abs(rich_sample["overall"] - 50)
    assert one_goal["confidence_score"] < rich_sample["confidence_score"]
    assert 0 <= rich_sample["coverage_score"] <= 1
