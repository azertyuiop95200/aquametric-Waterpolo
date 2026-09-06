from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_browser_capture_exposes_normal_fast_and_turbo_modes():
    template = (ROOT / "templates" / "browser_capture_v4.html").read_text(encoding="utf-8")
    assert "Analyse normale x1" in template
    assert "Analyse rapide x2" in template
    assert "Turbo ≤15 min" in template
    assert "4 segments parallèles × x2" in template
    assert "Lecture vidéo" in template
    assert "Analyse IA" in template
    assert "/analysis/browser-capture/frame" in template
    assert "/analysis/browser-capture/status" in template
    assert "recorder.start(5000)" in template
    assert "setPlaybackRate" in template
    assert "durée non détectée" in template
    assert "chooseMode('fast')" in template


def test_rapid_analysis_remaps_2x_capture_to_source_timeline():
    rapid = (ROOT / "services" / "rapid_match_analysis.py").read_text(encoding="utf-8")
    assert "_FAST_CAPTURE_SENTINEL = 1_000_000.0" in rapid
    assert "time_scale = 2.0" in rapid
    assert "float(sample.second) * time_scale + time_offset" in rapid
    assert '"source_time_scale": round(time_scale, 3)' in rapid
    assert "2× playback" in rapid


def test_turbo_routes_start_real_preanalysis_while_capture_is_running():
    routes = (ROOT / "capture_turbo_routes.py").read_text(encoding="utf-8")
    assert "def turbo_progress_frame" in routes
    assert "_progressive_frame_analysis" in routes
    assert "progressive_samples" in routes
    assert "progressive_ocr_hits" in routes
    assert '"analysis_percent"' in routes
    assert "run_mosaic_analysis" in routes


def test_mosaic_engine_maps_four_parallel_segments_to_source_timeline():
    engine = (ROOT / "services" / "mosaic_match_analysis.py").read_text(encoding="utf-8")
    assert "parallel YouTube segments" in engine
    assert "segment_span = source_duration / segments" in engine
    assert "seg * segment_span + float(capture_second) * rate" in engine
    assert '"parallel_segments": segments' in engine
    assert '"pipeline": "parallel-mosaic-v2-focused-ocr"' in engine
    assert "_ocr_target_seconds" in engine
    assert "budget_exhausted" in engine
