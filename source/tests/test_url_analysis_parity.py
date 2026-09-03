from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


def test_url_analysis_routes_are_nested_in_installed_performance_router():
    from tactical_media_routes import router
    paths = {route.path for route in router.routes}
    assert "/analysis/url/create" in paths
    assert "/matches/{match_id}/url-analysis/start" in paths
    assert "/matches/{match_id}/url-analysis/events" in paths
    assert "/matches/{match_id}/url-analysis" in paths


def test_new_analysis_page_exposes_direct_url_analysis_action():
    html = (ROOT / "templates" / "match_new.html").read_text(encoding="utf-8")
    assert 'formaction="/analysis/url/create"' in html
    assert "Analyser directement depuis l'URL" in html
    assert "même minimum Ultimate Analyst" in html


def test_existing_remote_match_gets_ultimate_url_entry():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "addUrlAnalysisEntry" in js
    assert "/url-analysis/start" in js
    assert "Analyser l’URL · Ultimate Analyst" in js


def test_url_result_contains_minimum_ultimate_contract():
    html = (ROOT / "templates" / "url_analysis.html").read_text(encoding="utf-8")
    for needle in [
        "MINIMUM GARANTI", "Tir, passe, possession", "PERTES DE POSSESSION",
        "TRANSITION", "QUALITATIF COACH", "JOUEUSE PAR JOUEUSE",
        "Data Coverage", "Readiness",
    ]:
        assert needle in html
    assert "youtube" not in html.lower() or "embed" in html.lower()
    assert "AquaMetric ne copie pas la vidéo tierce" in html


def test_url_template_compiles():
    env = Environment(loader=FileSystemLoader(ROOT / "templates"))
    env.get_template("url_analysis.html")


def test_url_route_uses_same_ultimate_engine_as_uploaded_analysis():
    src = (ROOT / "url_analysis_routes.py").read_text(encoding="utf-8")
    assert "ultimate_match_report(match)" in src
    assert "team_performance_report(match)" in src
    assert "ultimate_event_report(events" in src
    assert "framework_ready" in src
    assert "Third-party pixels are not copied" in src
    assert "manual_url_review" in src
