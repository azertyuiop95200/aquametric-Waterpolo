from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_third_party_video_extraction_is_removed():
    remote = (ROOT / "services" / "remote_video.py").read_text(encoding="utf-8")
    assert "yt-dlp" not in remote
    assert "subprocess" not in remote
    assert "mode référence" in remote


def test_complete_runner_is_owned_upload_only():
    runner = (ROOT / "services" / "complete_analysis_runner.py").read_text(encoding="utf-8")
    assert "materialize_remote_video" not in runner
    assert 'match.video_source != "upload"' in runner
    assert "lecteur intégré + timestamps/bookmarks" in runner


def test_url_product_routes_use_reference_pipeline_without_clips():
    routes = (ROOT / "analysis_product_routes.py").read_text(encoding="utf-8")
    create_body = routes.split('def create_real_url_analysis', 1)[1].split('@router.post("/matches/{match_id}/analysis/start")', 1)[0]
    url_start_body = routes.split('def start_real_url_analysis', 1)[1].split('@router.get("/matches/{match_id}/analysis/result"', 1)[0]
    assert "_run_reference_only" in create_body
    assert "run_complete_analysis" not in create_body
    assert "_run_reference_only" in url_start_body
    assert "run_complete_analysis" not in url_start_body
    helper = routes.split('def _run_reference_only', 1)[1].split('@router.post("/analysis/url/create")', 1)[0]
    assert "run_product_analysis" in helper
    assert "max_clips=0" in helper
    assert "max_image_targets=0" in helper


def test_uploaded_video_keeps_dense_evidence_generation():
    routes = (ROOT / "analysis_product_routes.py").read_text(encoding="utf-8")
    start_body = routes.split('def start_real_analysis', 1)[1].split('@router.post("/matches/{match_id}/url-analysis/start")', 1)[0]
    assert "run_complete_analysis" in start_body
    assert "max_targets=72" in start_body
    assert "max_clips=48" in start_body
    assert "max_image_targets=72" in start_body
