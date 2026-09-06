"""Install result-first analysis routes directly on the FastAPI application."""
from __future__ import annotations

from fastapi.responses import HTMLResponse

from analysis_library_product_routes import published_ultimate_detail, ultimate_analysis_library
from analysis_input_routes_v2 import create_flexible_uploaded_match
from analysis_input_routes_v3 import create_flexible_url_analysis
from analysis_product_routes import (
    export_complete_analysis,
    regenerate_exact_evidence,
    start_real_analysis,
    start_real_url_analysis,
)
from analysis_result_clean_v2 import clean_analysis_result
from capture_turbo_routes_v9 import (
    turbo_append_chunk,
    turbo_browser_capture_page,
    turbo_capture_status,
    turbo_create_session,
    turbo_finish_capture,
    turbo_progress_frame,
)


def install_priority_analysis_routes(app) -> None:
    registrations = [
        ("/analysis/url/create", create_flexible_url_analysis, "POST", None, "product_create_url_analysis"),
        ("/matches", create_flexible_uploaded_match, "POST", None, "product_create_uploaded_match"),
        ("/matches/{match_id}/analysis/start", start_real_analysis, "POST", None, "product_start_analysis"),
        ("/matches/{match_id}/url-analysis/start", start_real_url_analysis, "POST", None, "product_start_url_analysis"),
        ("/matches/{match_id}/analysis/browser-capture", turbo_browser_capture_page, "GET", HTMLResponse, "turbo_browser_capture_page"),
        ("/matches/{match_id}/analysis/browser-capture/session", turbo_create_session, "POST", None, "turbo_capture_session"),
        ("/matches/{match_id}/analysis/browser-capture/chunk", turbo_append_chunk, "POST", None, "turbo_capture_chunk"),
        ("/matches/{match_id}/analysis/browser-capture/frame", turbo_progress_frame, "POST", None, "turbo_capture_frame"),
        ("/matches/{match_id}/analysis/browser-capture/status", turbo_capture_status, "GET", None, "turbo_capture_status"),
        ("/matches/{match_id}/analysis/browser-capture/finish", turbo_finish_capture, "POST", None, "turbo_capture_finish"),
        ("/matches/{match_id}/analysis/result", clean_analysis_result, "GET", HTMLResponse, "product_analysis_result"),
        ("/matches/{match_id}/analysis/evidence-pack", regenerate_exact_evidence, "POST", None, "product_evidence_pack"),
        ("/matches/{match_id}/analysis/export.zip", export_complete_analysis, "GET", None, "product_analysis_export"),
        ("/analysis-library", ultimate_analysis_library, "GET", HTMLResponse, "product_analysis_library"),
        ("/analysis-library/{item_id}", published_ultimate_detail, "GET", HTMLResponse, "product_analysis_library_detail"),
    ]
    for path, endpoint, method, response_class, name in registrations:
        kwargs = {"methods": [method], "name": name}
        if response_class is not None:
            kwargs["response_class"] = response_class
        app.add_api_route(path, endpoint, **kwargs)
