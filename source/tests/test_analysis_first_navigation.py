"""Regression contract for the analysis-first primary navigation."""
from pathlib import Path
from types import SimpleNamespace
import re
from jinja2 import Environment, FileSystemLoader

SOURCE = Path(__file__).resolve().parents[1]
TEMPLATES = SOURCE / "templates"
EXPECTED = ["/dashboard", "/matches/new", "/matches", "/knowledge",
            "/analysis-history", "/analysis-library"]
ENV = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)

def render_nav(path):
    html = ENV.get_template("base.html").render(
        request=SimpleNamespace(url=SimpleNamespace(path=path)),
        user=SimpleNamespace(name="Test", email="test@example.invalid"),
        app_name="AquaMetric", web_demo_mode=False,
    )
    return re.search(r'<nav class="side-nav"[^>]*>.*?</nav>', html, re.S).group()

def test_primary_destinations_and_active_state():
    cases = {
        "/dashboard": "/dashboard",
        "/matches/new": "/matches/new",
        "/matches/42": "/matches",
        "/matches/42/tactics": "/knowledge",
        "/matches/42/report": "/analysis-history",
        "/matches/42/analysis/result": "/analysis-history",
        "/analysis-history": "/analysis-history",
        "/analysis-library/42": "/analysis-library",
    }
    for path, target in cases.items():
        nav = render_nav(path)
        assert re.findall(r'href="([^"]+)"', nav) == EXPECTED
        assert re.findall(r'<a href="([^"]+)" class="active" aria-current="page"', nav) == [target]

def test_dashboard_only_analysis_shortcuts():
    html = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    for route in ("/competitions", "/scouting", "/simulation", "/transfer-watch", "/benchmarks"):
        assert f'href="{route}"' not in html
    assert 'href="/matches/new"' in html
    assert 'href="/my-team"' in html

def test_match_links_and_translations():
    html = (TEMPLATES / "matches.html").read_text(encoding="utf-8")
    for suffix in ("/analysis/result", "/tactics", "/report"):
        assert "/matches/{{m.id}}" + suffix in html
    keys = re.findall(r'data-i18n="([^"]+)"', render_nav("/dashboard"))
    dictionary = (SOURCE / "static" / "i18n.js").read_text(encoding="utf-8")
    assert len(keys) == 6
    assert all(dictionary.count(f"'{key}':") == 5 for key in keys)
