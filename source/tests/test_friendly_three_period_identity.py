from types import SimpleNamespace

from services.autonomous_engine import infer_periods
from services.player_identity import cap_identity_key, event_identity_key


def _obs(second, period):
    return {
        "second": float(second),
        "period": period,
        "home_score": 0,
        "away_score": 0,
        "ocr_confidence": 0.9,
    }


def test_three_period_friendly_never_invents_a_fourth_period():
    observations = [
        _obs(20, 1), _obs(420, 1),
        _obs(520, 2), _obs(930, 2),
        _obs(1040, 3), _obs(1450, 3),
    ]
    periods = infer_periods(observations, duration=1500)
    assert [row["period"] for row in periods] == [1, 2, 3]
    assert len(periods) == 3
    assert all(row["period"] != 4 for row in periods)


def test_same_cap_number_on_opposite_teams_is_never_same_identity():
    assert cap_identity_key(12, "for", 7) == "m12:for:cap:7"
    assert cap_identity_key(12, "against", 7) == "m12:against:cap:7"
    assert cap_identity_key(12, "for", 7) != cap_identity_key(12, "against", 7)


def test_event_identity_uses_perspective_with_explicit_cap_tag():
    own = SimpleNamespace(
        match_id=9,
        player_id=None,
        note="period=2 cap=4 zone=point",
        context_meta=SimpleNamespace(perspective="for"),
    )
    opponent = SimpleNamespace(
        match_id=9,
        player_id=None,
        note="period=2 cap=4 zone=point",
        context_meta=SimpleNamespace(perspective="against"),
    )
    assert event_identity_key(own) == "m9:for:cap:4"
    assert event_identity_key(opponent) == "m9:against:cap:4"
    assert event_identity_key(own) != event_identity_key(opponent)
