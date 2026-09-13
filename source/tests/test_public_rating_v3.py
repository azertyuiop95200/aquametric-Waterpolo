import json
from types import SimpleNamespace

from services.public_match_ratings import evaluate_public_match


def metric(name, value, team="Lille UC Métropole Water-Polo"):
    row = SimpleNamespace(metric=name, value=value, team_name=team)
    row._team_name = team
    return row


def match(meta=None):
    return SimpleNamespace(
        team_a="Lille UC Métropole Water-Polo", team_b="Grand Nancy Aquatique Club",
        score_a=17, score_b=10,
        team_stats_json=json.dumps({"_aquametric": meta or {
            "source_tier": "federation_official", "competition_level": 4,
            "scorer_list_complete": True,
        }}),
    )


def test_goals_only_public_rating_stays_partial_and_shrunk():
    row = evaluate_public_match(match(), [metric("appearance", 1), metric("goals", 7)], role="Field player")
    assert row["engine_version"] == "public-rating-v3"
    assert row["evidence_families"] == 1
    assert row["coverage"] <= .25
    assert row["overall"] < row["raw_overall"]
    assert row["overall"] < 75
    assert "single-stat" in row["scope"]


def test_multi_stat_public_rating_has_more_coverage_and_reliability():
    goals_only = evaluate_public_match(match(), [metric("appearance", 1), metric("goals", 3)], role="Field player")
    fuller = evaluate_public_match(match(), [
        metric("appearance", 1), metric("goals", 3), metric("shots", 6),
        metric("assists", 2), metric("steals", 2), metric("exclusions", 1),
    ], role="Field player")
    assert fuller["evidence_families"] > goals_only["evidence_families"]
    assert fuller["coverage"] > goals_only["coverage"]
    assert fuller["reliability"] > goals_only["reliability"]
    assert fuller["confidence_score"] > goals_only["confidence_score"]
