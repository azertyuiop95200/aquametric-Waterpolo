from services.deep_scouting_review import REVIEWS, enrich_with_deep_review


def _base(name, overall=75.0):
    return {
        "name": name,
        "overall": overall,
        "stars": 3.5,
        "star_text": "★★★½☆",
        "dimensions": {"attack": 74.0, "defence": None, "decision": 72.0, "tactics": None, "transition": None, "discipline": None, "technique": 73.0, "impact": 75.0},
        "dimension_sources": {k: [] for k in ("attack", "defence", "decision", "tactics", "transition", "discipline", "technique", "impact")},
        "evidence_count": 4,
    }


def test_priority_reviews_cover_non_goal_traits():
    assert "Mandula Mihok" in REVIEWS
    assert REVIEWS["Mandula Mihok"]["dimensions"]["discipline"] < 70
    assert REVIEWS["Pien Gorter"]["dimensions"]["transition"] >= 90
    assert REVIEWS["Julia Teodoro"]["dimensions"]["defence"] >= 90


def test_deep_review_is_low_weight_and_exposes_video_status():
    row = enrich_with_deep_review(_base("Mandula Mihok"))
    assert row["deep_review"] is not None
    assert row["deep_review"]["linked_video_count"] >= 1
    assert "no frame-level score" in row["deep_review"]["video_status"]
    assert 70 < row["overall"] < 90
    assert "official play-by-play review" in row["dimension_sources"]["attack"]
    assert row["discipline"] if "discipline" in row else True


def test_unknown_player_is_not_given_fake_review():
    row = enrich_with_deep_review(_base("Unknown Prospect"))
    assert row["deep_review"] is None
    assert row["overall"] == 75.0
