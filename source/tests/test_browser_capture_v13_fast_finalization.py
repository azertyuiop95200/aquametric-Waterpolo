from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

import services.live_frame_match_analysis as live_frame_match_analysis
from db import SessionLocal
from main import app
from models import Match, VisionAnalysis, VisionSample

client = TestClient(app)


def _create_match() -> int:
    email = f"v13-fast-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "V13 Fast Final", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    response = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville",
            "opponent": "V13 Fast Opponent",
            "competition": "Friendly",
            "match_date": "2026-09-07",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return int(response.headers["location"].split("/matches/", 1)[1].split("/", 1)[0])


def _jpeg() -> bytes:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    boxes = ((0, 0, 640, 360), (640, 0, 1280, 360), (0, 360, 640, 720), (640, 360, 1280, 720))
    for idx, (x1, y1, x2, y2) in enumerate(boxes):
        base = 50 + idx * 35
        frame[y1:y2, x1:x2] = (base, min(255, base + 45), min(255, base + 90))
        cv2.circle(frame, (x1 + 150 + idx * 20, y1 + 150), 45 + idx * 5, (255, 255, 255), -1)
        cv2.line(frame, (x1 + 50, y1 + 280), (x1 + 500, y1 + 80), (20, 20, 20), 8)
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 84])
    assert ok
    return encoded.tobytes()


def test_v13_finishes_from_retained_live_frames_without_rescanning_webm(monkeypatch):
    monkeypatch.setattr(live_frame_match_analysis, "tesseract_available", lambda: False)
    match_id = _create_match()
    session = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "0",
            "source_duration_seconds": "256",
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert session.status_code == 200, session.text
    session_id = session.json()["session_id"]

    frame = _jpeg()
    for wall_second in range(0, 33, 4):
        response = client.post(
            f"/matches/{match_id}/analysis/browser-capture/frame",
            data={"session_id": session_id, "wall_second": str(wall_second)},
            files={"frame": ("progress.jpg", frame, "image/jpeg")},
        )
        assert response.status_code == 200, response.text

    # The fast path uses the retained decoded JPEG evidence. A capture byte stream
    # still has to exist and be non-trivial, but it is deliberately not reopened
    # by the V13 core finalizer.
    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/chunk",
        data={"session_id": session_id, "index": "0"},
        files={"chunk": ("capture-00000.webm", b"x" * (80 * 1024), "video/webm")},
    )
    assert response.status_code == 200, response.text

    finish = client.post(
        f"/matches/{match_id}/analysis/browser-capture/finish",
        data={
            "session_id": session_id,
            "source_start_second": "0",
            "source_duration_seconds": "256",
            "playback_rate": "2",
            "parallel_segments": "4",
            "client_read_percent": "99",
            "client_finish_reason": "near_end_stall",
        },
    )
    assert finish.status_code == 200, finish.text
    body = finish.json()
    assert body["accepted"] is True
    assert body["fast_finalization"] is True
    assert body["retained_live_frames"] >= 8

    status = client.get(body["status_url"])
    assert status.status_code == 200, status.text
    progress = status.json()["progress"]
    assert progress["status"] in {"complete", "partial"}
    assert progress["analysis_percent"] == 100.0
    assert progress["finalization_engine"] == "live-frame-final-v1"
    assert progress["retained_live_frames"] >= 8
    assert progress["finalization_elapsed_seconds"] >= 0.0

    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        assert match is not None
        assert match.status in {"browser_capture_analyzed", "browser_capture_analyzed_partial"}
        vision = db.scalar(
            select(VisionAnalysis)
            .where(VisionAnalysis.match_id == match_id)
            .order_by(VisionAnalysis.id.desc())
        )
        assert vision is not None
        assert vision.engine_version == "live-frame-vision-v1"
        assert vision.duration_seconds == 256.0
        samples = db.scalars(
            select(VisionSample)
            .where(VisionSample.analysis_id == vision.id)
            .order_by(VisionSample.second.asc())
        ).all()
        assert len(samples) == vision.sample_count
        assert len(samples) >= 24
        assert samples[0].second >= 0.0
        assert samples[-1].second > 220.0
        assert samples[-1].second <= 256.0
    finally:
        db.close()


def test_priority_routes_use_v13_finalizer():
    source = open(os.path.join(os.path.dirname(__file__), "..", "priority_analysis_routes.py"), encoding="utf-8").read()
    assert "from capture_turbo_routes_v13 import" in source
