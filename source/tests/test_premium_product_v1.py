from pathlib import Path
from types import SimpleNamespace

from services.premium_public_analysis import _pair_score, _scorer_report, _history_summary

ROOT = Path(__file__).resolve().parents[1]


def test_quarter_dynamics_and_lead_changes_are_derived_from_scores():
    rows, changes = _pair_score([[2, 4], [5, 2], [1, 3], [4, 1]])
    assert len(rows) == 4
    assert rows[0]["cumulative_a"] == 2
    assert rows[-1]["cumulative_a"] == 12
    assert rows[-1]["cumulative_b"] == 10
    assert changes >= 1


def test_scorer_distribution_reports_share_and_balance_without_invention():
    players = [
        SimpleNamespace(team_name="France", player_name="A", goals=4, shots=7, assists=2, steals=1, exclusions=0, saves=None, source_quality="official", note=""),
        SimpleNamespace(team_name="France", player_name="B", goals=3, shots=5, assists=1, steals=0, exclusions=1, saves=None, source_quality="official", note=""),
        SimpleNamespace(team_name="France", player_name="C", goals=2, shots=None, assists=None, steals=None, exclusions=None, saves=None, source_quality="official", note=""),
        SimpleNamespace(team_name="Other", player_name="X", goals=8, shots=9, assists=0, steals=0, exclusions=0, saves=None, source_quality="official", note=""),
    ]
    report = _scorer_report(players, "France", 10)
    assert report["known_goals"] == 9
    assert report["coverage_pct"] == 90.0
    assert report["rows"][0]["share_pct"] == 40.0
    assert report["rows"][0]["shooting_pct"] == 57.1


def test_history_summary_is_explicit_about_sample_size():
    report = _history_summary([
        {"result": "W", "goals_for": 14, "goals_against": 10},
        {"result": "L", "goals_for": 9, "goals_against": 11},
        {"result": "W", "goals_for": 16, "goals_against": 8},
    ])
    assert report["matches"] == 3
    assert report["wins"] == 2
    assert report["win_pct"] == 66.7
    assert report["avg_for"] == 13.0


def test_premium_library_has_video_film_room_and_deep_match_cards():
    html = (ROOT / "templates" / "premium_analysis_library.html").read_text(encoding="utf-8")
    for needle in ["Une bibliothèque qui produit des décisions", "Film Room internationale", "habitudes", "Dossier complet", "ZIP complet"]:
        assert needle in html
    route = (ROOT / "premium_product_routes.py").read_text(encoding="utf-8")
    for youtube_id in ["a5Ja269h5G8", "VvuJSTuuUI8", "fWFM4kB8nvw", "bF-Am10VtF4", "HfkCCOpLIBA", "Ek1kBvUjivc", "TseN9CGbfQw", "Z-8PwbnKBWU"]:
        assert youtube_id in route


def test_premium_public_detail_is_not_three_line_summary():
    html = (ROOT / "templates" / "premium_analysis_library_detail.html").read_text(encoding="utf-8")
    for needle in ["DYNAMIQUE DU MATCH", "COMMENT LES ÉQUIPES MARQUENT", "TENDANCES & HABITUDES", "HISTORIQUE COMPARABLE", "COACH ROOM", "TRAÇABILITÉ"]:
        assert needle in html


def test_global_product_design_and_match_brief_are_loaded():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "/static/premium-product.css?v=2026.09.04.1" in base
    assert "/static/premium-product.js?v=2026.09.04.4" in base
    js = (ROOT / "static" / "premium-product.js").read_text(encoding="utf-8")
    assert "/api/premium/matches/" in js
    assert "Executive Coach Brief" in js
    security = (ROOT / "security.py").read_text(encoding="utf-8")
    assert "premium_product_router" in security


def test_dashboard_is_now_coach_command_center():
    html = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
    for needle in ["COACH COMMAND CENTER", "Du match brut à la décision coach", "Analyse Ultimate", "Film Room & Tactique", "Simulation manager"]:
        assert needle in html
