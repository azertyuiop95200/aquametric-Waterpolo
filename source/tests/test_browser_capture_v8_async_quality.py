from pathlib import Path

import cv2
import numpy as np

from capture_turbo_routes_v7 import _quality_metrics
from capture_turbo_routes_v10 import _final_scan_budget

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
    assert "moving = min(87.5, read * 0.884)" in source
    assert '"analysis_percent": 89.0' in source
    assert '"accepted": True' in source
    assert "status_code=202" not in source
    assert "multiple_match_candidates" in source


def test_v10_adapts_warmup_and_reduces_redundant_final_scan():
    source = (ROOT / "capture_turbo_routes_v10.py").read_text(encoding="utf-8")
    priority = (ROOT / "priority_analysis_routes.py").read_text(encoding="utf-8")
    assert "warmGood" in source
    assert "setPlaybackRate(1)" in source
    assert "waited<6500" in source
    assert "progressive_samples" in source
    assert "visual_samples=visual_samples" in source
    assert "ocr_samples=ocr_samples" in source
    assert "from capture_turbo_routes_v13 import" in priority
    v13 = (ROOT / "capture_turbo_routes_v13.py").read_text(encoding="utf-8")
    assert "import capture_turbo_routes_v12 as v12" in v13
    assert "run_live_frame_analysis" in v13

    assert _final_scan_budget({"progressive_samples": 120}, 0, 3600, 4) == (120, 24, "dense live coverage")
    assert _final_scan_budget({"progressive_samples": 50}, 0, 3600, 4) == (132, 28, "live coverage")
    assert _final_scan_budget({}, 0, 1200, 1) == (136, 28, "short capture")
    assert _final_scan_budget({}, 0, 3600, 4) == (144, 32, "fallback verification")


def test_v11_has_independent_post_finish_watchdog_and_history_marker():
    source = (ROOT / "capture_turbo_routes_v11.py").read_text(encoding="utf-8")
    extensions = (ROOT / "extensions.py").read_text(encoding="utf-8")
    assert "aquametric-v11-final-watchdog" in source
    assert "response.clone().json()" in source
    assert "payload.accepted" in source
    assert "payload.status_url" in source
    assert "setTimeout(resolve, 600)" in source
    assert "browser_capture_finalize_v11" in source
    assert "background_tasks.add_task(_close_finalize_marker" in source
    assert "app.include_router(video_session_router)" in extensions


def test_fast_browser_normalization_uses_analysis_oriented_fallback():
    source = (ROOT / "services" / "browser_capture_media.py").read_text(encoding="utf-8")
    assert "fast_analysis: bool = False" in source
    assert '"-preset", "ultrafast"' in source
    assert "fps=12" in source
    assert "reencode_h264_fast_analysis" in source
