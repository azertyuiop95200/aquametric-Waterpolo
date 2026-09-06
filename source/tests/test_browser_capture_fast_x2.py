from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_browser_capture_exposes_normal_and_fast_modes():
    template = (ROOT / "templates" / "browser_capture.html").read_text(encoding="utf-8")
    assert "Analyse normale x1" in template
    assert "Analyse rapide x2" in template
    assert "FAST_CAPTURE_SENTINEL = 1000000" in template
    assert "ytCommand('setPlaybackRate', [playbackRate])" in template
    assert "playbackRate === 2 ? FAST_CAPTURE_SENTINEL + sourceStart : sourceStart" in template


def test_rapid_analysis_remaps_2x_capture_to_source_timeline():
    rapid = (ROOT / "services" / "rapid_match_analysis.py").read_text(encoding="utf-8")
    assert "_FAST_CAPTURE_SENTINEL = 1_000_000.0" in rapid
    assert 'time_scale = 2.0' in rapid
    assert "float(sample.second) * time_scale + time_offset" in rapid
    assert '"source_time_scale": round(time_scale, 3)' in rapid
    assert "2× playback" in rapid
