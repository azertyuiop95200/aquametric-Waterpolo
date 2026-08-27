import os
os.environ.setdefault('DATABASE_URL','sqlite:///./test_v10.db')
from fastapi.testclient import TestClient
from sqlalchemy import select
from main import app
from db import SessionLocal
from models import PlayerIntelligenceProfile, PlayerMatchMetric, FranceSquadMembership
from services.france_intelligence import WA_2025_REPORT

client=TestClient(app)

def login_user(email='v10@example.com'):
    client.post('/register',data={'email':email,'password':'password123','name':'V10'})
    r=client.post('/login',data={'email':email,'password':'password123'},follow_redirects=False)
    assert r.status_code in (302,303)

def test_france_five_year_intelligence_and_official_metrics():
    login_user('france-v10@example.com')
    r=client.get('/france-intelligence')
    assert r.status_code==200
    assert '2022' in r.text and '2026' in r.text
    assert 'Ema Vernoux' in r.text
    assert 'key passes' in r.text.lower() and 'centre touches' in r.text.lower()
    with SessionLocal() as db:
        ema=db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name=='Ema Vernoux'))
        metric=db.scalar(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id==ema.id, PlayerMatchMetric.metric=='tournament_goals', PlayerMatchMetric.source_url==WA_2025_REPORT))
        assert metric is not None and metric.value==15
        f2026=db.scalar(select(FranceSquadMembership).where(FranceSquadMembership.profile_id==ema.id,FranceSquadMembership.year==2026))
        assert f2026 is not None and f2026.roster_kind=='official'

def test_tactical_chess_is_conditional_not_guaranteed():
    login_user('chess-v10@example.com')
    r=client.get('/tactical-chess?defence=drop_2_4')
    assert r.status_code==200
    text=r.text.lower()
    assert '2–4' in r.text or '2-4' in r.text
    assert 'decision tree' in text
    assert 'video facts required' in text
    assert 'not a guaranteed' in text

def test_simulation_route_reports_uncertainty():
    login_user('sim-v10@example.com')
    r=client.get('/simulation?team_a=Granville%20Water%20Polo&team_b=France%20%E2%80%94%20Women%20Senior&tactic_a=centre_pressure&tactic_b=defence_first')
    assert r.status_code==200
    text=r.text.lower()
    assert 'exploratory' in text
    assert 'not a betting model' in text
    assert 'coverage' in text
    assert 'granville water polo' in text

def test_player_dossier_has_advanced_metrics_and_empty_maps_when_unobserved():
    login_user('maps-v10@example.com')
    with SessionLocal() as db:
        p=db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name=='Ema Vernoux'))
        pid=p.id
    r=client.get(f'/player-intelligence/{pid}')
    assert r.status_code==200
    assert 'Pool shot origin' in r.text
    assert 'Goal target map' in r.text
    assert 'No shot-location observations yet' in r.text
    assert 'action created' in r.text.lower()

def test_advanced_event_summary_does_not_double_count_off_target_shot():
    from types import SimpleNamespace
    from services.advanced_metrics import event_metric_summary
    events=[SimpleNamespace(player_id=7,event_type='shot_off_target'),SimpleNamespace(player_id=7,event_type='key_pass'),SimpleNamespace(player_id=7,event_type='duel_won')]
    s=event_metric_summary(events,7)
    assert s['shots']==1
    assert s['shots_off_target']==1 and s['key_passes']==1 and s['duels_won']==1
