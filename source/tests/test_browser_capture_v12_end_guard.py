from __future__ import annotations

import os
import time
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient

from analysis_product_routes import _capture_session_dir
from capture_turbo_routes import _read_state, _write_state
from capture_turbo_routes_v12 import _end_guard_decision
from db import SessionLocal
from main import app
from models import Match, User

client = TestClient(app)


def _create_match() -> tuple[int, str]:
    email = f"v12-end-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "V12 End Guard", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    response = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville",
            "opponent": "V12 End Guard",
            "competition": "Friendly",
            "match_date": "2026-09-07",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI&t=465s",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    match_id = int(location.split("/matches/", 1)[1].split("/", 1)[0])
    return match_id, location


def _capture_page() -> str:
    _, location = _create_match()
    page = client.get(location)
    assert page.status_code == 200
    return page.text


def test_v12_end_guard_finishes_near_complete_reader():
    assert _end_guard_decision(
        read_percent=99.5,
        stalled_seconds=0,
        elapsed_seconds=400,
        expected_seconds=500,
    ) == (True, "near_complete")


def test_v12_end_guard_breaks_the_observed_87_percent_plateau():
    assert _end_guard_decision(
        read_percent=98.35,
        stalled_seconds=7.1,
        elapsed_seconds=520,
        expected_seconds=515,
    ) == (True, "near_end_stall")


def test_v12_deadline_never_promotes_low_coverage_capture():
    assert _end_guard_decision(
        read_percent=80,
        stalled_seconds=120,
        elapsed_seconds=900,
        expected_seconds=500,
    ) == (False, "")
    assert _end_guard_decision(
        read_percent=95.2,
        stalled_seconds=0,
        elapsed_seconds=546,
        expected_seconds=500,
    ) == (True, "deadline_guard")


def test_production_capture_page_contains_independent_end_guards():
    html = _capture_page()
    assert "function v12EndGuard(" in html
    assert "function v12FlushAndStop(" in html
    assert "read>=98&&v12ReadChangedAt&&now-v12ReadChangedAt>=7000" in html
    assert "['recording','paused'].includes(recorder.state)" in html
    assert "p.force_finish" in html
    assert "client_read_percent" in html
    assert "client_finish_reason" in html
    assert "recorder.requestData" in html
    assert "r>=99.8" not in html
    priority = open(
        os.path.join(os.path.dirname(__file__), "..", "priority_analysis_routes.py"),
        encoding="utf-8",
    ).read()
    assert "from capture_turbo_routes_v14 import" in priority
    v14_source = open(
        os.path.join(os.path.dirname(__file__), "..", "capture_turbo_routes_v14.py"),
        encoding="utf-8",
    ).read()
    assert "import capture_turbo_routes_v13 as v13" in v14_source


def test_server_status_forces_finish_after_real_near_end_stall():
    match_id, _ = _create_match()
    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "0",
            "source_duration_seconds": "3600",
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert response.status_code == 200, response.text
    session_id = response.json()["session_id"]

    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        user = db.get(User, match.owner_id)
        root = _capture_session_dir(user, match, session_id)
        state = _read_state(root)
        state["read_percent"] = 98.35
        state["analysis_percent"] = 87.0
        state["v12_last_read_percent"] = 98.35
        state["v12_last_progress_at"] = time.time() - 8.0
        _write_state(root, state)
    finally:
        db.close()

    status = client.get(
        f"/matches/{match_id}/analysis/browser-capture/status?session_id={session_id}"
    )
    assert status.status_code == 200, status.text
    progress = status.json()["progress"]
    assert progress["force_finish"] is True
    assert progress["force_finish_reason"] == "near_end_stall"
    assert "fermeture automatique" in progress["phase"]
