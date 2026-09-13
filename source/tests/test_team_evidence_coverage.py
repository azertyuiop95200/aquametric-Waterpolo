import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from db import SessionLocal
from main import app
from models import ScoutingTeam, PlayerIntelligenceProfile, MatchLibraryItem
from services.player_intelligence import profile_snapshot
from services.team_evidence_coverage import team_evidence_coverage, aliases_for, _match_in_scope


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


def test_national_team_aliases_and_age_group_scope_do_not_mix_senior_and_u20():
    senior = ScoutingTeam(name='Greece — Women Senior', team_type='national_team', country='Greece', age_group='Senior')
    u20 = ScoutingTeam(name='Greece — Women U20', team_type='national_team', country='Greece', age_group='U20')
    senior_match = MatchLibraryItem(external_key='TEST-GRE-SENIOR', title='Greece vs Spain — World Cup', competition="Women's Water Polo World Cup", team_a='Greece', team_b='Spain')
    u20_match = MatchLibraryItem(external_key='TEST-GRE-U20', title='Greece vs Spain — Women U20', competition="Women's U20 World Championships", team_a='Greece', team_b='Spain')
    assert 'Greece' in aliases_for(senior)
    assert 'GRE' in aliases_for(senior)
    assert _match_in_scope(senior, senior_match) is True
    assert _match_in_scope(senior, u20_match) is False
    assert _match_in_scope(u20, senior_match) is False
    assert _match_in_scope(u20, u20_match) is True


def test_u20_world_aquatics_library_is_visible_to_each_relevant_team():
    db = SessionLocal()
    try:
        by_name = {r['team'].name:r for r in team_evidence_coverage(db)}
        for name in ('Spain — Women U20', 'Greece — Women U20', 'United States — Women U20', 'Italy — Women U20', 'Croatia — Women U20', 'Brazil — Women U20'):
            row = by_name[name]
            assert row['documented_matches'] > 0, name
            assert row['performance_matches'] > 0, name
            assert row['performance_players'] > 0, name
            assert row['state'] == 'performance_stats', name
            assert '2025' in row['evidence_seasons'], name
    finally:
        db.close()


def test_benchmark_does_not_duplicate_canonical_spain_greece_u20_semifinal():
    db = SessionLocal()
    try:
        rows = db.scalars(select(MatchLibraryItem).where(
            MatchLibraryItem.team_a == 'Spain',
            MatchLibraryItem.team_b == 'Greece',
            MatchLibraryItem.score_a == 11,
            MatchLibraryItem.score_b == 9,
            MatchLibraryItem.season == '2025',
        )).all()
        assert len(rows) == 1
        assert rows[0].external_key == 'WA-U20W-2025-SF-ESP-GRE'
    finally:
        db.close()


def test_evidence_coverage_dashboard_and_api_require_login_then_render():
    anonymous = TestClient(app)
    denied = anonymous.get('/evidence-coverage', follow_redirects=False)
    # The application-wide 401 handler redirects browser users to login. The key
    # security property is that protected coverage content is not returned directly.
    assert denied.status_code in (302, 303, 307, 401)
    if denied.status_code != 401:
        assert '/login' in denied.headers.get('location', '')

    client = TestClient(app)
    client.cookies.clear()
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
    granville = next(row for row in data['teams'] if row['name'] == 'Granville Water Polo')
    assert granville['season'] == '2026-2027'
    assert granville['age_group'] == 'Senior'
    assert granville['evidence_seasons'] == ['2025-2026']
