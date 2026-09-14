import io
import json
import subprocess
import time
import uuid
import zipfile
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from services.capture_sequence_media import capture_window, create_capture_clip, materialize_capture_sequences
from services.capture_report_progress import latest_capture_root, report_progress
from services.capture_state_io import write_state_atomic
from services.media import ffmpeg_executable


@pytest.fixture
def mosaic(tmp_path):
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[:120, :160] = (20, 40, 220)
    frame[:120, 160:] = (20, 220, 40)
    frame[120:, :160] = (220, 40, 20)
    frame[120:, 160:] = (60, 180, 220)
    video = tmp_path / "mosaic.webm"
    subprocess.run([ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "bgr24", "-video_size", "320x240", "-framerate", "5",
        "-i", "pipe:0", "-an", "-c:v", "libvpx-vp9", "-threads", "1", "-lossless", "1", str(video)],
        input=frame.tobytes() * 50, check=True, capture_output=True, timeout=30)
    return video


@pytest.mark.parametrize("segments,rate,second,expected_size,expected_pixel", [
    (1, 1, 105, (320, 240), (60, 180, 220)),
    (2, 2, 125, (160, 240), (60, 180, 220)),
    (4, 2, 145, (160, 120), (220, 40, 20)),
])
def test_actual_clips_crop_the_right_pane_and_restore_source_time(mosaic, tmp_path, segments, rate, second, expected_size, expected_pixel):
    state = dict(source_start_second=100, source_duration_seconds=100 + 10 * segments * rate,
                 playback_rate=rate, parallel_segments=segments)
    target = dict(second=second, start_second=second - 3, end_second=second + 3)
    window = capture_window(target, state)
    path = create_capture_clip(mosaic, tmp_path / "clips", window)
    decoder = cv2.VideoCapture(str(path))
    try:
        assert (int(decoder.get(cv2.CAP_PROP_FRAME_WIDTH)), int(decoder.get(cv2.CAP_PROP_FRAME_HEIGHT))) == expected_size
        ok, image = decoder.read()
        assert ok
        pixel = image[image.shape[0] * 3 // 4, image.shape[1] * 3 // 4]
        assert np.max(np.abs(pixel.astype(int) - np.array(expected_pixel))) < 12
        duration = decoder.get(cv2.CAP_PROP_FRAME_COUNT) / decoder.get(cv2.CAP_PROP_FPS)
        assert abs(duration - (window["source_end"] - window["source_start"])) < .8
    finally:
        decoder.release()


def test_windows_never_cross_a_pane_boundary_or_accept_outside_capture():
    state = dict(source_start_second=100, source_duration_seconds=180, playback_rate=2, parallel_segments=4)
    window = capture_window(dict(second=140, start_second=136, end_second=146), state)
    assert window["pane"] == 2 and window["source_start"] == 140 and window["capture_start"] == 0
    assert capture_window(dict(second=180, start_second=178, end_second=188), state) is None


def test_progress_is_owner_scoped_and_stops_after_worker_disappears(tmp_path):
    match = SimpleNamespace(id=2, owner_id=7)
    root = tmp_path / ("u7_m2_" + "a" * 32)
    write_state_atomic(root, {"enrichment_status": "queued", "media_status": "queued", "v16_report_published_at": 100})
    write_state_atomic(tmp_path / ("u8_m2_" + "b" * 32), {"enrichment_status": "complete"})
    assert latest_capture_root(match, tmp_path) == root
    assert report_progress(match, root=root, now=120)["active"]
    assert not report_progress(match, root=root, now=710)["active"]
    assert report_progress(match, root=root, now=710)["stale"]


def test_saved_report_serves_real_clips_zip_assets_and_denies_other_accounts(mosaic):
    from main import app
    from db import SessionLocal
    from models import Event, Match, User
    from analysis_product_routes import EVIDENCE_DIR, _capture_session_dir
    from capture_turbo_routes import _read_state
    import shutil
    with TestClient(app) as client:
        client.post("/register", data={"name": "Clip tester", "email": f"clip-{uuid.uuid4().hex}@example.com", "password": "test-password123"})
        response = client.post("/analysis/url/create", data={"team_name": "Private clip team", "opponent": "Clip opponent",
                               "video_url": "https://example.com/fixture.webm"}, follow_redirects=False)
        mid = int(response.headers["location"].split("/matches/", 1)[1].split("/", 1)[0])
        with SessionLocal() as db:
            match = db.get(Match, mid)
            root = _capture_session_dir(db.get(User, match.owner_id), match, uuid.uuid4().hex)
            write_state_atomic(root, dict(source_start_second=100, source_duration_seconds=180,
                                          playback_rate=2, parallel_segments=4, enrichment_status="complete", media_status="queued"))
            shutil.copyfile(mosaic, root / "capture.webm")
            db.add(Event(match_id=mid, event_type="goal", second=145, confidence="CONFIRMED", note="But saisi pour le test de vidéo."))
            db.commit()
            result = materialize_capture_sequences(db, match, root, EVIDENCE_DIR)
            assert result["media_status"] == "complete", result
            assert result["media_clips"] >= 1
            clip = next(a for a in match.media_artifacts if a.artifact_type == "clip")
            clip_id, clip_file = clip.id, clip.file_path
            count = len(match.media_artifacts)
            materialize_capture_sequences(db, match, root, EVIDENCE_DIR)
            assert len(match.media_artifacts) == count  # retry reuses the generated files
            assert (root / "capture.webm").is_file()
            assert _read_state(root)["media_status"] == "complete"
        for path in [f"/matches/{mid}/analysis/result", f"/matches/{mid}/analysis/report.html"]:
            response = client.get(path)
            assert response.status_code == 200, response.text
            assert f'/matches/{mid}/evidence/{clip_id}' in response.text
            assert '<video' in response.text and "But saisi pour le test de vidéo." in response.text
        response = client.get(f"/matches/{mid}/evidence/{clip_id}", headers={"Range": "bytes=0-99"})
        assert response.status_code == 206 and len(response.content) == 100
        assert "ftyp" in response.content.decode("latin1")
        archive_response = client.get(f"/matches/{mid}/analysis/export.zip")
        with zipfile.ZipFile(io.BytesIO(archive_response.content)) as archive:
            clip_name = next(name for name in archive.namelist() if name.endswith('/' + clip_file))
            assert len(archive.read(clip_name)) > 100
            report = archive.read(next(name for name in archive.namelist() if name.endswith('/report.html'))).decode()
            assert '../05_evidence/clips/' + clip_file in report
        # The UI offers recovery while keeping owner checks and HTTP status.
        client.post("/register", data={"name": "Other", "email": f"other-{uuid.uuid4().hex}@example.com", "password": "test-password123"})
        for path in [f"/matches/{mid}/analysis/result", f"/matches/{mid}/analysis/browser-capture"]:
            denied = client.get(path)
            assert denied.status_code == 404
            assert 'Dossier de match indisponible' in denied.text and 'Private clip team' not in denied.text
        assert client.get(f"/matches/{mid}/evidence/{clip_id}").status_code == 404
        assert client.get(f"/matches/{mid}/analysis/progress").status_code == 404
        assert client.post(f"/matches/{mid}/analysis/captured-clips").status_code == 404


def test_missing_recording_does_not_leave_report_stuck_in_queued(tmp_path):
    write_state_atomic(tmp_path, {"media_status": "queued"})
    result = materialize_capture_sequences(None, None, tmp_path, tmp_path)
    assert result["media_status"] == "unavailable"
    assert json.loads((tmp_path / "progress.json").read_text())["media_status"] == "unavailable"
