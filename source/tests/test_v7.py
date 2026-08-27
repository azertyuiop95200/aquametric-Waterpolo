import os
os.environ.setdefault('DATABASE_URL','sqlite:///./test_v7.db')
from fastapi.testclient import TestClient
from main import app
from db import SessionLocal
from models import TrainingSession, OfficialFixture, ScoutingTeam, ScoutingPlayer, RosterUpdateRequest
from sqlalchemy import select

client=TestClient(app)

def login_user(email='v7@example.com'):
    client.post('/register',data={'email':email,'password':'password123','name':'V7'})
    r=client.post('/login',data={'email':email,'password':'password123'},follow_redirects=False)
    assert r.status_code in (302,303)

def test_granville_2026_27_training_has_monday_and_seven_slots():
    login_user('trainingv7@example.com')
    r=client.get('/my-team')
    assert r.status_code==200
    assert 'Monday' in r.text and '18:55' in r.text and '21:15' in r.text
    assert 'Thursday' in r.text and '06:40' in r.text
    with SessionLocal() as db:
        slots=db.scalars(select(TrainingSession).where(TrainingSession.source_season=='2026-2027')).all()
        assert len(slots) >= 7 and len(slots) % 7 == 0
        assert any(s.weekday=='Monday' and s.start_time=='18:55' for s in slots)

def test_granville_ffn_elite_calendar_has_18_exact_fixtures():
    login_user('calv7@example.com')
    client.get('/my-team')
    with SessionLocal() as db:
        fixtures=db.scalars(select(OfficialFixture).where(OfficialFixture.season=='2026-2027',OfficialFixture.competition=='Elite Féminine').order_by(OfficialFixture.start_text)).all()
        assert len(fixtures)==18
        assert fixtures[0].start_text=='2026-09-12 20:00'
        assert fixtures[0].home_team=='Lille UC Métropole Water-Polo'
        assert fixtures[0].away_team=='Granville Waterpolo'
        assert fixtures[-1].start_text=='2027-04-24 20:00'
        assert fixtures[-1].away_team=='Grand Nancy Aquatique Club'

def test_scouting_and_granville_historical_roster_are_explicitly_labelled():
    login_user('scoutv7@example.com')
    r=client.get('/scouting')
    assert r.status_code==200
    assert 'Lille UC Métropole' in r.text
    assert 'historical roster pending 2026 27 confirmation' in r.text.lower()
    with SessionLocal() as db:
        g=db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key=='club-fr-granville-w-elite'))
        assert g is not None
        players=db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id==g.id)).all()
        assert len(players)>=12
        assert any(p.name=='Rumina Edgerton' for p in players)

def test_scouting_detail_and_request_queue():
    login_user('reqv7@example.com')
    with SessionLocal() as db:
        lille=db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key=='club-fr-lille-uc-w-elite'))
        tid=lille.id
    d=client.get(f'/scouting/{tid}')
    assert d.status_code==200 and 'Eszter Lefebvre' in d.text
    r=client.post('/scouting/request',data={'request_type':'team','query':'Olympic Nice women roster 2026-27','source_hint':'FFN'},follow_redirects=False)
    assert r.status_code in (302,303)
    with SessionLocal() as db:
        q=db.scalar(select(RosterUpdateRequest).where(RosterUpdateRequest.query=='Olympic Nice women roster 2026-27'))
        assert q is not None and q.status=='queued'

def test_national_team_hub_separates_senior_and_u20():
    login_user('natv7@example.com')
    r=client.get('/national-teams')
    assert r.status_code==200
    assert 'France — Women Senior' in r.text
    assert 'United States — Women U20' in r.text
    assert 'World U20 preparation pool' in r.text
