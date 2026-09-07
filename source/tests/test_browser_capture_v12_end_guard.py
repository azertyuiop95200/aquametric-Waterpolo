from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient

from capture_turbo_routes_v12 import _end_guard_decision
from main import app

client = TestClient(app)


def _capture_page() -> str:
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
    page = client.get(response.headers["location"])
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
    # V9 maps a ~98.x% source read to an AI bar around 87%. If source progress
    # stops there for seven seconds, V12 must hand off instead of recording forever.
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
    assert "from capture_turbo_routes_v12 import" in open(
        os.path.join(os.path.dirname(__file__), "..", "priority_analysis_routes.py"),
        encoding="utf-8",
    ).read()
