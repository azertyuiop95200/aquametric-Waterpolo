from pathlib import Path
from types import SimpleNamespace

from services.player_deep_metrics import player_deep_metrics, team_player_totals

ROOT = Path(__file__).resolve().parents[1]


def ev(kind, second=0, note=""):
    return SimpleNamespace(event_type=kind, second=second, note=note)


def test_player_deep_metrics_cover_touches_passes_duels_time_and_distance():
    player = SimpleNamespace(id=7, name="Test Player", cap_number=4, primary_role="Wing")
    events = [
        ev("touch", 10, "playing_time_s=1200; distance_total_m=860; max_swim_speed_mps=1.92"),
        ev("centre_touch", 20), ev("pass_complete", 30), ev("pass_complete", 40),
        ev("bad_pass", 50), ev("goal", 60, "shot_speed_kmh=56; shot_distance_m=5.2"),
        ev("shot_off_target", 70), ev("duel_won", 80), ev("duel_lost", 90),
        ev("turnover", 100), ev("interception", 110), ev("exclusion_earned", 120),
    ]
    row = player_deep_metrics(player, events)
    assert row["touches"] == 2
    assert row["centre_touches"] == 1
    assert row["passes_completed"] == 2
    assert row["passes_failed"] == 1
    assert row["pass_completion_pct"] == 66.7
    assert row["duel_success_pct"] == 50.0
    assert row["playing_time_min"] == 20.0
    assert row["physical"]["distance_m"] == 860.0
    assert row["physical"]["max_swim_speed_mps"] == 1.92
    assert row["physical"]["shot_speed_kmh_avg"] == 56.0


def test_physical_metrics_do_not_invent_values_without_tags():
    player = SimpleNamespace(id=1, name="No Calibration", cap_number=1, primary_role="Field")
    row = player_deep_metrics(player, [ev("touch", 1), ev("pass_complete", 2)])
    assert row["playing_time_s"] is None
    assert row["physical"]["distance_m"] is None
    assert row["physical"]["max_swim_speed_mps"] is None
    assert row["physical"]["shot_speed_kmh_avg"] is None


def test_team_totals_preserve_denominators():
    players = [
        {"touches": 5, "centre_touches": 1, "ball_actions_tagged": 8, "passes_completed": 4, "passes_failed": 1, "pass_attempts": 5, "key_passes": 1, "assists": 0, "actions_created": 0, "shots": 2, "goals": 1, "shots_on_target": 1, "shots_off_target": 1, "shots_blocked": 0, "turnovers": 1, "duels": 2, "duels_won": 1, "duels_lost": 1, "interceptions": 0, "recoveries": 0, "blocks": 0, "saves": 0, "exclusions_earned": 0, "exclusions_committed": 0, "playing_time_s": 600, "physical": {"distance_m": 300}},
        {"touches": 3, "centre_touches": 0, "ball_actions_tagged": 5, "passes_completed": 2, "passes_failed": 0, "pass_attempts": 2, "key_passes": 0, "assists": 0, "actions_created": 0, "shots": 1, "goals": 0, "shots_on_target": 0, "shots_off_target": 1, "shots_blocked": 0, "turnovers": 0, "duels": 0, "duels_won": 0, "duels_lost": 0, "interceptions": 1, "recoveries": 0, "blocks": 0, "saves": 0, "exclusions_earned": 0, "exclusions_committed": 0, "playing_time_s": None, "physical": {"distance_m": None}},
    ]
    totals = team_player_totals(players)
    assert totals["touches"] == 8
    assert totals["passes_completed"] == 6
    assert totals["pass_attempts"] == 7
    assert totals["pass_completion_pct"] == 85.7
    assert totals["players_with_playing_time"] == 1
    assert totals["players_with_distance"] == 1


def test_v122_player_matrix_assets_and_endpoint_are_wired():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "player-metrics-v122.css?v=12.2.0.2" in base
    assert "player-metrics-v122.js?v=12.2.0.2" in base
    security = (ROOT / "security.py").read_text(encoding="utf-8")
    assert "player_metrics_router" in security
    route = (ROOT / "player_metrics_routes.py").read_text(encoding="utf-8")
    assert "/api/v122/matches/{match_id}/player-metrics" in route
    js = (ROOT / "static" / "player-metrics-v122.js").read_text(encoding="utf-8")
    for label in ["Temps de jeu", "Ballons touchés", "Passes réussies", "Duels G/P", "Distance parcourue", "Jusqu’à 72 séquences"]:
        assert label in js


def test_ingest_generates_dense_media_and_board_audit_is_strict():
    ingest = (ROOT / "premium_ingest_routes.py").read_text(encoding="utf-8")
    assert "max_targets=72, max_clips=48, max_image_targets=72, triple_frames=48" in ingest
    audit = (ROOT / "static" / "tactical-board-audit.js").read_text(encoding="utf-8")
    assert "data.personnelValid" not in audit
    assert "svg.dataset.personnelValid" in audit
    assert "attendu" in audit
    assert "6v5 / 5v6" in audit
