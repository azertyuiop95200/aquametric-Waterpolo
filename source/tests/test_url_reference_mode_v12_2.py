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


def test_uploaded_video_keeps_dense_evidence_generation_in_background(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    import video_action_routes as routes
    import services.complete_analysis_runner as complete
    import services.deep_analysis_sequences as sequences
    from models import Match
    match, job = SimpleNamespace(id=1), SimpleNamespace(status="queued", progress=0, message="")
    calls = []
    @contextmanager
    def session():
        yield SimpleNamespace(get=lambda model, key: match if model is Match else job,
                              commit=lambda: None, rollback=lambda: None)
    monkeypatch.setattr(routes, "SessionLocal", session)
    monkeypatch.setattr(complete, "run_complete_analysis", lambda *args, **kw: calls.append(("analysis", kw)))
    monkeypatch.setattr(sequences, "materialize_deep_sequence_pack", lambda *args, **kw: calls.append(("media", kw)))
    routes.upload_analysis_background(1, 2, False)
    assert [kind for kind, options in calls] == ["analysis", "media"]
    assert calls[0][1]["include_audio"] is False
    assert calls[1][1]["max_targets"] == 72 and calls[1][1]["max_clips"] == 48
    assert calls[1][1]["max_image_targets"] == 72
    assert job.status == "complete" and job.progress == 100
