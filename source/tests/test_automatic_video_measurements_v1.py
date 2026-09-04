from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_performance_api_exposes_automatic_analysis_and_measurement_matrix():
    route = (ROOT / "performance_routes.py").read_text(encoding="utf-8")
    for needle in [
        '"automatic_analysis": automatic',
        '"measurement_matrix": measurement_matrix',
        '"Structure vidéo"',
        '"Scoreboard / OCR"',
        '"Variations de score"',
        '"Sifflets"',
        '"Tirs / buts / cadrage"',
        '"Passes"',
        '"Attribution joueuse"',
        '"Possessions exactes"',
        '"Transitions D→A / A→D"',
        '"Sprint / vitesse / release"',
        '"NON MESURÉ"',
    ]:
        assert needle in route


def test_ultimate_result_loads_automatic_video_measurement_surface():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "automatic-video-measurements.js").read_text(encoding="utf-8")
    assert "/static/automatic-video-measurements.js?v=2026.09.04.1" in base
    assert "Matrice de mesure — ce qui est réellement disponible" in js
    assert "Mesures automatiques réellement extraites de la vidéo" in js
    assert "OCR, périodes, score et audio — sorties automatiques" in js
    assert "AUTO, CANDIDAT AUTO, TAGUÉ, CALIBRÉ ou NON MESURÉ" in js


def test_automatic_surface_keeps_candidates_separate_from_player_facts():
    js = (ROOT / "static" / "automatic-video-measurements.js").read_text(encoding="utf-8")
    route = (ROOT / "performance_routes.py").read_text(encoding="utf-8")
    assert "non promus en stats joueuse sans validation" in js
    assert "They are not silently promoted to player-level pass/shot facts" in route
