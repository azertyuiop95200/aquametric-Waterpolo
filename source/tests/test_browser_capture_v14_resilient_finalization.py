from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from capture_turbo_routes_v14 import V14_FINALIZATION_WATCHDOG_SECONDS, _should_rescue
from db import SessionLocal
from main import app
from models import AutonomousAnalysis, Match, VisionAnalysis

client = TestClient(app)


def _create_match() -> int:
    email = f"v14-resilient-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "V14 Resilient", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    response = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville",
            "opponent": "Fallback Opponent",
            "competition": "Friendly",
            "match_date": "2026-09-08",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return int(response.headers["location"].split("/matches/", 1)[1].split("/", 1)[0])


def test_sparse_capture_publishes_terminal_truthful_report_without_blocking_on_video_decode():
    match_id = _create_match()
    session = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "0",
            "source_duration_seconds": "180",
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert session.status_code == 200, session.text
    session_id = session.json()["session_id"]

    chunk = client.post(
        f"/matches/{match_id}/analysis/browser-capture/chunk",
        data={"session_id": session_id, "index": "0"},
        files={"chunk": ("capture.webm", b"not-a-video" + b"x" * (80 * 1024), "video/webm")},
    )
    assert chunk.status_code == 200, chunk.text

    finish = client.post(
        f"/matches/{match_id}/analysis/browser-capture/finish",
        data={
            "session_id": session_id,
            "source_duration_seconds": "180",
            "playback_rate": "2",
            "parallel_segments": "4",
            "client_read_percent": "95",
            "client_finish_reason": "deadline_guard",
        },
    )
    assert finish.status_code == 200, finish.text
    body = finish.json()
    assert body["accepted"] is True
    assert body["non_blocking"] is True
    assert body["report_ready"] is True
    assert body["analysis_percent"] == 100.0
    assert body["max_wait_before_rescue_seconds"] == 0.0

    status = client.get(body["status_url"])
    assert status.status_code == 200, status.text
    progress = status.json()["progress"]
    assert progress["status"] == "partial"
    assert progress["analysis_percent"] == 100.0
    assert progress["report_ready"] is True
    assert progress["finalization_engine"] == "report-first-v16"
    assert progress["report_quality"] == "published_progressive_evidence"
    assert progress["retry_available"] is False
    assert progress["enrichment_status"] == "failed"

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
        autonomy = db.scalar(
            select(AutonomousAnalysis)
            .where(AutonomousAnalysis.match_id == match_id)
            .order_by(AutonomousAnalysis.id.desc())
        )
        assert vision is not None
        assert autonomy is not None
        assert vision.engine_version == "live-frame-resilient-v14"
        assert vision.status == "partial"
        assert vision.sample_count == 0
        assert autonomy.status == "partial"
        assert '"processing_completion_percent": 100.0' in autonomy.summary_json
        assert '"report_quality": "evidence_limited"' in autonomy.summary_json
    finally:
        db.close()


def test_v14_watchdog_only_rescues_stalled_finalization():
    now = 1000.0
    timeout = V14_FINALIZATION_WATCHDOG_SECONDS
    assert _should_rescue("finalizing", now - timeout - 0.1, now=now) is True
    assert _should_rescue("queued_finalization", now - timeout - 5.0, now=now) is True
    assert _should_rescue("finalizing", now - timeout + 0.1, now=now) is False
    assert _should_rescue("complete", now - timeout - 100.0, now=now) is False
    assert _should_rescue("partial", now - timeout - 100.0, now=now) is False
