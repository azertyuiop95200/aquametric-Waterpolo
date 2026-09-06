import os
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import Match, Team
from analysis_product_routes import _capture_session_dir
from capture_turbo_routes import _read_state, _write_state

client = TestClient(app)


def _register():
    email = f"flex-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/register", data={"name": "Flex", "email": email, "password": "password123"}, follow_redirects=False)
    assert r.status_code == 303


def test_match_new_accepts_arbitrary_team_names_and_gender():
    _register()
    r = client.get("/matches/new")
    assert r.status_code == 200
    html = r.text
    assert "n’importe quel nom d’équipe" in html
    assert 'name="team_name"' in html
    assert 'name="opponent"' in html
    assert 'name="category"' in html
    assert 'value="Women"' in html
    assert 'value="Men"' in html
    assert "La vidéo contient-elle plusieurs matchs" in html
    assert 'name="scope_mode"' in html


def test_url_analysis_creates_unknown_mens_team_and_preserves_manual_scope():
    _register()
    team_name = f"Club masculin libre {uuid.uuid4().hex[:6]}"
    opponent = f"Adversaire libre {uuid.uuid4().hex[:6]}"
    r = client.post(
        "/analysis/url/create",
        data={
            "team_name": team_name,
            "opponent": opponent,
            "category": "Men",
            "competition": "Friendly men",
            "match_date": "2026-09-06",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI",
            "scope_mode": "manual",
            "scope_start_second": "120",
            "scope_end_second": "900",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    location = r.headers["location"]
    assert "scope_mode=manual" in location
    assert "scope_start=120.000" in location
    assert "scope_end=900.000" in location
    match_id = int(location.split("/matches/", 1)[1].split("/", 1)[0])
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        assert match is not None
        assert match.opponent == opponent
        team = db.get(Team, match.team_id)
        assert team is not None
        assert team.name == team_name
        assert team.category == "Men"
    finally:
        db.close()

    page = client.get(location)
    assert page.status_code == 200
    assert team_name in page.text
    assert opponent in page.text
    assert "requestedScopeEnd=900.000" in page.text


def test_multimatch_finish_requests_scope_instead_of_mixing_matches():
    _register()
    r = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Alpha Women",
            "opponent": "Beta Women",
            "category": "Women",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI",
            "scope_mode": "auto",
        },
        follow_redirects=False,
    )
    match_id = int(r.headers["location"].split("/matches/", 1)[1].split("/", 1)[0])
    session = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "0",
            "source_duration_seconds": "2400",
            "playback_rate": "2",
            "parallel_segments": "4",
            "scope_mode": "auto",
        },
    )
    assert session.status_code == 200
    session_id = session.json()["session_id"]

    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        user = match.owner
        root = _capture_session_dir(user, match, session_id)
        state = _read_state(root)
        state["multiple_match_candidates"] = True
        state["match_candidates"] = [
            {"signature": "alpha beta", "label": "ALPHA 0-0 BETA", "first_second": 50.0, "last_second": 900.0, "confidence": 0.7, "target": True},
            {"signature": "gamma delta", "label": "GAMMA 0-0 DELTA", "first_second": 1250.0, "last_second": 2100.0, "confidence": 0.6, "target": False},
        ]
        _write_state(root, state)
    finally:
        db.close()

    r = client.post(
        f"/matches/{match_id}/analysis/browser-capture/finish",
        data={
            "session_id": session_id,
            "source_start_second": "0",
            "source_duration_seconds": "2400",
            "playback_rate": "2",
            "parallel_segments": "4",
            "scope_mode": "auto",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["needs_match_selection"] is True
    assert len(body["match_candidates"]) == 2
    assert "choisis" in body["message"].lower()
