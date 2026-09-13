from services.autonomous_engine import infer_candidates, build_auto_summary
from services.scoreboard_ocr import parse_scoreboard_text


def _obs(second, score, *, period=1, clock=400, text="", replay=False, break_flag=False, final=False, conf=0.92):
    h, a = score
    return {
        "second": float(second),
        "home_score": h,
        "away_score": a,
        "period": period,
        "clock_seconds": clock,
        "ocr_confidence": conf,
        "raw_text": text,
        "normalized_text": text,
        "is_replay": replay,
        "is_break": break_flag,
        "is_final": final,
    }


def _goals(candidates):
    return [c for c in candidates if c.event_type.startswith("goal_candidate")]


def test_goal_requires_confirmed_plus_one_scoreboard_increment():
    rows = [
        _obs(0, (0, 0), clock=420),
        _obs(10, (1, 0), clock=410),
        _obs(20, (1, 0), clock=400),
    ]
    candidates = infer_candidates(rows, [{"second": 8, "score": 0.99}])
    goals = _goals(candidates)
    assert len(goals) == 1
    goal = goals[0]
    assert goal.event_type == "goal_candidate_home"
    assert goal.evidence["before"] == [0, 0]
    assert goal.evidence["after"] == [1, 0]
    assert goal.evidence["time_precision"] == "score_bracket_only"
    # The visual peak can be shown for review but is never the asserted goal time.
    assert goal.second == 10.0
    assert goal.evidence["visual_focus_second"] == 8.0
    assert "scoreboard" in goal.evidence["signal"]


def test_visual_replay_cannot_create_a_second_goal():
    rows = [
        _obs(0, (0, 0), clock=420),
        _obs(10, (1, 0), clock=410),
        _obs(20, (1, 0), clock=410, text="REPLAY"),
        _obs(30, (1, 0), clock=400),
    ]
    candidates = infer_candidates(rows, [
        {"second": 9, "score": 0.7},
        {"second": 22, "score": 1.0},  # stronger replay image
    ])
    assert len(_goals(candidates)) == 1
    assert all(c.event_type != "goal_candidate_home" or c.second == 10.0 for c in candidates)


def test_replay_score_overlay_is_ignored_even_if_it_looks_like_increment():
    rows = [
        _obs(0, (0, 0), clock=420),
        _obs(10, (1, 0), clock=410, text="REPLAY", replay=True),
        _obs(20, (0, 0), clock=405),
        _obs(30, (0, 0), clock=395),
    ]
    assert _goals(infer_candidates(rows, [])) == []


def test_score_difference_across_quarter_boundary_never_becomes_goal():
    rows = [
        _obs(0, (2, 2), period=1, clock=3),
        _obs(20, (3, 2), period=2, clock=480),
        _obs(30, (3, 2), period=2, clock=470),
    ]
    candidates = infer_candidates(rows, [])
    assert _goals(candidates) == []
    assert any(c.event_type == "period_change_candidate" for c in candidates)


def test_break_and_final_screens_cannot_generate_goals():
    for flag_name in ("is_break", "is_final"):
        row = _obs(10, (1, 0), clock=0)
        row[flag_name] = True
        rows = [_obs(0, (0, 0), clock=5), row, _obs(20, (1, 0), clock=0)]
        assert _goals(infer_candidates(rows, [])) == []


def test_unconfirmed_ocr_spike_is_review_window_not_goal_and_does_not_poison_score():
    rows = [
        _obs(0, (0, 0), clock=420),
        _obs(10, (1, 0), clock=410),  # one-frame spike
        _obs(20, (0, 0), clock=400),
        _obs(30, (1, 0), clock=390),  # real state
        _obs(40, (1, 0), clock=380),
    ]
    candidates = infer_candidates(rows, [])
    goals = _goals(candidates)
    assert len(goals) == 1
    assert goals[0].second == 30.0
    assert any(c.event_type == "score_change_window_home" and c.second == 10.0 for c in candidates)


def test_scoreboard_parser_tags_replay_break_and_final():
    assert parse_scoreboard_text("REPLAY Q2 4:22 3 2")["is_replay"] is True
    assert parse_scoreboard_text("HALF TIME Q2 0:00 3 2")["is_break"] is True
    assert parse_scoreboard_text("FINAL Q4 0:00 9 7")["is_final"] is True


def test_summary_reports_ignored_non_live_states():
    rows = [
        _obs(0, (0, 0), text="REPLAY", replay=True),
        _obs(10, (0, 0), text="BREAK", break_flag=True),
        _obs(20, (0, 0), text="FINAL", final=True),
    ]
    summary = build_auto_summary(rows, [], [])
    assert summary["replay_observations_ignored_for_goals"] == 1
    assert summary["break_observations_ignored_for_goals"] == 1
    assert summary["final_observations_ignored_for_goals"] == 1
