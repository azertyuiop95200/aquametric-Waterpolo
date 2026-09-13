from types import SimpleNamespace

from services.ratings import build_detailed_evaluation
from db import normalize_database_url


def event(kind, phase="auto"):
    return SimpleNamespace(event_type=kind, context_meta=SimpleNamespace(phase_tag=phase))


def test_rating_v2_withholds_score_without_player_evidence():
    d = build_detailed_evaluation([], role="Field player")
    assert d["rated"] is False
    assert d["overall"] is None
    assert d["physical"] is None
    assert d["confidence_label"] == "INSUFFICIENT DATA"


def test_rating_v2_is_multidimensional_and_evidence_bound():
    d = build_detailed_evaluation([
        event("goal", "power_play"), event("assist", "power_play"),
        event("interception", "even_defence"), event("fast_recovery", "defensive_recovery"),
        event("pass_complete", "even_attack"), event("block", "penalty_kill"),
    ], role="Field player")
    assert d["rated"] is True
    assert 0 <= d["overall"] <= 100
    assert set(d["dimensions"]) == {"attack", "defence", "decision", "tactics", "transition", "discipline", "technique", "impact"}
    assert d["physical"] is None
    assert d["dimensions"]["attack"] > 50
    assert d["dimensions"]["defence"] > 50


def test_postgres_urls_are_normalized_for_psycopg3():
    assert normalize_database_url("postgres://u:p@host/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("postgresql://u:p@host/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("sqlite:///x.db") == "sqlite:///x.db"


def test_v12_routes_and_security_headers_are_installed():
    from main import app
    from fastapi.testclient import TestClient
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/matches/{match_id}/intelligence" in paths
    assert "/profiles/players/{profile_id}" in paths
    assert "/coach-intelligence/{coach_id}" in paths
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "default-src 'self'" in r.headers.get("content-security-policy", "")
