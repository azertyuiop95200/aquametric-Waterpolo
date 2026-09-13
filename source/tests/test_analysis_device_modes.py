from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_match_new_exposes_phone_and_desktop_analysis_modes():
    template = (ROOT / "templates" / "match_new.html").read_text(encoding="utf-8")
    assert "Analyse sur ordinateur" in template
    assert "Analyse sur téléphone" in template
    assert 'id="desktopAnalysisMode"' in template
    assert 'id="phoneAnalysisMode"' in template
    assert 'formaction="/analysis/url/create"' in template
    assert 'formaction="/matches"' in template
    assert 'name="video_url"' in template
    assert 'name="video_file"' in template
    assert "mobileLike" in template
    assert "selectMode(mobileLike ? 'phone' : 'desktop')" in template
