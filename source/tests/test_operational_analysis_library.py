import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import User, Club, Team, Player, Match, Event, MatchLibraryItem
from services.match_statistics import build_match_statistics

client = TestClient(app)


def _workspace_match():
    email = f"operational-library-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "Video Analyst", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        club = Club(name=f"Analysis Club {uuid.uuid4().hex[:6]}", country="France", division="Test", category="Women", owner_id=user.id)
        db.add(club); db.flush()
        team = Team(name="Analysis Test Women", club_id=club.id, owner_id=user.id, category="Women")
        db.add(team); db.flush()
        player = Player(team_id=team.id, name="Test Shooter", cap_number=7, primary_role="perimeter")
        db.add(player); db.flush()
        match = Match(owner_id=user.id, team_id=team.id, opponent="Test Opponent", competition="Test Cup", match_date="2026-08-31")
        db.add(match); db.flush()
        db.add_all([
            Event(match_id=match.id, player_id=player.id, second=40, event_type="goal", confidence="CONFIRMED", source="manual"),
            Event(match_id=match.id, player_id=player.id, second=80, event_type="shot_off_target", confidence="CONFIRMED", source="manual"),
            Event(match_id=match.id, player_id=player.id, second=90, event_type="assist", confidence="CONFIRMED", source="manual"),
            Event(match_id=match.id, player_id=player.id, second=100, event_type="duel_won", confidence="CONFIRMED", source="manual"),
        ])
        db.commit()
        return match.id
    finally:
        db.close()


def test_full_match_statistics_are_evidence_aware_and_derived():
    match_id = _workspace_match()
    db = SessionLocal()
    try:
        match = db.get(Match, match_id)
        stats = build_match_statistics(match)
        assert stats["for"]["goals"] == 1
        assert stats["for"]["shots"] == 2
        assert stats["for"]["shot_efficiency"] == 50.0
        assert stats["for"]["assists"] == 1
        assert stats["for"]["duel_win_rate"] == 100.0
        assert "restart_time" not in stats["for"]  # unavailable must not become a fake zero
        assert stats["coverage"]["confirmed_rows"] == 4
    finally:
        db.close()


def test_analysis_library_is_operational_not_reference_demo_only():
    match_id = _workspace_match()
    page = client.get("/analysis-library")
    assert page.status_code == 200
    assert "Bibliothèque d'analyse opérationnelle" in page.text
    assert "Mes matchs analysés" in page.text
    assert f'/match-analysis/{match_id}' in page.text
    assert "Analyse réelle, pas vitrine démo" in page.text

    workspace = client.get(f"/match-analysis/{match_id}")
    assert workspace.status_code == 200
    assert "RAPID LONG-VIDEO PIPELINE" in workspace.text
    assert "Passes décisives" in workspace.text
    assert "Ballons touchés en pointe" in workspace.text
    assert "Supériorité / infériorité" in workspace.text
    assert "Gardienne" in workspace.text
    assert "Une case vide signifie" in workspace.text


def test_rapid_run_requires_owned_uploaded_video():
    match_id = _workspace_match()
    response = client.post(f"/match-analysis/{match_id}/rapid-run", data={}, follow_redirects=False)
    assert response.status_code == 400
    assert "vidéo détenue et téléversée" in response.text


def test_reference_detail_exposes_all_supported_official_player_columns():
    _workspace_match()
    db = SessionLocal()
    try:
        item = db.scalar(select(MatchLibraryItem).order_by(MatchLibraryItem.id))
        assert item is not None
        item_id = item.id
    finally:
        db.close()
    page = client.get(f"/analysis-library/{item_id}")
    assert page.status_code == 200
    for label in ("Buts", "Tirs", "% tir", "Assists", "Steals", "Exclusions", "Arrêts", "Qualité source"):
        assert label in page.text
