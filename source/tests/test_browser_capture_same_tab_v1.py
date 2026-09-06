from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_browser_capture_prefers_same_tab_and_embeds_youtube_replay():
    template = (ROOT / "templates" / "browser_capture.html").read_text(encoding="utf-8")
    assert "Démarrer l’analyse dans cet onglet" in template
    assert "preferCurrentTab:true" in template
    assert "selfBrowserSurface:'include'" in template
    assert "displaySurface:'browser'" in template
    assert "enablejsapi=1" in template
    assert "setPlaybackRate" in template
    assert "playVideo" in template
    assert "captureShell.classList.add('studio-live')" in template
    assert "Ouvrir le replay" in template
    assert "Turbo ≤15 min" in template
    assert "Lecture vidéo" in template
    assert "Analyse IA" in template
