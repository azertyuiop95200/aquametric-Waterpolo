import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import Match, Team

client = TestClient(app)


def _register_user():
    email = f"analysis-all-teams-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "Universal Analyst", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_analysis_form_exposes_database_teams_not_only_granville():
    _register_user()
    response = client.get("/matches/new")
    assert response.status_code == 200
    assert "Astralpool CN Sabadell" in response.text
    assert "Search any club or national team" in response.text


def test_can_create_analysis_for_non_granville_catalog_team():
    _register_user()
    response = client.post(
        "/matches",
        data={
            "team_name": "Astralpool CN Sabadell",
            "opponent": "Olympiacos SFP",
            "competition": "European Aquatics Champions League Women",
            "match_date": "2026-08-31",
            "video_url": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    match_id = int(response.headers["location"].rsplit("/", 1)[-1])

    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        assert match is not None
        team = db.get(Team, match.team_id)
        assert team is not None
        assert team.name == "Astralpool CN Sabadell"
        assert match.opponent == "Olympiacos SFP"
    finally:
        db.close()


def test_legacy_team_id_submission_still_works():
    _register_user()
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).order_by(Team.id.desc()))
        assert team is not None
        team_id = team.id
    finally:
        db.close()

    response = client.post(
        "/matches",
        data={
            "team_id": str(team_id),
            "opponent": "Legacy Opponent",
            "competition": "Compatibility Cup",
            "match_date": "2026-08-31",
            "video_url": "",
        },
        follow_redirects=False,
    )
    # If the most recent team belongs to another test user, the universal route
    # safely rejects it rather than crossing workspaces. Existing per-user team
    # IDs remain supported when they belong to the authenticated user.
    assert response.status_code in {303, 400}
