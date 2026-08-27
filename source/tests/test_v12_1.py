from pathlib import Path
import re

from services.advanced_metrics import _target_preference, _side_preference
from services.simulation import simulate_matchup

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_mobile_menu_closes_outside_without_navigation_logic():
    base = read("templates/base.html")
    js = read("static/app.js")
    css = read("static/v12.css")
    assert "data-menu-backdrop" in base
    assert "document.addEventListener('pointerdown'" in js
    assert "setMenu(false)" in js
    assert "history." not in js
    assert "location.href" not in js
    assert ".sidebar-backdrop.open" in css


def test_five_interface_languages_are_available():
    base = read("templates/base.html")
    i18n = read("static/i18n.js")
    for code in ("en", "fr", "it", "es", "ru"):
        assert f'value="{code}"' in base
        assert f" {code}:{{" in i18n or f"\n {code}:{{" in i18n
    assert "localStorage.setItem('aquametric.language'" in i18n


def test_no_user_visible_refresh_buttons_remain_in_templates():
    offenders = []
    for path in (ROOT / "templates").glob("*.html"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"<button\b[^>]*>[^<]*refresh[^<]*</button>", text, flags=re.I):
            offenders.append(path.name)
    assert offenders == []


def test_knowledge_page_is_synthesis_not_source_directory():
    text = read("templates/knowledge.html")
    assert "tactic.press.title" in text
    assert "tactic.42.title" in text
    assert "tactic.pk.title" in text
    assert "research_references" not in text
    assert "references|length" not in text
    assert "reference-row" not in text


def test_transfer_watch_is_grouped_by_year_and_market_window_and_links_profiles():
    text = read("templates/transfer_watch.html")
    assert "years.items" in text
    assert "['summer','winter']" in text
    assert "window == 'summer'" in text
    assert "window == 'winter'" in text
    assert "published_date[:4]" in text
    assert "/profiles/players/" in text
    assert "transfer-kind" in text


def test_player_lists_link_to_profiles_or_safe_name_resolver():
    checks = {
        "templates/my_team.html": "/intelligence/player?name=",
        "templates/scouting_detail.html": "/intelligence/player?name=",
        "templates/player_data.html": "/intelligence/player?name=",
        "templates/analysis_library_detail.html": "/intelligence/player?name=",
        "templates/player_intelligence.html": "/profiles/players/",
        "templates/france_intelligence.html": "/profiles/players/",
        "templates/team_detail.html": "/players/",
    }
    for rel, needle in checks.items():
        assert needle in read(rel), rel


def test_shot_preferences_require_a_minimum_sample():
    assert _target_preference([[1, 0, 0], [0, 1, 0], [0, 0, 0]])["available"] is False
    result = _target_preference([[0, 0, 3], [0, 1, 0], [0, 0, 0]])
    assert result["available"] is True
    assert result["label"] == "upper right"
    assert result["share"] == 75
    assert _side_preference({"left": 1, "right": 1})["available"] is False
    side = _side_preference({"left": 3, "right": 1, "unknown": 9})
    assert side["available"] is True
    assert side["label"] == "left"
    assert side["share"] == 75


def test_match_simulation_is_still_wired_and_level_dominant():
    result = simulate_matchup(
        "Granville Water Polo", "France — Women Senior",
        n=1200, seed=41, venue="neutral"
    )
    assert result["team_a"] == "Granville Water Polo"
    assert result["team_b"] == "France — Women Senior"
    assert result["win_b"] > result["win_a"]
    assert result["avg_b"] > result["avg_a"]
    assert "factor_rows" in result and result["factor_rows"]
    assert result["coverage"] <= 100


def test_shot_preference_ui_is_present_on_player_dossier():
    text = read("templates/player_intelligence_detail.html")
    assert "shot_map.preferences.target" in text
    assert "shot_map.preferences.side" in text
    assert "minimum 3" in text
    assert "shot.demo" in text
