from pathlib import Path
from types import SimpleNamespace

from services.performance_intelligence import player_match_breakdown, _statboard, _loss_breakdown, _transition_timing

ROOT = Path(__file__).resolve().parents[1]


def ev(second, kind, note="", phase="auto", perspective="for"):
    return SimpleNamespace(
        second=second,
        event_type=kind,
        note=note,
        context_meta=SimpleNamespace(phase_tag=phase, perspective=perspective, quality_tag=""),
    )


def test_shot_pass_and_turnover_percentages_are_denominator_based():
    events = [
        ev(1, "goal"), ev(2, "shot_on_target"), ev(3, "shot_off_target"), ev(4, "shot_blocked"),
        ev(5, "pass_complete"), ev(6, "pass_complete"), ev(7, "bad_pass"), ev(8, "turnover"),
    ]
    board = _statboard(events)
    assert board["shots"] == 4
    assert board["shot_accuracy_pct"] == 50.0
    assert board["scoring_efficiency_pct"] == 25.0
    assert board["passes_completed"] == 2
    assert board["passes_failed"] == 1
    assert board["pass_completion_pct"] == 66.7
    assert board["turnovers"] == 2


def test_loss_reason_breakdown_returns_percent_share():
    events = [
        ev(1, "bad_pass", "centre entry forced"),
        ev(2, "bad_pass", "late pass"),
        ev(3, "turnover", "offensive foul push off"),
        ev(4, "turnover", "counterattack handling"),
    ]
    result = _loss_breakdown(events)
    assert result["total"] == 4
    assert round(sum(x["share"] for x in result["rows"]), 1) == 100.0
    labels = {x["label"] for x in result["rows"]}
    assert "Entrée centre perdue" in labels
    assert "Faute offensive" in labels


def test_transition_timings_use_real_timestamps_and_explicit_speed_tags_only():
    events = [
        ev(10, "counterattack_start"), ev(12.4, "pass_complete"), ev(16, "shot_on_target", "shot_speed_kmh=68.5 release_time_s=0.72"),
        ev(30, "defensive_recovery_start"), ev(34.5, "fast_recovery", "sprint_5m_s=3.2"),
    ]
    timing = _transition_timing(events)
    assert timing["defence_to_attack_first_pass_s"] == 2.4
    assert timing["defence_to_attack_shot_s"] == 6.0
    assert timing["attack_to_defence_shape_s"] == 4.5
    assert timing["measured"]["shot_speed_kmh"]["avg"] == 68.5
    assert timing["measured"]["sprint_5m_s"]["avg"] == 3.2
    assert timing["measured"]["sprint_10m_s"]["avg"] is None


def test_player_breakdown_has_position_specific_qualitative_layer():
    detail = {"rated": False, "dimensions": {}}
    wing = player_match_breakdown([ev(1, "pass_complete")], detail, role="Wing")
    keeper = player_match_breakdown([ev(1, "save")], detail, role="Goalkeeper")
    assert wing["position_family"] == "wing"
    assert any("Hauteur réelle" in x and "largeur" in x for x in wing["qualitative_checklist"])
    assert keeper["position_family"] == "goalkeeper"
    assert any("première passe" in x.lower() for x in keeper["qualitative_checklist"])


def test_elite_analyst_lab_covers_priority_national_programmes_and_rankings():
    html = (ROOT / "static" / "elite-analyst-lab.html").read_text(encoding="utf-8")
    for needle in ["France Senior", "France U20", "Russie Senior", "Russie U20", "Israël Senior", "Israël U20", "Top 12 mondial", "Top 12 Europe"]:
        assert needle in html
    assert "a5Ja269h5G8" in html
    assert "VvuJSTuuUI8" in html
    assert "mesuré" in html and "calculé" in html and "qualitatif" in html
    assert "2–3 m" in html


def test_old_generic_video_atlas_is_retired_in_favour_of_evidence_based_film_room():
    html = (ROOT / "static" / "elite-video-atlas.html").read_text(encoding="utf-8")
    assert "/analysis-library#filmroom" in html
    assert "L’ancien atlas a été retiré" in html
    assert "trois croquis génériques" in html
    assert "reconstructions pédagogiques" not in html
    assert "data-defenders" not in html


def test_tactical_board_audit_corrects_special_teams_and_displays_personnel():
    js = (ROOT / "static" / "tactical-board-audit.js").read_text(encoding="utf-8")
    assert "board-personnel" in js
    assert "X6" in js
    assert "expectedDefenders='5'" in js
    assert "circle.d" in js


def test_v122_release_marker_is_explicit():
    release = (ROOT / "static" / "release.json").read_text(encoding="utf-8")
    assert "AQUAMETRIC_V12_2_ULTIMATE_MATCH_VIDEO_INTELLIGENCE_2026_09_05" in release
    assert '"product_version": "12.2.0"' in release
    assert '"analysis_engine": "ultimate-analyst-v2.0"' in release
    assert "up_to_72_evidence_sequences" in release
    assert "complete_analysis_zip_export" in release
    assert "automatic_video_measurement_matrix" in release
    assert "complete_measured_analytics_surface" in release


def test_base_loads_engineering_and_tactical_audit_assets():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "/static/elite-analyst.css?v=12.2.0" in base
    assert "/static/elite-analyst.js?v=12.2.0" in base
    assert "/static/tactical-board-audit.js?v=12.2.0" in base
    assert 'data-product-version="12.2.0"' in base
