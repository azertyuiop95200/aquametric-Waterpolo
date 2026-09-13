from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_primary_navigation_has_one_tactics_hub_only():
    base = read("templates/base.html")
    assert "Tactique & Connaissance" in base
    assert 'href="/tactical-chess"' not in base
    assert "Analyse vidéo élite" not in base
    assert "video-session-elite.html" not in base
    # The cache-busting version is expected to evolve with releases; the
    # regression contract is that the current application bundle is loaded.
    assert '/static/app.js?v=' in base


def test_video_coach_room_is_embedded_in_the_hub():
    knowledge = read("templates/knowledge.html")
    assert 'id="coach"' in knowledge
    for video_id in ("HfkCCOpLIBA", "Ek1kBvUjivc", "TseN9CGbfQw", "bF-Am10VtF4"):
        assert f"youtube-nocookie.com/embed/{video_id}" in knowledge
    assert "Séance vidéo coach" in knowledge
    assert "Stop avant décision" in knowledge
    assert "reconstructions pédagogiques" in knowledge


def test_reference_wings_are_high_near_two_to_three_metres():
    knowledge = read("templates/knowledge.html")
    assert 'data-wing-reference="O1-O5-2to3m"' in knowledge
    assert '(42,76,"O1")' in knowledge
    assert '(258,76,"O5")' in knowledge
    assert '(96,128,"O2")' in knowledge
    assert '(204,128,"O4")' in knowledge
    assert "O1/O5 hautes" in knowledge


def test_legacy_tactical_route_converges_without_separate_navigation():
    app = read("static/app.js")
    film_room = read("static/video-session-elite.html")
    assert "location.pathname==='/tactical-chess'" in app
    assert "location.replace('/knowledge')" in app
    assert "elite-video-quick-access" not in app
    assert "Tactique & Connaissance" in film_room
    assert 'href="/knowledge#coach"' in film_room
