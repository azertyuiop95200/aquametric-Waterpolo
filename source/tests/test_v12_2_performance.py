from pathlib import Path
from types import SimpleNamespace

from services.performance_intelligence import team_performance_report, player_match_breakdown, shot_preference_summary
from services.ratings import build_detailed_evaluation


def ev(kind, second, perspective="for", phase="auto", player_id=1):
    meta = SimpleNamespace(perspective=perspective, phase_tag=phase)
    return SimpleNamespace(event_type=kind, second=second, context_meta=meta, player_id=player_id)


def test_team_performance_report_is_evidence_bound():
    events = [
        ev("power_play_start", 0, phase="power_play"),
        ev("pass_complete", 2, phase="power_play"),
        ev("key_pass", 4, phase="power_play"),
        ev("goal", 6, phase="power_play"),
        ev("shot_on_target", 18), ev("shot_off_target", 25),
        ev("recovery", 31), ev("block", 35), ev("duel_won", 39),
        ev("counterattack_start", 50, phase="counterattack"),
        ev("pass_complete", 53, phase="counterattack"), ev("goal", 57, phase="counterattack"),
        ev("defensive_recovery_start", 80, phase="defensive_recovery"), ev("fast_recovery", 84, phase="defensive_recovery"),
        ev("shot_on_target", 100, perspective="against"), ev("goal", 104, perspective="against"),
    ]
    report = team_performance_report(SimpleNamespace(events=events))
    assert report["overall"] is not None
    assert report["event_count"] == len(events)
    assert any(d["label"] == "Attack" and d["available"] for d in report["dimensions"])
    assert any(d["label"] == "Tactical execution" and d["available"] for d in report["dimensions"])


def test_team_performance_does_not_invent_sparse_dimensions():
    report = team_performance_report(SimpleNamespace(events=[ev("goal", 2)]))
    assert report["overall"] is None
    assert all(not d["available"] for d in report["dimensions"])


def test_player_breakdown_and_shot_preference_guardrails():
    events = [ev("goal", 1), ev("assist", 2), ev("pass_complete", 3), ev("turnover", 4), ev("block", 5)]
    detail = build_detailed_evaluation(events, role="perimeter")
    breakdown = player_match_breakdown(events, detail)
    assert breakdown["technical_score"] is not None
    assert breakdown["tactical_score"] is not None
    assert shot_preference_summary({"count": 2})["available"] is False
    pref = shot_preference_summary({
        "count": 6,
        "pool_bins": [[3, 2, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]],
        "goal_bins": [[0, 0, 4], [0, 1, 0], [0, 0, 1]],
        "confidence": .8,
    })
    assert pref["available"] is True
    assert "Left-side" in pref["origin"]
    assert "High right" in pref["target"]


def test_v12_2_routes_and_template_are_integrated():
    from main import app
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/matches/{match_id}/performance" in paths
    template = Path(__file__).resolve().parents[1] / "templates" / "match_intelligence.html"
    text = template.read_text(encoding="utf-8")
    assert 'id="performance-intelligence"' in text
    assert 'id="integrated-media"' in text
    assert 'id="player-performance-lab"' in text
