"""Install result-first analysis routes directly on the FastAPI application.

FastAPI resolves the first matching route. AquaMetric still contains historical
routes in main.py for compatibility, and nested APIRouter inclusion is not a
strong enough ordering guarantee with recent FastAPI versions. This module puts
all analysis-product entry points at the application boundary before main.py
registers its legacy routes.
"""
from __future__ import annotations

from fastapi.responses import HTMLResponse

from analysis_library_product_routes import published_ultimate_detail, ultimate_analysis_library
from analysis_product_routes import (
    analysis_result,
    create_real_url_analysis,
    export_complete_analysis,
    regenerate_exact_evidence,
    start_real_analysis,
    start_real_url_analysis,
)


def install_priority_analysis_routes(app) -> None:
    registrations = [
        ("/analysis/url/create", create_real_url_analysis, "POST", None, "product_create_url_analysis"),
        ("/matches/{match_id}/analysis/start", start_real_analysis, "POST", None, "product_start_analysis"),
        ("/matches/{match_id}/url-analysis/start", start_real_url_analysis, "POST", None, "product_start_url_analysis"),
        ("/matches/{match_id}/analysis/result", analysis_result, "GET", HTMLResponse, "product_analysis_result"),
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
