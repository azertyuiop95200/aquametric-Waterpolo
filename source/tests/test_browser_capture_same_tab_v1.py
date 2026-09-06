from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_browser_capture_prefers_studio_tab_with_external_replay_fallback():
    template = (ROOT / "templates" / "browser_capture_v4.html").read_text(encoding="utf-8")
    assert "Démarrer l’analyse" in template
    assert "preferCurrentTab:!externalFallback" in template
    assert "selfBrowserSurface:'include'" in template
    assert "displaySurface:'browser'" in template
    assert "https://www.youtube.com/iframe_api" in template
    assert "setPlaybackRate" in template
    assert "playVideo" in template
    assert "captureShell.classList.add('studio-live')" in template
    assert "Ouvrir le replay YouTube" in template
    assert "capture externe disponible" in template
    assert "Turbo ≤15 min" in template
    assert "Lecture vidéo" in template
    assert "Analyse IA" in template
