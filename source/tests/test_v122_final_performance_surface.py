from pathlib import Path
from types import SimpleNamespace

from services.player_deep_metrics import player_deep_metrics

ROOT = Path(__file__).resolve().parents[1]


def _event(kind, second=0, note="", phase="auto"):
    return SimpleNamespace(
        event_type=kind,
        second=second,
        note=note,
        context_meta=SimpleNamespace(phase_tag=phase, quality_tag="", perspective="for"),
    )


def test_player_surface_counts_touches_passes_shots_duels_losses_and_phases():
    player = SimpleNamespace(id=7, name="Test Player", cap_number=7, primary_role="Wing")
    events = [
        _event("touch", 1, phase="even_attack"),
        _event("centre_touch", 2, phase="centre_play"),
        _event("pass_complete", 3, phase="even_attack"),
        _event("pass_complete", 4, phase="even_attack"),
        _event("bad_pass", 5, "centre entry", phase="even_attack"),
        _event("goal", 6, phase="power_play"),
        _event("shot_off_target", 7, phase="even_attack"),
        _event("duel_won", 8, phase="even_defence"),
        _event("duel_lost", 9, phase="even_defence"),
        _event("interception", 10, phase="even_defence"),
        _event("exclusion_earned", 11, phase="centre_play"),
        _event("counterattack_start", 12, phase="counterattack"),
        _event("fast_recovery", 13, phase="defensive_recovery"),
    ]
    row = player_deep_metrics(player, events)
    assert row["touches"] == 2
    assert row["centre_touches"] == 1
    assert row["passes_completed"] == 2
    assert row["passes_failed"] == 1
    assert row["pass_completion_pct"] == 66.7
    assert row["goals"] == 1 and row["shots"] == 2
    assert row["duels"] == 2 and row["duel_success_pct"] == 50.0
    assert row["turnovers"] == 1
    assert row["loss_breakdown"][0]["key"] == "centre_entry"
    assert row["interceptions"] == 1
    assert row["exclusions_earned"] == 1
    assert row["counterattack_starts"] == 1
    assert row["fast_recoveries"] == 1
    assert row["phases"]["even_attack"] >= 1


def test_playing_time_distance_and_physical_values_require_explicit_tags():
    player = SimpleNamespace(id=3, name="Measured", cap_number=3, primary_role="Driver")
    empty = player_deep_metrics(player, [_event("touch", 1)])
    assert empty["playing_time_s"] is None
    assert empty["physical"]["distance_m"] is None
    assert empty["physical"]["max_swim_speed_mps"] is None

    measured = player_deep_metrics(player, [
        _event("touch", 1, "playing_time_s=1260 distance_total_m=1480 max_swim_speed_mps=2.25"),
        _event("shot_on_target", 2, "shot_speed_kmh=54.2 shot_distance_m=6.1 release_time_s=0.72"),
        _event("shot_on_target", 3, "shot_speed_kmh=57.8 shot_distance_m=6.5 release_time_s=0.68"),
        _event("counterattack_start", 4, "sprint_10m_s=6.4"),
    ])
    assert measured["playing_time_min"] == 21.0
    assert measured["physical"]["distance_m"] == 1480.0
    assert measured["physical"]["max_swim_speed_mps"] == 2.25
    assert measured["physical"]["shot_speed_kmh_avg"] == 56.0
    assert measured["physical"]["shot_speed_kmh_max"] == 57.8
    assert measured["physical"]["shot_distance_m_avg"] == 6.3
    assert measured["physical"]["sprint_10m_s_best"] == 6.4


def test_player_matrix_exposes_large_video_and_image_evidence_wall():
    js = (ROOT / "static" / "player-metrics-v122.js").read_text(encoding="utf-8")
    for needle in [
        "Ballons touchés", "Passes ratées", "Pertes par cause", "Distance parcourue",
        "Vitesse tir max", "EVIDENCE ROOM · VIDEO + IMAGES", "Jusqu’à 72 séquences du match",
        "aqpm-stills", "screenshot_urls",
    ]:
        assert needle in js


def test_tactical_board_audit_has_correct_6v5_and_5v6_personnel_rules():
    js = (ROOT / "static" / "tactical-board-audit.js").read_text(encoding="utf-8")
    assert "return{a:6,d:5,g:1,label:'6v5'}" in js
    assert "return{a:5,d:6,g:1,label:'5v6'}" in js
    assert "removeByLabel(svg,'O6'" in js
    assert "removeByLabel(svg,'X6'" in js
    assert "personnelValid" in js


def test_v122_assets_are_cache_busted_for_final_surface():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "/static/tactical-board-audit.js?v=12.2.0.3" in base
    assert "/static/player-metrics-v122.js?v=12.2.0.3" in base
    assert "/static/player-metrics-v122.css?v=12.2.0.3" in base
