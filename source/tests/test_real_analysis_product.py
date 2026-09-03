from pathlib import Path


def _routes(app, path, method):
    return [
        route for route in app.routes
        if getattr(route, "path", None) == path
        and method in (getattr(route, "methods", set()) or set())
    ]


def test_real_analysis_routes_precede_legacy_placeholder():
    from main import app

    start_routes = _routes(app, "/matches/{match_id}/analysis/start", "POST")
    assert start_routes
    assert start_routes[0].endpoint.__module__ == "analysis_product_routes"

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/matches/{match_id}/analysis/result" in paths
    assert "/matches/{match_id}/analysis/evidence-pack" in paths
    assert "/matches/{match_id}/analysis/export.zip" in paths


def test_real_url_create_and_start_precede_framework_only_routes():
    from main import app

    create_routes = _routes(app, "/analysis/url/create", "POST")
    start_routes = _routes(app, "/matches/{match_id}/url-analysis/start", "POST")
    assert create_routes and create_routes[0].endpoint.__module__ == "analysis_product_routes"
    assert start_routes and start_routes[0].endpoint.__module__ == "analysis_product_routes"


def test_ultimate_library_precedes_legacy_library():
    from main import app

    library_routes = _routes(app, "/analysis-library", "GET")
    detail_routes = _routes(app, "/analysis-library/{item_id}", "GET")
    assert library_routes and library_routes[0].endpoint.__module__ == "analysis_library_product_routes"
    assert detail_routes and detail_routes[0].endpoint.__module__ == "analysis_library_product_routes"


def test_youtube_evidence_is_bounded_to_exact_window():
    from services.analysis_product import youtube_segment_embed

    value = youtube_segment_embed("https://www.youtube.com/watch?v=abcdefghijk", 123.4, 131.9)
    assert "/embed/abcdefghijk" in value
    assert "start=123" in value
    assert "end=131" in value


def test_result_template_is_result_first_and_zip_enabled():
    source = Path("source/templates/analysis_result.html").read_text(encoding="utf-8")
    assert "ULTIMATE MATCH ANALYSIS · RÉSULTATS" in source
    assert "Télécharger le dossier ZIP complet" in source
    assert "PREUVES EXACTES" in source
    assert "Aucune image locale" in source
    assert "analysis_exact" in source


def test_library_template_exposes_real_ultimate_results():
    source = Path("source/templates/analysis_library.html").read_text(encoding="utf-8")
    assert "Résultats réellement produits" in source
    assert "Couverture Ultimate" in source
    assert "ZIP complet" in source
    assert "pas faux clips" in source


def test_zip_contract_contains_all_analysis_folders():
    source = Path("source/services/analysis_product.py").read_text(encoding="utf-8")
    for folder in (
        "01_report/report.html",
        "01_report/analysis.json",
        "02_kpis/team_kpis.csv",
        "03_events/events.csv",
        "04_sequences/auto_candidates.csv",
        "04_sequences/tactical_sequences.json",
        "05_evidence/evidence_index.csv",
        "05_evidence/external_segments.csv",
        "06_sources/evidence_contract.json",
        "06_sources/public_reference.json",
    ):
        assert folder in source
    assert "Les vidéos tierces ne sont pas copiées" in source
