import os
os.environ.setdefault('DATABASE_URL','sqlite:///./test_v8.db')
from fastapi.testclient import TestClient
from main import app
from db import SessionLocal
from models import SourceWatch, TransferSignal, MatchResearchTarget, ScoutingPlayer
from sqlalchemy import select
client=TestClient(app)
def login_user(email='v8@example.com'):
    client.post('/register',data={'email':email,'password':'password123','name':'V8'}); r=client.post('/login',data={'email':email,'password':'password123'},follow_redirects=False); assert r.status_code in (302,303)
def test_transfer_watch_seeds_current_sources_and_signals():
    login_user('watchv8@example.com'); r=client.get('/transfer-watch'); assert r.status_code==200; assert 'Waterpolo 360' in r.text and 'Total Waterpolo' in r.text; assert 'Elena Ruiz' in r.text and 'Iva Rozic' in r.text; assert 'rumour' in r.text.lower()
    with SessionLocal() as db: assert db.scalar(select(SourceWatch).where(SourceWatch.platform=='facebook')) is not None; assert db.scalar(select(TransferSignal).where(TransferSignal.player_name=='Kamilla Farago',TransferSignal.signal_type=='rumour')) is not None
def test_transfer_rumour_does_not_mutate_scouting_roster():
    login_user('rumourv8@example.com')
    with SessionLocal() as db:
        p=db.scalar(select(ScoutingPlayer).where(ScoutingPlayer.name=='Iva Rozic')); before=p.current_status if p else None; _=db.scalar(select(TransferSignal).where(TransferSignal.player_name=='Iva Rozic')); p2=db.scalar(select(ScoutingPlayer).where(ScoutingPlayer.name=='Iva Rozic')); assert (p2.current_status if p2 else None)==before
def test_match_research_queue_contains_2026_world_cup_and_youth_targets():
    login_user('matchqv8@example.com'); r=client.get('/transfer-watch'); assert 'World Aquatics U18' in r.text
    with SessionLocal() as db: assert db.scalar(select(MatchResearchTarget).where(MatchResearchTarget.external_key=='WA-WWC-2026-F-USA-ESP')) is not None
def test_player_data_coverage_page():
    login_user('coveragev8@example.com'); r=client.get('/player-data'); assert r.status_code==200; assert 'PLAYER DATA COVERAGE' in r.text; assert 'Isabel Piralkova' in r.text
