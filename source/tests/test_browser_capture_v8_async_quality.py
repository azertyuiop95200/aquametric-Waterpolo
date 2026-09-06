from pathlib import Path

import cv2
import numpy as np

from capture_turbo_routes_v7 import _quality_metrics

ROOT = Path(__file__).resolve().parents[1]


def test_quality_detector_distinguishes_blank_from_detailed_mosaic():
    blank = np.zeros((720, 1280, 3), dtype=np.uint8)
    low = _quality_metrics(blank, 4)
    assert low["quality_ok"] is False

    detailed = np.zeros((720, 1280, 3), dtype=np.uint8)
    for x in range(0, 1280, 24):
        cv2.line(detailed, (x, 0), (1279 - x, 719), (255, 255, 255), 2)
    high = _quality_metrics(detailed, 4)
    assert high["quality_ok"] is True
    assert high["quality_score"] > low["quality_score"]


def test_v7_quality_pause_is_time_safe_and_final_rescan_is_bounded():
    source = (ROOT / "capture_turbo_routes_v7.py").read_text(encoding="utf-8")
    assert "BackgroundTasks" in source
    assert '"accepted": True' in source
    assert "fast_analysis=True" in source
    assert "visual_samples=176" in source
    assert "ocr_samples=40" in source
    assert "recorder.start(3000)" in source
    assert "enterQualityPause" in source
    assert "recorder.pause()" in source
    assert "activeWallSeconds" in source
    assert "quality_pause_recommended" in source


def test_v8_resolves_post_render_match_urls_prebuffers_and_caps_quality_pauses():
    source = (ROOT / "capture_turbo_routes_v8.py").read_text(encoding="utf-8")
    assert 'html.replace("{{match.id}}", str(match_id))' in source
    assert "setTimeout(r,2800)" in source
    assert "qualityPauseCount>=6" in source


def test_v9_removes_85_plateau_and_uses_normal_async_http_handoff():
    source = (ROOT / "capture_turbo_routes_v9.py").read_text(encoding="utf-8")
    priority = (ROOT / "priority_analysis_routes.py").read_text(encoding="utf-8")
    assert "moving = min(87.5, read * 0.884)" in source
    assert '"analysis_percent": 89.0' in source
    assert '"accepted": True' in source
    assert "status_code=202" not in source
    assert "multiple_match_candidates" in source
    assert "from capture_turbo_routes_v9 import" in priority


def test_fast_browser_normalization_uses_analysis_oriented_fallback():
    source = (ROOT / "services" / "browser_capture_media.py").read_text(encoding="utf-8")
    assert "fast_analysis: bool = False" in source
    assert '"-preset", "ultrafast"' in source
    assert "fps=12" in source
    assert "reencode_h264_fast_analysis" in source
