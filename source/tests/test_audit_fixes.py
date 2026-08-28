import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from db import SessionLocal
from main import app
from models import AutonomousAnalysis, AutonomousEventCandidate, Club, Match, Team, User


def _register(client: TestClient, email: str):
    response = client.post(
        "/register",
        data={"name": "Audit User", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_private_clubs_are_isolated_between_users():
    token = uuid.uuid4().hex[:10]
    club_name = f"Private Club {token}"
    email_a = f"audit-a-{token}@example.com"
    email_b = f"audit-b-{token}@example.com"
    client_a = TestClient(app)
    client_b = TestClient(app)

    _register(client_a, email_a)
    response = client_a.post(
        "/clubs",
        data={"name": club_name, "country": "France", "division": "Audit", "category": "Women"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = SessionLocal()
    try:
        user_a = db.scalar(select(User).where(User.email == email_a))
        private_club = db.scalar(select(Club).where(Club.name == club_name, Club.owner_id == user_a.id))
        assert private_club is not None
        private_club_id = private_club.id
    finally:
        db.close()

    _register(client_b, email_b)
    response = client_b.get("/teams")
    assert response.status_code == 200
    assert club_name not in response.text

    response = client_b.post(
        "/teams",
        data={"name": f"Intruder Team {token}", "club_id": str(private_club_id), "category": "Women"},
        follow_redirects=False,
    )
    assert response.status_code == 400

    # Another user may create their own club with the same real-world label;
    # the first user's private record must not be treated as a global duplicate.
    response = client_b.post(
        "/clubs",
        data={"name": club_name, "country": "France", "division": "Audit", "category": "Women"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = SessionLocal()
    try:
        user_b = db.scalar(select(User).where(User.email == email_b))
        clubs = db.scalars(select(Club).where(Club.name == club_name).order_by(Club.id)).all()
        assert {club.owner_id for club in clubs} == {user_a.id, user_b.id}
        leaked_team = db.scalar(
            select(Team).where(Team.owner_id == user_b.id, Team.club_id == private_club_id)
        )
        assert leaked_team is None
    finally:
        db.close()


def test_report_json_uses_only_latest_autonomous_analysis_candidates():
    token = uuid.uuid4().hex[:10]
    email = f"audit-report-{token}@example.com"
    client = TestClient(app)
    _register(client, email)

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        shared_club = db.scalar(select(Club).where(Club.owner_id.is_(None)).order_by(Club.id))
        assert shared_club is not None
        team = Team(name=f"Report Team {token}", club_id=shared_club.id, owner_id=user.id, category="Women")
        db.add(team)
        db.flush()
        match = Match(
            owner_id=user.id,
            team_id=team.id,
            opponent="Audit Opponent",
            competition="Audit Cup",
            match_date="2026-08-28",
        )
        db.add(match)
        db.flush()

        old_analysis = AutonomousAnalysis(
            match_id=match.id,
            status="complete",
            summary_json='{"goal_candidates": 9}',
        )
        db.add(old_analysis)
        db.flush()
        db.add(
            AutonomousEventCandidate(
                analysis_id=old_analysis.id,
                match_id=match.id,
                second=12.0,
                event_type="goal_candidate",
                confidence_score=0.5,
                confidence_label="MEDIUM",
                summary="stale candidate",
            )
        )

        current_analysis = AutonomousAnalysis(
            match_id=match.id,
            status="complete",
            summary_json='{"goal_candidates": 1}',
        )
        db.add(current_analysis)
        db.flush()
        db.add(
            AutonomousEventCandidate(
                analysis_id=current_analysis.id,
                match_id=match.id,
                second=44.0,
                event_type="goal_candidate",
                confidence_score=0.8,
                confidence_label="HIGH",
                summary="current candidate",
            )
        )
        db.commit()
        match_id = match.id
    finally:
        db.close()

    response = client.get(f"/matches/{match_id}/report.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_quality"]["auto_candidates"] == 1
    assert payload["auto_summary"]["goal_candidates"] == 1
    assert payload["auto_candidates"] == [
        {
            "second": 44.0,
            "event_type": "goal_candidate",
            "confidence": "HIGH",
            "summary": "current candidate",
        }
    ]
