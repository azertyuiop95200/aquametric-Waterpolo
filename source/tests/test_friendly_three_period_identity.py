from types import SimpleNamespace

from services.autonomous_engine import infer_periods
from services.player_identity import cap_identity_key, event_identity_key
from services.reference_match_rosters import cap_candidates, roster_payload


REFERENCE_URL = "https://www.youtube.com/watch?v=Guo_UU282pI&t=465s"


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
    own = cap_identity_key(12, "for", 7)
    opponent = cap_identity_key(12, "against", 7)
    assert own == "m12:for:cap:7:track:ambiguous"
    assert opponent == "m12:against:cap:7:track:ambiguous"
    assert own != opponent


def test_same_cap_number_inside_same_team_needs_visual_track_to_split_identity():
    unresolved = cap_identity_key(12, "for", 12)
    hitomi_track = cap_identity_key(12, "for", 12, "white12-a")
    hanae_track = cap_identity_key(12, "for", 12, "white12-b")
    assert unresolved.endswith("cap:12:track:ambiguous")
    assert hitomi_track != hanae_track
    assert hitomi_track != unresolved
    assert hanae_track != unresolved


def test_event_identity_uses_perspective_and_optional_visual_track():
    own = SimpleNamespace(
        match_id=9,
        player_id=None,
        note="period=2 cap=4 track=white4-a zone=point",
        context_meta=SimpleNamespace(perspective="for"),
    )
    opponent = SimpleNamespace(
        match_id=9,
        player_id=None,
        note="period=2 cap=4 track=dark4-a zone=point",
        context_meta=SimpleNamespace(perspective="against"),
    )
    assert event_identity_key(own) == "m9:for:cap:4:track:white4-a"
    assert event_identity_key(opponent) == "m9:against:cap:4:track:dark4-a"
    assert event_identity_key(own) != event_identity_key(opponent)


def test_reference_match_roster_keeps_duplicate_12_and_13_candidates():
    assert cap_candidates(REFERENCE_URL, "for", 1) == ("Rumina",)
    assert cap_candidates(REFERENCE_URL, "for", 12) == ("Hitomi", "Hanae")
    assert cap_candidates(REFERENCE_URL, "for", 13) == ("Maëlle", "Clara")
    rows = roster_payload(REFERENCE_URL)
    assert len(rows) == 16
    assert all(row["ambiguous_cap"] for row in rows if row["cap_number"] in {12, 13})
