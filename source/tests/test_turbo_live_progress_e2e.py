import os
import shutil
import subprocess
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

import capture_turbo_routes
import services.mosaic_match_analysis as mosaic_match_analysis
from db import SessionLocal
from main import app
from models import Match, VisionAnalysis, VisionSample

client = TestClient(app)


def _register_and_create_match(*, duration: float = 497.0):
    email = f"turbo-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "Turbo E2E", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    response = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville",
            "opponent": "Turbo Test Opponent",
            "competition": "Friendly Turbo E2E",
            "match_date": "2026-09-05",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI&t=465s",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    match_id = int(location.split("/matches/", 1)[1].split("/", 1)[0])
    return match_id, location, duration


def _jpeg_frame(width=1280, height=720):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    half_w, half_h = width // 2, height // 2
    values = (60, 100, 140, 180)
    boxes = (
        (0, 0, half_w, half_h),
        (half_w, 0, width, half_h),
        (0, half_h, half_w, height),
        (half_w, half_h, width, height),
    )
    for value, (x1, y1, x2, y2) in zip(values, boxes):
        frame[y1:y2, x1:x2] = (value, min(255, value + 30), min(255, value + 60))
        cv2.rectangle(frame, (x1 + 20, y1 + 20), (x1 + 210, y1 + 70), (255, 255, 255), -1)
    ok, payload = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
    assert ok
    return payload.tobytes()


def _make_mosaic_webm(path: Path, seconds: int = 4) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "ffmpeg is required for the turbo E2E test"
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=15:duration={seconds}",
        "-f", "lavfi", "-i", f"testsrc=size=640x360:rate=15:duration={seconds}",
        "-f", "lavfi", "-i", f"color=c=blue:size=640x360:rate=15:duration={seconds}",
        "-f", "lavfi", "-i", f"color=c=green:size=640x360:rate=15:duration={seconds}",
        "-filter_complex", "[0:v][1:v]hstack=inputs=2[top];[2:v][3:v]hstack=inputs=2[bot];[top][bot]vstack=inputs=2[v]",
        "-map", "[v]", "-c:v", "libvpx-vp9", "-b:v", "1600k", "-an", str(path),
    ]
    subprocess.run(cmd, check=True, timeout=60)
    payload = path.read_bytes()
    assert len(payload) > 64 * 1024
    return payload


def test_live_progress_routes_are_priority_routes_and_process_real_frames(monkeypatch):
    monkeypatch.setattr(capture_turbo_routes, "tesseract_available", lambda: False)
    match_id, location, source_duration = _register_and_create_match(duration=497.0)

    page = client.get(location)
    assert page.status_code == 200
    assert "Lecture vidéo" in page.text
    assert "Analyse IA" in page.text
    assert "Turbo ≤15 min" in page.text

    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "465",
            "source_duration_seconds": str(source_duration),
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parallel_segments"] == 4
    assert body["playback_rate"] == 2.0
    assert body["expected_capture_seconds"] == 4.0
    session_id = body["session_id"]

    frame = _jpeg_frame()
    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/frame",
        data={"session_id": session_id, "wall_second": "2"},
        files={"frame": ("progress.jpg", frame, "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    progress = response.json()["progress"]
    assert progress["progressive_samples"] == 4
    assert progress["analysis_percent"] > 0
    assert progress["read_percent"] > 0
    assert "pré-analyse" in progress["phase"]

    status = client.get(
        f"/matches/{match_id}/analysis/browser-capture/status",
        params={"session_id": session_id},
    )
    assert status.status_code == 200
    status_progress = status.json()["progress"]
    assert status_progress["progressive_samples"] == 4
    assert status_progress["analysis_percent"] == progress["analysis_percent"]


def test_turbo_finish_analyzes_four_quadrants_and_maps_full_source_timeline(tmp_path, monkeypatch):
    monkeypatch.setattr(mosaic_match_analysis, "tesseract_available", lambda: False)
    match_id, _, source_duration = _register_and_create_match(duration=497.0)
    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "465",
            "source_duration_seconds": str(source_duration),
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    capture_path = tmp_path / "turbo-mosaic.webm"
    payload = _make_mosaic_webm(capture_path, seconds=4)
    split = max(128 * 1024, len(payload) // 4)
    chunks = [payload[i:i + split] for i in range(0, len(payload), split)]
    for index, data in enumerate(chunks):
        response = client.post(
            f"/matches/{match_id}/analysis/browser-capture/chunk",
            data={"session_id": session_id, "index": str(index)},
            files={"chunk": (f"capture-{index:05d}.webm", data, "video/webm")},
        )
        assert response.status_code == 200, response.text

    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/finish",
        data={
            "session_id": session_id,
            "source_start_second": "465",
            "source_duration_seconds": str(source_duration),
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["parallel_segments"] == 4
    assert body["visual_samples"] >= 80

    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        assert match is not None
        assert match.status == "browser_capture_analyzed"
        vision = db.scalar(
            select(VisionAnalysis)
            .where(VisionAnalysis.match_id == match_id)
            .order_by(VisionAnalysis.id.desc())
        )
        assert vision is not None
        assert vision.engine_version == "parallel-mosaic-vision-v2"
        assert vision.duration_seconds == 32.0
        samples = db.scalars(
            select(VisionSample)
            .where(VisionSample.analysis_id == vision.id)
            .order_by(VisionSample.second.asc())
        ).all()
        assert len(samples) == vision.sample_count
        assert samples[0].second >= 465.0
        assert samples[-1].second > 490.0
        assert samples[-1].second <= 497.0
    finally:
        db.close()
