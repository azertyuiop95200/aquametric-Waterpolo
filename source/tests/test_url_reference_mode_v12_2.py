from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_server_side_third_party_extraction_remains_disabled():
    remote = (ROOT / "services" / "remote_video.py").read_text(encoding="utf-8")
    assert "yt-dlp" not in remote
    assert "subprocess" not in remote
    assert "mode référence" in remote


def test_complete_runner_remains_owned_upload_only():
    runner = (ROOT / "services" / "complete_analysis_runner.py").read_text(encoding="utf-8")
    assert "materialize_remote_video" not in runner
    assert 'match.video_source != "upload"' in runner
    assert "lecteur intégré + timestamps/bookmarks" in runner


def test_url_routes_send_user_to_browser_capture_instead_of_fake_zero_analysis():
    routes = (ROOT / "analysis_product_routes.py").read_text(encoding="utf-8")
    create_body = routes.split('def create_real_url_analysis', 1)[1].split('@router.post("/matches/{match_id}/analysis/start")', 1)[0]
    start_body = routes.split('def start_real_analysis', 1)[1].split('@router.post("/matches/{match_id}/url-analysis/start")', 1)[0]
    url_start_body = routes.split('def start_real_url_analysis', 1)[1].split('@router.get("/matches/{match_id}/analysis/browser-capture"', 1)[0]
    assert "/analysis/browser-capture" in create_body
    assert "_run_reference_only(db, match)" not in create_body
    assert "/analysis/browser-capture" in start_body
    assert "/analysis/browser-capture" in url_start_body
    assert 'match.status = "url_capture_required"' in start_body


def test_browser_capture_runs_real_vision_ocr_then_deletes_pixels():
    routes = (ROOT / "analysis_product_routes.py").read_text(encoding="utf-8")
    finish_body = routes.split('def finish_browser_capture', 1)[1].split('@router.get("/matches/{match_id}/analysis/result"', 1)[0]
    assert "run_rapid_analysis" in finish_body
    assert 'source_kind="browser_capture"' in finish_body
    assert "persist_visual_artifacts=False" in finish_body
    assert "time_offset_seconds=" in finish_body
    assert 'match.status = "browser_capture_analyzed"' in finish_body
    assert "finally:" in finish_body
    assert "shutil.rmtree(root, ignore_errors=True)" in finish_body


def test_browser_capture_streams_small_chunks_instead_of_buffering_whole_match():
    template = (ROOT / "templates" / "browser_capture.html").read_text(encoding="utf-8")
    assert "navigator.mediaDevices.getDisplayMedia" in template
    assert "new MediaRecorder" in template
    assert "/analysis/browser-capture/session" in template
    assert "/analysis/browser-capture/chunk" in template
    assert "/analysis/browser-capture/finish" in template
    assert "recorder.start(5000)" in template
    assert "uploadChain" in template
    assert "source_start_second" in template
    assert "chunks.push" not in template


def test_uploaded_video_keeps_dense_evidence_generation():
    routes = (ROOT / "analysis_product_routes.py").read_text(encoding="utf-8")
    start_body = routes.split('def start_real_analysis', 1)[1].split('@router.post("/matches/{match_id}/url-analysis/start")', 1)[0]
    assert "run_complete_analysis" in start_body
    assert "max_targets=72" in start_body
    assert "max_clips=48" in start_body
    assert "max_image_targets=72" in start_body
