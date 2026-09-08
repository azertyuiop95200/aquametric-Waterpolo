import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient

import capture_turbo_routes_v14 as v14
from capture_turbo_routes import _read_state, _write_state
from db import SessionLocal
from main import app
from models import AnalysisJob

client = TestClient(app)


def _create_match(opponent: str):
    email = f"v11-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        "/register",
        data={"name": "V11 Test", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    r = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville",
            "opponent": opponent,
            "competition": "Friendly",
            "match_date": "2026-09-05",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI&t=465s",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    location = r.headers["location"]
    match_id = int(location.split("/matches/", 1)[1].split("/", 1)[0])
    return match_id, location


def test_v11_capture_page_installs_watchdog_before_studio_logic():
    match_id, location = _create_match("V11 Watchdog Page")
    r = client.get(location)
    assert r.status_code == 200, r.text
    html = r.text
    assert 'id="aquametric-v11-final-watchdog"' in html
    assert "response.clone().json()" in html
    assert "payload.accepted" in html
    assert "payload.status_url" in html
    assert f"/matches/{match_id}/analysis/browser-capture/finish" in html
    assert "{{match.id}}" not in html


def test_v11_finish_creates_history_marker_closes_it_and_exposes_surfaces(monkeypatch):
    opponent = f"V11 Publish {uuid.uuid4().hex[:8]}"
    match_id, _ = _create_match(opponent)

    r = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "0",
            "source_duration_seconds": "64",
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert r.status_code == 200, r.text
    session_id = r.json()["session_id"]

    r = client.post(
        f"/matches/{match_id}/analysis/browser-capture/chunk",
        data={"session_id": session_id, "index": "0"},
        files={"chunk": ("capture.webm", b"A" * (80 * 1024), "video/webm")},
    )
    assert r.status_code == 200, r.text

    def fake_core(match_id, root_value, start, total_duration, rate, segments):
        root = v14.Path(root_value)
        out = _read_state(root)
        out.update({
            "status": "complete",
            "analysis_percent": 100.0,
            "read_percent": 100.0,
            "phase": "rapport Vision V14 prêt",
            "redirect": f"/matches/{match_id}/analysis/result",
            "visual_samples": 48,
            "scoreboard_observations": 3,
            "parallel_segments": segments,
            "finalization_engine": "test-v14",
        })
        _write_state(root, out)

    monkeypatch.setattr(v14, "_core_finalize_job_v14", fake_core)
    monkeypatch.setattr(v14.v13, "_enrich_after_report", lambda *args, **kwargs: None)

    r = client.post(
        f"/matches/{match_id}/analysis/browser-capture/finish",
        data={
            "session_id": session_id,
            "source_start_second": "0",
            "source_duration_seconds": "64",
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["accepted"] is True

    status = client.get(payload["status_url"])
    assert status.status_code == 200, status.text
    progress = status.json()["progress"]
    assert progress["status"] == "complete"
    assert progress["analysis_percent"] == 100.0
    assert progress["finalization_job_status"] == "complete"
    assert progress["finalization_job_progress"] == 100

    db = SessionLocal()
    try:
        marker = db.query(AnalysisJob).filter(
            AnalysisJob.match_id == match_id,
            AnalysisJob.stage == "browser_capture_finalize_v11",
        ).order_by(AnalysisJob.id.desc()).first()
        assert marker is not None
        assert marker.status == "complete"
        assert marker.progress == 100
    finally:
        db.close()

    history = client.get("/analysis-history")
    assert history.status_code == 200, history.text
    assert opponent in history.text
    assert "browser_capture_finalize_v11" in history.text

    library = client.get("/analysis-library")
    assert library.status_code == 200, library.text
    assert opponent in library.text

    session = client.get(f"/analysis/video-session-elite?match_id={match_id}")
    assert session.status_code == 200, session.text
    assert opponent in session.text
