import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from db import SessionLocal
from main import app
from models import ScoutingTeam, PlayerIntelligenceProfile
from services.player_intelligence import profile_snapshot
from services.team_evidence_coverage import team_evidence_coverage


FRENCH_ELITE = {
    "Lille UC Métropole Water-Polo",
    "Union St-Bruno Bordeaux",
    "Olympic Nice Natation",
    "Grand Nancy Aquatique Club",
    "Toulon Waterpolo",
    "Taverny Sports Nautiques 95",
    "Sporting Club des Nageurs de Choisy le Roi",
}


def _register(client):
    email = f"coverage-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post('/register', data={'name':'Coverage Audit','email':email,'password':'password123'}, follow_redirects=False)
    assert r.status_code == 303


def test_every_scouting_team_is_present_in_evidence_inventory():
    db = SessionLocal()
    try:
        rows = team_evidence_coverage(db)
        tracked = db.scalars(select(ScoutingTeam)).all()
        assert len(rows) == len(tracked)
        names = {r['team'].name for r in rows}
        assert FRENCH_ELITE <= names
        assert 'Granville Water Polo' in names
        assert 'France — Women Senior' in names
        assert 'Spain — Women Senior' in names
        assert 'United States — Women Senior' in names
    finally:
        db.close()


def test_french_elite_teams_have_performance_evidence_state():
    db = SessionLocal()
    try:
        by_name = {r['team'].name:r for r in team_evidence_coverage(db)}
        for name in FRENCH_ELITE:
            row = by_name[name]
            assert row['documented_matches'] > 0, name
            assert row['performance_matches'] > 0, name
            assert row['performance_players'] > 0, name
            assert row['state'] == 'performance_stats', name
    finally:
        db.close()


def test_granville_is_lineup_evidence_not_fake_performance_stats():
    db = SessionLocal()
    try:
        row = next(r for r in team_evidence_coverage(db) if r['team'].name == 'Granville Water Polo')
        assert row['documented_matches'] == 12
        assert row['lineup_only_matches'] == 12
        assert row['performance_matches'] == 0
        assert row['state'] == 'official_lineups'
    finally:
        db.close()


def test_profile_snapshot_separates_documented_appearances_from_stat_matches():
    db = SessionLocal()
    try:
        rumina = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == 'Rumina Edgerton'))
        assert rumina is not None
        snap = profile_snapshot(db, rumina)
        assert snap['documented_matches'] == 11
        assert snap['matches'] == 0
        assert snap['goals'] == 0
        assert snap['saves'] == 0
    finally:
        db.close()


def test_evidence_coverage_dashboard_and_api_require_login_then_render():
    anonymous = TestClient(app)
    assert anonymous.get('/evidence-coverage').status_code == 401
    client = TestClient(app)
    _register(client)
    page = client.get('/evidence-coverage')
    assert page.status_code == 200
    assert 'Evidence coverage' in page.text
    assert 'Lille UC Métropole Water-Polo' in page.text
    assert 'Granville Water Polo' in page.text
    payload = client.get('/api/evidence-coverage')
    assert payload.status_code == 200
    data = payload.json()
    assert data['totals']['teams'] >= 10
    assert any(row['name'] == 'Olympic Nice Natation' and row['performance_matches'] > 0 for row in data['teams'])
