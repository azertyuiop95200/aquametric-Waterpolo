from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def test_result_template_is_result_first_playable_and_zip_enabled():
    source = (ROOT / "templates" / "analysis_result.html").read_text(encoding="utf-8")
    assert "ULTIMATE MATCH ANALYSIS · RÉSULTATS" in source
    assert "Télécharger le dossier ZIP complet" in source
    assert "SÉQUENCES ANALYSÉES · MAXIMUM" in source
    assert "Générer un maximum de séquences" in source
    assert "PREUVES EXACTES" in source
    assert "Aucune image locale" in source
    assert "analysis_exact" in source
    assert "s.clip_url" in source
    assert "s.segment_embed" in source
    assert "s.screenshot_urls" in source
    assert '_analysis_research_context.html' in source


def test_scoring_patterns_are_visible_and_evidence_first():
    partial = (ROOT / "templates" / "_analysis_scoring_patterns.html").read_text(encoding="utf-8")
    service = (ROOT / "services" / "team_scoring_patterns.py").read_text(encoding="utf-8")
    research_partial = (ROOT / "templates" / "_analysis_research_context.html").read_text(encoding="utf-8")
    assert "COMMENT LES ÉQUIPES MARQUENT · TENDANCES & HABITUDES" in partial
    assert "habitudes observées" in partial
    assert "SÉQUENCES DE BUT VÉRIFIÉES" in partial
    assert "score seul n'est converti en cause tactique" in service
    assert "repeated_routes" in service
    assert "positive_habits" in service
    assert "negative_habits" in service
    assert '_analysis_scoring_patterns.html' in research_partial


def test_library_template_exposes_real_results_and_embedded_replays():
    source = (ROOT / "templates" / "analysis_library.html").read_text(encoding="utf-8")
    assert "Résultats réellement produits" in source
    assert "Couverture Ultimate" in source
    assert "ZIP complet" in source
    assert "Replays directement lisibles" in source
    for video_id in ("pIJu8tQT7-I", "bF-Am10VtF4", "TnZjH0VeCsQ"):
        assert video_id in source


def test_zip_contract_contains_all_analysis_folders_and_deep_manifest():
    source = (ROOT / "services" / "analysis_product.py").read_text(encoding="utf-8")
    for folder in (
        "01_report/report.html",
        "01_report/analysis.json",
        "02_kpis/{side}_kpis.csv",
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

    deep = (ROOT / "services" / "deep_analysis_sequences.py").read_text(encoding="utf-8")
    assert "sequence_manifest.csv" in deep
    assert "sequence_manifest.json" in deep
    assert "max_total: int = 72" in deep
    assert '"vision_peak"' in deep
    assert '"active_window"' in deep

    research = (ROOT / "services" / "analysis_research_context.py").read_text(encoding="utf-8")
    assert "research_context.json" in research
    assert "official_reference_catalog.json" in research
    assert "team_roster.csv" in research
    assert "related_fixtures.csv" in research

    scoring = (ROOT / "services" / "team_scoring_patterns.py").read_text(encoding="utf-8")
    assert "scoring_patterns.json" in scoring
    assert "scoring_sequences.csv" in scoring
    assert "team_habits.csv" in scoring


def test_export_route_materializes_every_catalogued_local_clip_before_zip():
    source = (ROOT / "analysis_product_routes.py").read_text(encoding="utf-8")
    assert "max_targets=72, max_clips=72" in source
    assert "max_image_targets=72" in source
    assert "append_sequence_manifest" in source
    assert "append_research_to_zip" in source
    assert "append_scoring_patterns_to_zip" in source


def test_complete_runner_doubles_visual_density_and_maxes_ocr():
    source = (ROOT / "services" / "complete_analysis_runner.py").read_text(encoding="utf-8")
    assert "visual_samples=360" in source
    assert "ocr_samples=96" in source
    assert "max_candidates=28" in source


def test_scoreboard_candidates_are_focused_inside_score_change_window():
    source = (ROOT / "services" / "autonomous_engine.py").read_text(encoding="utf-8")
    assert "_best_visual_focus" in source
    assert "bracket_start_second" in source
    assert "visual_focus_second" in source
    assert "score_change_window" in source
