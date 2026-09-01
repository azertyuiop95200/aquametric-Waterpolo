from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_elite_video_is_directly_available_in_primary_navigation():
    base = read("templates/base.html")
    assert 'href="/static/video-session-elite.html?v=20260901-1"' in base
    assert 'Analyse vidéo élite' in base
    assert '/static/app.js?v=2026.09.01.1' in base


def test_floating_elite_video_shortcut_uses_versioned_film_room_url():
    app = read("static/app.js")
    assert "video-session-elite.html?v=20260901-1" in app
    assert "Analyse vidéo élite" in app
