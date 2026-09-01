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
    assert '/static/app.js?v=2026.09.01.2' in base


def test_knowledge_embeds_video_excerpts_in_the_hub():
    knowledge = read("templates/knowledge.html")
    assert 'id="video"' in knowledge
    assert "youtube-nocookie.com/embed/HfkCCOpLIBA?start=" in knowledge
    assert "youtube-nocookie.com/embed/Ek1kBvUjivc?start=" in knowledge
    assert "youtube-nocookie.com/embed/TseN9CGbfQw?start=" in knowledge
    assert "youtube-nocookie.com/embed/bF-Am10VtF4?start=" in knowledge
    assert "Les extraits sont dans le site" in knowledge


def test_reference_wings_are_high_near_two_to_three_metres():
    knowledge = read("templates/knowledge.html")
    assert 'data-wing-reference="O1-O5-2to3m"' in knowledge
    assert '(42,76,"O1")' in knowledge
    assert '(258,76,"O5")' in knowledge
    assert '(96,128,"O2")' in knowledge
    assert '(204,128,"O4")' in knowledge
    assert "O1/O5 restent hautes sur les ailes" in knowledge


def test_legacy_tactical_and_video_pages_converge_to_hub():
    app = read("static/app.js")
    film_room = read("static/video-session-elite.html")
    assert "location.pathname==='/tactical-chess'" in app
    assert "location.replace('/knowledge')" in app
    assert "elite-video-quick-access" not in app
    assert "location.replace('/knowledge#video')" in film_room
