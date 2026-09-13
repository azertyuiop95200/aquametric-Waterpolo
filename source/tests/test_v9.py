import os
os.environ.setdefault('DATABASE_URL','sqlite:///./test_v9.db')
from fastapi.testclient import TestClient
from sqlalchemy import select
from main import app
from db import SessionLocal
from models import PlayerIntelligenceProfile, PlayerSourceRecord, PlayerMatchMetric, MatchLibraryItem, RosterUpdateRequest

client=TestClient(app)

def login_user(email='v9@example.com'):
    client.post('/register',data={'email':email,'password':'password123','name':'V9'})
    r=client.post('/login',data={'email':email,'password':'password123'},follow_redirects=False)
    assert r.status_code in (302,303)

def test_player_intelligence_registry_and_profiles_seed():
    login_user('intel-v9@example.com')
    r=client.get('/player-intelligence')
    assert r.status_code==200
    assert 'PLAYER INTELLIGENCE' in r.text
    assert 'Emily Ausmus' in r.text and 'Elena Ruiz' in r.text and 'Rumina Edgerton' in r.text
    with SessionLocal() as db:
        assert db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name=='Emily Ausmus')) is not None
        assert db.scalar(select(PlayerSourceRecord).join(PlayerIntelligenceProfile, PlayerSourceRecord.profile_id==PlayerIntelligenceProfile.id).where(PlayerIntelligenceProfile.canonical_name=='Elena Ruiz')) is not None

def test_world_cup_final_is_linked_to_player_metrics():
    login_user('metrics-v9@example.com')
    with SessionLocal() as db:
        emily=db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name=='Emily Ausmus'))
        final=db.scalar(select(MatchLibraryItem).where(MatchLibraryItem.external_key=='WA-WWC-2026-F-USA-ESP'))
        goals=db.scalar(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id==emily.id,PlayerMatchMetric.library_match_id==final.id,PlayerMatchMetric.metric=='goals'))
        assert goals is not None and goals.value==6
        pid=emily.id
    r=client.get(f'/player-intelligence/{pid}')
    assert r.status_code==200
    assert '13–9' in r.text and 'tournament goals' in r.text.lower()

def test_granville_profile_is_honest_about_current_season():
    login_user('granville-v9@example.com')
    with SessionLocal() as db:
        rumina=db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name=='Rumina Edgerton'))
        assert rumina.roster_status=='historical_club_confirmed_pending_2627'
        pid=rumina.id
    r=client.get(f'/player-intelligence/{pid}')
    assert 'no match-level stats yet' in r.text.lower()
    assert '2025-2026' in r.text

def test_player_research_request_queue():
    login_user('request-v9@example.com')
    r=client.post('/player-intelligence/request',data={'query':'Lille goalkeeper 2026-27','source_hint':'club Instagram'},follow_redirects=False)
    assert r.status_code in (302,303)
    with SessionLocal() as db:
        q=db.scalar(select(RosterUpdateRequest).where(RosterUpdateRequest.query=='Lille goalkeeper 2026-27'))
        assert q is not None and q.request_type=='player_intelligence'
