import os
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import capture_turbo_routes_v11 as v11
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

    def fake_v10_finish(
        match_id,
        request,
        background_tasks,
        session_id,
        source_start_second=0.0,
        source_duration_seconds=0.0,
        playback_rate=1.0,
        parallel_segments=1,
        scope_mode="auto",
        analysis_scope_start_second=0.0,
        analysis_scope_end_second=0.0,
        db=None,
    ):
        user, match = v11._owned_match(match_id, request, db)
        root = v11._capture_session_dir(user, match, session_id)
        state = _read_state(root)
        state.update({
            "status": "queued_finalization",
            "analysis_percent": 89.0,
            "read_percent": 100.0,
            "phase": "capture reçue",
        })
        _write_state(root, state)

        def publish():
            out = _read_state(root)
            out.update({
                "status": "complete",
                "analysis_percent": 100.0,
                "read_percent": 100.0,
                "phase": "rapport Vision prêt",
                "redirect": f"/matches/{match_id}/analysis/result",
                "visual_samples": 48,
                "scoreboard_observations": 3,
            })
            _write_state(root, out)

        background_tasks.add_task(publish)
        return JSONResponse({
            "ok": True,
            "accepted": True,
            "analysis_percent": 89.0,
            "status_url": f"/matches/{match_id}/analysis/browser-capture/status?session_id={session_id}",
            "redirect": f"/matches/{match_id}/analysis/result",
        })

    monkeypatch.setattr(v11.v10, "turbo_finish_capture", fake_v10_finish)

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
