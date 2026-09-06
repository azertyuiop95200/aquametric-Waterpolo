from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_security_explicitly_allows_first_party_display_capture():
    security = (ROOT / "security.py").read_text(encoding="utf-8")
    assert "display-capture=(self)" in security
    assert "camera=()" in security
    assert "microphone=()" in security


def test_browser_capture_permission_flow_is_user_visible_and_actionable():
    template = (ROOT / "templates" / "browser_capture.html").read_text(encoding="utf-8")
    assert "Démarrer l’analyse dans cet onglet" in template
    assert "navigator.mediaDevices.getDisplayMedia" in template
    assert "window.isSecureContext" in template
    assert "NotAllowedError" in template
    assert "displaySurface: 'browser'" in template
    assert "source_start_second" in template
    assert "recorder.start(5000)" in template
    assert "preferCurrentTab: true" in template
    assert "selfBrowserSurface: 'include'" in template


def test_reference_match_shared_cap_13_keeps_goalkeeper_identity_signal():
    roster = (ROOT / "services" / "reference_match_rosters.py").read_text(encoding="utf-8")
    assert 'MatchRosterCandidate("for", 13, "Maëlle", role="gardienne", cap_color="rouge")' in roster
    assert 'MatchRosterCandidate("for", 13, "Clara", role="joueuse de champ")' in roster
    assert 'MatchRosterCandidate("for", 12, "Hitomi")' in roster
    assert 'MatchRosterCandidate("for", 12, "Hanae")' in roster
