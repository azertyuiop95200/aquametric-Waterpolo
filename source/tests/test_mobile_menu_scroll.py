from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_sidebar_keeps_vertical_touch_scrolling_enabled():
    css = (ROOT / "static" / "v121-hotfix.css").read_text(encoding="utf-8")
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")

    assert ".sidebar .side-nav" in css
    assert "overflow-y:auto!important" in css
    assert "touch-action:pan-y!important" in css
    assert ".menu-open{overflow:hidden!important;touch-action:none!important}" not in css
    assert "v121-hotfix.css?v=12.2.0" in base
    assert "app.js?v=12.2.0" in base
