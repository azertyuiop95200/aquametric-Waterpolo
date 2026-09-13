from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_video_session_uses_real_match_analysis_data():
    route = read("video_session_routes.py")
    for marker in [
        "sequence_gallery", "sequence_summary", "player_deep_metrics", "team_player_totals",
        "build_team_scoring_patterns", "max_total=72", "match_id", "screenshot_count",
    ]:
        assert marker in route


def test_video_session_replaces_placeholder_with_evidence_room():
    html = read("templates/video_session_elite.html")
    for marker in [
        "SÉANCE VIDÉO V12.2", "Jusqu’à 72", "Temps de jeu", "Ballons touchés",
        "Passes", "Duels", "Distance", "Aucune séquence vérifiée",
        "MUR DE PREUVES", "FILM ROOM INTERNATIONALE", "CONTRAT DE PREUVE",
    ]:
        assert marker in html
    assert "VIDÉO / CAPTURE" not in html


def test_analysis_library_exposes_deep_workspace_metrics_and_video_session():
    html = read("templates/premium_analysis_library.html")
    for marker in [
        "recalculée V12.2", "Ballons touchés", "Temps de jeu", "Duels",
        "Distance", "Séance vidéo", "/analysis/video-session-elite?match_id=",
        "Les anciens dossiers sont remis à jour",
    ]:
        assert marker in html
    route = read("premium_product_routes.py")
    for marker in ["player_deep_metrics", "team_player_totals", "player_totals", "attribution", "screenshots"]:
        assert marker in route


def test_video_session_is_first_class_v122_route_and_navigation_item():
    security = read("security.py")
    assert "video_session_router" in security
    assert "app.include_router(video_session_router)" in security
    base = read("templates/base.html")
    assert "/analysis/video-session-elite" in base
    assert "Séances vidéo" in base


def test_evidence_and_physical_truth_contract_stays_visible():
    html = read("templates/video_session_elite.html")
    assert "Temps de jeu et distance ne sont affichés que" in html
    assert "AquaMetric n’invente ni action, ni timestamp, ni image" in html
    service = read("services/player_deep_metrics.py")
    assert "distance_calibrated_m" in service
    assert "playing_time_s" in service
    assert "Valeurs physiques affichées uniquement" in service
