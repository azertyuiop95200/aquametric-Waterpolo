import os
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient

import capture_turbo_routes_v4
from db import SessionLocal
from main import app
from models import Match

client = TestClient(app)


def _create_url_match():
    email = f"capture-v4-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "Capture V4", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    response = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville",
            "opponent": "Video Test",
            "competition": "Friendly",
            "match_date": "2026-09-05",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI&t=465s",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    match_id = int(location.split("/matches/", 1)[1].split("/", 1)[0])
    return match_id, location


def test_capture_page_does_not_preload_manual_player_names_or_numbers():
    match_id, location = _create_url_match()
    response = client.get(location)
    assert response.status_code == 200
    html = response.text
    assert "Lecture vidéo" in html
    assert "Analyse IA" in html
    assert "Turbo ≤15 min" in html
    assert "https://www.youtube.com/iframe_api" in html
    assert "durée non détectée" in html
    assert "navigator.mediaDevices.getDisplayMedia" in html
    assert "displaySurface:'browser'" in html
    assert "recorder.start(5000)" in html
    assert "NotAllowedError" in html
    assert "Roster de référence" not in html
    assert "Morgane" not in html
    assert "Maëlle" not in html
    assert "Hitomi" not in html
    assert "Hanae" not in html
    assert "#13" not in html
    assert "#12" not in html


def test_security_allows_official_youtube_iframe_api():
    response = client.get("/")
    csp = response.headers.get("content-security-policy", "")
    assert "script-src 'self' 'unsafe-inline' https://www.youtube.com" in csp
    assert "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com" in csp
    assert "display-capture=(self)" in response.headers.get("permissions-policy", "")


def test_completed_vision_report_survives_sequence_enrichment_failure(monkeypatch):
    match_id, _ = _create_url_match()

    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "465",
            "source_duration_seconds": "0",
            "playback_rate": "1",
            "parallel_segments": "1",
        },
    )
    assert response.status_code == 200, response.text
    session_id = response.json()["session_id"]

    payload = b"A" * (80 * 1024)
    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/chunk",
        data={"session_id": session_id, "index": "0"},
        files={"chunk": ("capture.webm", payload, "video/webm")},
    )
    assert response.status_code == 200, response.text

    def fake_rapid(*args, **kwargs):
        return {
            "summary": {
                "visual_samples": 42,
                "scoreboard_observations": 5,
                "source_time_offset_seconds": 465.0,
            },
            "candidates": [{"second": 470.0}],
        }

    monkeypatch.setattr(capture_turbo_routes_v4, "run_rapid_analysis", fake_rapid)
    monkeypatch.setattr(
        capture_turbo_routes_v4,
        "materialize_deep_sequence_pack",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("sequence pack test failure")),
    )

    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/finish",
        data={
            "session_id": session_id,
            "source_start_second": "465",
            "source_duration_seconds": "0",
            "playback_rate": "1",
            "parallel_segments": "1",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["partial"] is True
    assert body["visual_samples"] == 42
    assert body["scoreboard_observations"] == 5
    assert body["redirect"] == f"/matches/{match_id}/analysis/result"
    assert "Séquences avancées non finalisées" in body["warning"]

    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        assert match is not None
        assert match.status == "browser_capture_analyzed_partial"
    finally:
        db.close()
