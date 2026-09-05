from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_third_party_video_extraction_is_transient_and_cleaned_up():
    remote = (ROOT / "services" / "remote_video.py").read_text(encoding="utf-8")
    assert "materialize_remote_video" in remote
    assert "cleanup_remote_video" in remote
    assert '"yt-dlp"' in remote
    assert "httpx.stream" in remote
    assert "aquametric_url_" in remote
    assert "shutil.rmtree" in remote
    assert "never exposed" in remote or "never" in remote.lower()


def test_complete_runner_uses_transient_url_pixels_without_persisting_visual_artifacts():
    runner = (ROOT / "services" / "complete_analysis_runner.py").read_text(encoding="utf-8")
    assert "materialize_remote_video" in runner
    assert "cleanup_remote_video" in runner
    assert 'source_kind="third_party_transient"' in runner
    assert "persist_visual_artifacts=False" in runner
    assert "finally:" in runner
    assert "build_exact_evidence_pack" in runner  # uploaded videos still keep owned evidence


def test_url_product_routes_run_complete_analysis_but_never_generate_third_party_clips():
    routes = (ROOT / "analysis_product_routes.py").read_text(encoding="utf-8")
    create_body = routes.split('def create_real_url_analysis', 1)[1].split('@router.post("/matches/{match_id}/analysis/start")', 1)[0]
    url_start_body = routes.split('def start_real_url_analysis', 1)[1].split('@router.get("/matches/{match_id}/analysis/result"', 1)[0]
    helper = routes.split('def _run_match_analysis', 1)[1].split('@router.post("/analysis/url/create")', 1)[0]
    sequence_helper = routes.split('def _materialize_sequences_after_analysis', 1)[1].split('def _run_match_analysis', 1)[0]

    assert "_run_match_analysis" in create_body
    assert "_run_match_analysis" in url_start_body
    assert "run_complete_analysis" in helper
    assert "_record_failure" in helper
    assert "max_clips=0" in sequence_helper
    assert "max_image_targets=0" in sequence_helper


def test_uploaded_video_keeps_dense_owned_evidence_generation():
    routes = (ROOT / "analysis_product_routes.py").read_text(encoding="utf-8")
    sequence_helper = routes.split('def _materialize_sequences_after_analysis', 1)[1].split('def _run_match_analysis', 1)[0]
    assert "_is_owned_upload" in sequence_helper
    assert "max_targets=72" in sequence_helper
    assert "max_clips=48" in sequence_helper
    assert "max_image_targets=72" in sequence_helper


def test_url_failure_is_persisted_instead_of_becoming_zero_statistics():
    routes = (ROOT / "analysis_product_routes.py").read_text(encoding="utf-8")
    failure_helper = routes.split('def _record_failure', 1)[1].split('def _materialize_sequences_after_analysis', 1)[0]
    assert 'stage="video_ingest"' in failure_helper
    assert 'status="failed"' in failure_helper
    assert 'match.status = "analysis_failed"' in failure_helper
