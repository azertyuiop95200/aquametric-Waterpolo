from __future__ import annotations

import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

import capture_turbo_routes_v16 as v16
from analysis_product_routes import _capture_session_dir
from capture_turbo_routes import _read_state, _write_state
from db import SessionLocal
from main import app
from models import AutonomousAnalysis, Match, User, VisionAnalysis

client = TestClient(app)


def _create_match() -> int:
    email = f"v16-report-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "V16 Report First", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    response = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville",
            "opponent": "V16 Anti Stall",
            "competition": "Friendly",
            "match_date": "2026-09-09",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return int(response.headers["location"].split("/matches/", 1)[1].split("/", 1)[0])


def test_report_ready_marker_wins_over_late_89_percent_progress_write(tmp_path):
    root = tmp_path / "session"
    _write_state(root, {"status": "running", "analysis_percent": 89.0, "read_percent": 100.0})
    v16._write_report_marker(
        root,
        {
            "status": "partial",
            "analysis_percent": 100.0,
            "read_percent": 100.0,
            "phase": "rapport disponible",
            "redirect": "/matches/1/analysis/result",
            "finalization_engine": "report-first-v16",
            "report_quality": "published_progressive_evidence",
            "report_ready": True,
            "enrichment_status": "queued",
        },
    )

    # Simulate the exact last-writer-wins race that used to put the UI back at 89%.
    _write_state(root, {"status": "running", "analysis_percent": 89.0, "read_percent": 100.0})
    restored = v16._terminal_from_marker(root, _read_state(root))

    assert restored["status"] == "partial"
    assert restored["analysis_percent"] == 100.0
    assert restored["report_ready"] is True
    assert restored["finalization_engine"] == "report-first-v16"


def test_v16_ui_redirects_immediately_when_finish_says_report_ready():
    html = "before if(payload.accepted){const done=await waitForFinalReport(payload); after"
    patched = v16._patch_report_first_ui(html, 42)

    assert "payload.accepted&&payload.report_ready" in patched
    assert "/matches/42/analysis/result" in patched
    assert "120" in patched
    # Compatibility wait remains only for older/non-V16 responses.
    assert "if(payload.accepted){const done=await waitForFinalReport(payload);" in patched


def test_finish_publishes_100_before_optional_verification(monkeypatch):
    # The test deliberately uses an invalid WebM. Heavy verification is made a
    # no-op: report publication itself must not depend on video decode success.
    monkeypatch.setattr(v16, "_verify_after_publish", lambda *args, **kwargs: None)
    monkeypatch.setattr(v16.v15.v14.v13, "_enrich_after_report", lambda *args, **kwargs: None)

    match_id = _create_match()
    session = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "0",
            "source_duration_seconds": "2400",
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert session.status_code == 200, session.text
    session_id = session.json()["session_id"]

    chunk = client.post(
        f"/matches/{match_id}/analysis/browser-capture/chunk",
        data={"session_id": session_id, "index": "0"},
        files={"chunk": ("capture-00000.webm", b"x" * (80 * 1024), "video/webm")},
    )
    assert chunk.status_code == 200, chunk.text

    finish = client.post(
        f"/matches/{match_id}/analysis/browser-capture/finish",
        data={
            "session_id": session_id,
            "source_start_second": "0",
            "source_duration_seconds": "2400",
            "playback_rate": "2",
            "parallel_segments": "4",
            "client_read_percent": "100",
            "client_finish_reason": "normal",
        },
    )
    assert finish.status_code == 200, finish.text
    body = finish.json()
    assert body["accepted"] is True
    assert body["report_ready"] is True
    assert body["analysis_percent"] == 100.0
    assert body["finalization_engine"] == "report-first-v16"

    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        user = db.get(User, match.owner_id)
        root = _capture_session_dir(user, match, session_id)
        assert v16._read_report_marker(root)["report_ready"] is True

        # A stale concurrent writer must never revive 89% after publication.
        stale = _read_state(root)
        stale.update({"status": "running", "analysis_percent": 89.0})
        _write_state(root, stale)
    finally:
        db.close()

    status = client.get(body["status_url"])
    assert status.status_code == 200, status.text
    progress = status.json()["progress"]
    assert progress["status"] in {"complete", "partial"}
    assert progress["analysis_percent"] == 100.0
    assert progress["report_ready"] is True

    db = SessionLocal()
    try:
        vision = db.scalar(
            select(VisionAnalysis)
            .where(VisionAnalysis.match_id == match_id)
            .order_by(VisionAnalysis.id.desc())
        )
        autonomous = db.scalar(
            select(AutonomousAnalysis)
            .where(AutonomousAnalysis.match_id == match_id)
            .order_by(AutonomousAnalysis.id.desc())
        )
        assert vision is not None
        assert autonomous is not None
        assert vision.status == "partial"
        assert autonomous.status == "partial"
    finally:
        db.close()
