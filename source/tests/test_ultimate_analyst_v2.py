from pathlib import Path
from types import SimpleNamespace

from services.ultimate_analytics import (
    note_tags,
    ultimate_event_report,
    possession_report,
    coverage_report,
    shot_profile,
    pass_profile,
    loss_context_report,
)

ROOT = Path(__file__).resolve().parents[1]


def ev(second, kind, note="", phase="even_attack", perspective="for", player_id=1):
    return SimpleNamespace(
        second=second,
        event_type=kind,
        note=note,
        player_id=player_id,
        context_meta=SimpleNamespace(phase_tag=phase, perspective=perspective, quality_tag=""),
    )


def test_note_tags_parse_structured_aquametric_context():
    e = ev(2, "shot_on_target", "bonne fixation | [AQ] period=2 zone=flat_left pressure=high decision=good distance_m=6.2 shot_speed_kmh=71.5")
    tags = note_tags(e)
    assert tags["period"] == "2"
    assert tags["zone"] == "flat_left"
    assert tags["pressure"] == "high"
    assert tags["decision"] == "good"
    assert tags["distance_m"] == 6.2
    assert tags["shot_speed_kmh"] == 71.5


def test_possession_report_requires_explicit_ids_for_exact_rates():
    untagged = [ev(1, "pass_complete"), ev(3, "goal")]
    proxy = possession_report(untagged)
    assert proxy["available"] is False
    assert proxy["possessions"] is None
    assert "n'est pas inventé" in proxy["note"]

    tagged = [
        ev(1, "pass_complete", "[AQ] possession=P1 period=1"),
        ev(3, "goal", "[AQ] possession=P1 period=1 zone=flat_left"),
        ev(8, "pass_complete", "[AQ] possession=P2 period=1"),
        ev(10, "turnover", "[AQ] possession=P2 period=1 cause=pressure"),
    ]
    report = possession_report(tagged)
    assert report["available"] is True
    assert report["possessions"] == 2
    assert report["goals_per_possession_pct"] == 50.0
    assert report["turnover_possessions_pct"] == 50.0


def test_shot_profile_splits_zone_and_keeps_calibrated_speed_samples():
    events = [
        ev(1, "goal", "[AQ] zone=wing_left shot_type=catch_shoot hand=right distance_m=5.4 shot_speed_kmh=70"),
        ev(2, "shot_on_target", "[AQ] zone=wing_left shot_type=catch_shoot hand=right distance_m=5.8"),
        ev(3, "shot_off_target", "[AQ] zone=point shot_type=fake_shoot hand=left distance_m=7.0 shot_speed_kmh=74"),
    ]
    profile = shot_profile(events)
    assert profile["total"] == 3
    assert profile["located_pct"] == 100.0
    assert profile["shot_speed_kmh_avg"] == 72.0
    assert profile["calibrated_speed_samples"] == 2
    wing = next(x for x in profile["zones"] if x["key"] == "wing_left")
    assert wing["shots"] == 2
    assert wing["accuracy_pct"] == 100.0


def test_pass_profile_and_loss_context_are_denominator_based():
    events = [
        ev(1, "pass_complete", "[AQ] pass_type=centre_entry pressure=high zone=flat_left"),
        ev(2, "pass_complete", "[AQ] pass_type=centre_entry pressure=high zone=flat_left"),
        ev(3, "bad_pass", "[AQ] pass_type=centre_entry pressure=high zone=flat_left cause=centre_entry"),
        ev(4, "turnover", "[AQ] pressure=high zone=centre cause=pressure"),
    ]
    passes = pass_profile(events)
    centre = next(x for x in passes["types"] if x["key"] == "centre_entry")
    assert centre["attempts"] == 3
    assert centre["completion_pct"] == 66.7
    losses = loss_context_report(events)
    assert losses["total"] == 2
    assert round(sum(x["share"] for x in losses["reasons"]), 1) == 100.0
    assert {x["key"] for x in losses["reasons"]} == {"centre_entry", "pressure"}


def test_coverage_and_ultimate_report_expose_engineering_depth():
    events = [
        ev(1, "pass_complete", "[AQ] period=1 possession=P1 zone=flat_left pressure=medium decision=good pass_type=perimeter"),
        ev(2, "key_pass", "[AQ] period=1 possession=P1 zone=flat_left pressure=high decision=good pass_type=centre_entry"),
        ev(3, "goal", "[AQ] period=1 possession=P1 zone=centre pressure=high decision=good shot_type=centre hand=right"),
        ev(9, "pass_complete", "[AQ] period=1 possession=P2 zone=point pressure=medium decision=neutral pass_type=perimeter"),
        ev(11, "bad_pass", "[AQ] period=1 possession=P2 zone=point pressure=high decision=poor pass_type=skip cause=decision"),
    ]
    cov = coverage_report(events)
    assert cov["score"] >= 80
    report = ultimate_event_report(events)
    assert report["possessions"]["available"] is True
    assert report["periods"]["rows"][0]["period"] == "1"
    assert report["decisions"]["total"] == 5
    assert report["basic"]["pass_completion_pct"] == 75.0


def test_frontend_contains_ultimate_structured_tagger_and_dashboard():
    js = (ROOT / "static" / "elite-analyst.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "elite-analyst.css").read_text(encoding="utf-8")
    assert "ULTIMATE TAGGING" in js
    assert "possession" in js and "shot_speed_kmh" in js and "release_time_s" in js
    assert "Couverture, possessions et contexte" in js
    assert "ea-tagger-grid" in css
    assert "ea-coverage-grid" in css
