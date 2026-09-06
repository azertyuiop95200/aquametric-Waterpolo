from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_security_explicitly_allows_first_party_display_capture():
    security = (ROOT / "security.py").read_text(encoding="utf-8")
    assert "display-capture=(self)" in security
    assert "camera=()" in security
    assert "microphone=()" in security
    assert "https://www.youtube.com" in security


def test_browser_capture_permission_flow_is_user_visible_and_actionable():
    template = (ROOT / "templates" / "browser_capture_v4.html").read_text(encoding="utf-8")
    assert "Démarrer l’analyse" in template
    assert "navigator.mediaDevices.getDisplayMedia" in template
    assert "window.isSecureContext" in template
    assert "NotAllowedError" in template
    assert "displaySurface:'browser'" in template
    assert "source_start_second" in template
    assert "recorder.start(5000)" in template
    assert "preferCurrentTab:!externalFallback" in template
    assert "selfBrowserSurface:'include'" in template
    assert "Lecture vidéo" in template
    assert "Analyse IA" in template
    assert "Turbo ≤15 min" in template
    assert "https://www.youtube.com/iframe_api" in template
    assert "durée non détectée" in template


def test_manual_reference_roster_is_disabled_for_analysis_identity():
    roster = (ROOT / "services" / "reference_match_rosters.py").read_text(encoding="utf-8")
    assert "_REFERENCE_ROSTERS: dict[str, tuple[MatchRosterCandidate, ...]] = {}" in roster
    assert "return ()" in roster
    assert "return []" in roster
    assert "Maëlle" not in roster
    assert "Clara" not in roster
    assert "Hitomi" not in roster
    assert "Hanae" not in roster
