from services.game_reading import add_game_reading_score


def test_game_reading_requires_tactical_coverage():
    row = {
        "name": "Sparse Prospect",
        "role": "Field player",
        "dimensions": {"decision": 82, "tactics": None, "transition": None, "impact": None, "discipline": None},
        "dimension_sources": {"decision": ["official report"]},
        "confidence_score": .70,
        "video_analyzed_matches": 0,
        "public_rated_matches": 1,
    }
    result = add_game_reading_score(row)
    assert result["game_reading"]["score"] is None
    assert result["game_reading"]["label"] == "NON ÉVALUÉE"


def test_game_reading_is_separate_high_confidence_grade():
    row = {
        "name": "Tactical Prospect",
        "role": "Field player",
        "dimensions": {
            "decision": 90,
            "tactics": 88,
            "transition": 85,
            "impact": 84,
            "discipline": 80,
        },
        "dimension_sources": {
            "decision": ["tagged/video"],
            "tactics": ["tagged/video", "official play-by-play review"],
            "transition": ["tagged/video"],
            "impact": ["official play-by-play review"],
            "discipline": ["official play-by-play review"],
        },
        "confidence_score": .80,
        "video_analyzed_matches": 2,
        "public_rated_matches": 5,
        "deep_review": {"evidence_count": 3},
    }
    result = add_game_reading_score(row)
    reading = result["game_reading"]
    assert reading["score"] >= 82
    assert reading["label"] in {"TRÈS FORTE", "LECTURE ÉLITE"}
    assert reading["confidence_score"] >= .80
    assert "tagged/video" in reading["sources"]


def test_goalkeeper_game_reading_uses_defensive_reading():
    row = {
        "name": "Keeper Prospect",
        "role": "Goalkeeper",
        "dimensions": {
            "decision": 84,
            "tactics": 83,
            "defence": 91,
            "transition": 78,
            "impact": 87,
        },
        "dimension_sources": {k: ["official play-by-play review"] for k in ("decision", "tactics", "defence", "transition", "impact")},
        "confidence_score": .68,
        "video_analyzed_matches": 0,
        "public_rated_matches": 3,
        "deep_review": {"evidence_count": 2},
    }
    result = add_game_reading_score(row)
    reading = result["game_reading"]
    assert reading["score"] >= 80
    assert reading["components"]["defence"] == 91
    assert "attack" not in reading["components"]
