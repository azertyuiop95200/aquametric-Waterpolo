import os
import shutil
import subprocess
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import Match, VisionAnalysis, VisionSample


client = TestClient(app)


def _make_webm(path: Path, seconds: int = 8) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "ffmpeg is required for the real capture-pipeline test"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc2=size=640x360:rate=15:duration={seconds}",
        "-vf", "drawbox=x=20:y=20:w=210:h=70:color=white@0.9:t=fill,drawbox=x=35:y=35:w=30:h=30:color=black:t=fill",
        "-c:v", "libvpx-vp9",
        "-b:v", "900k",
        "-an",
        str(path),
    ]
    subprocess.run(cmd, check=True, timeout=60)
    payload = path.read_bytes()
    assert len(payload) > 64 * 1024, "synthetic capture must exceed the real minimum capture size"
    return payload


def test_browser_capture_chunks_reconstruct_real_video_and_create_vision_analysis(tmp_path):
    email = f"capture-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "Capture E2E", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    reference_url = "https://www.youtube.com/watch?v=Guo_UU282pI&t=465s"
    response = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville",
            "opponent": "Capture Test Opponent",
            "competition": "Friendly E2E",
            "match_date": "2026-09-05",
            "video_url": reference_url,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "/analysis/browser-capture" in location
    match_id = int(location.split("/matches/", 1)[1].split("/", 1)[0])

    page = client.get(location)
    assert page.status_code == 200
    assert "Démarrer l’analyse" in page.text
    assert "preferCurrentTab:!externalFallback" in page.text
    assert "displaySurface:'browser'" in page.text
    assert "Turbo ≤15 min" in page.text
    assert "Lecture vidéo" in page.text
    assert "Analyse IA" in page.text
    assert 'value="465.0"' in page.text
    assert "https://www.youtube.com/iframe_api" in page.text
    assert "Roster de référence" not in page.text
    assert "Maëlle" not in page.text
    assert "Hitomi" not in page.text
    assert "#13" not in page.text
    assert "#12" not in page.text

    response = client.post(f"/matches/{match_id}/analysis/browser-capture/session")
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    assert len(session_id) == 32

    capture_path = tmp_path / "capture.webm"
    payload = _make_webm(capture_path)
    split = max(96 * 1024, len(payload) // 4)
    chunks = [payload[i:i + split] for i in range(0, len(payload), split)]
    assert len(chunks) >= 2

    total = 0
    for index, data in enumerate(chunks):
        response = client.post(
            f"/matches/{match_id}/analysis/browser-capture/chunk",
            data={"session_id": session_id, "index": str(index)},
            files={"chunk": (f"capture-{index:05d}.webm", data, "video/webm")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True
        assert body["next_index"] == index + 1
        total += len(data)
        assert body["bytes"] == total

    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/finish",
        data={"session_id": session_id, "source_start_second": "465"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["visual_samples"] >= 8
    assert body["source_time_offset_seconds"] == 465.0
    assert body["redirect"] == f"/matches/{match_id}/analysis/result"

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
        assert vision.status == "complete"
        assert vision.source_kind == "browser_capture"
        assert vision.sample_count == body["visual_samples"]
        assert vision.sample_count >= 8
        assert vision.duration_seconds >= 7.0
        assert vision.width == 640
        assert vision.height == 360

        samples = db.scalars(
            select(VisionSample)
            .where(VisionSample.analysis_id == vision.id)
            .order_by(VisionSample.second.asc())
        ).all()
        assert len(samples) == vision.sample_count
        assert len(samples) >= 8
        assert samples[0].second >= 465.0
    finally:
        db.close()
