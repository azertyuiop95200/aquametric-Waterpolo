import os, uuid
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_full_product_flow():
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post('/register', data={'name':'Coach Test','email':email,'password':'password123'}, follow_redirects=False)
    assert r.status_code == 303
    r = client.get('/teams')
    assert r.status_code == 200
    assert 'Granville Water Polo' in r.text
    r = client.post('/teams', data={'name':'Test Squad','club_id':'1','category':'Women'}, follow_redirects=False)
    assert r.status_code == 303
    r = client.get('/teams')
    assert 'Test Squad' in r.text
    from db import SessionLocal
    from models import Team, Match
    from sqlalchemy import select
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name=='Test Squad').order_by(Team.id.desc()))
        assert team is not None
        team_id = team.id
    finally:
        db.close()
    r = client.post(f'/teams/{team_id}/players', data={'name':'Player 7','cap_number':'7'}, follow_redirects=False)
    assert r.status_code == 303
    r = client.post('/matches', data={'team_id':str(team_id),'opponent':'Opponent','competition':'Test Cup','match_date':'2026-08-26','video_url':''}, follow_redirects=False)
    assert r.status_code == 303
    location = r.headers['location']
    assert location.startswith('/matches/')
    match_id = int(location.rsplit('/',1)[-1])
    from models import Player
    db = SessionLocal()
    try:
        player = db.scalar(select(Player).where(Player.team_id==team_id, Player.name=='Player 7'))
        assert player is not None
        pid = player.id
    finally:
        db.close()
    r = client.post(f'/matches/{match_id}/events', data={'event_type':'goal','second':'62.5','player_id':str(pid),'note':'verified'}, follow_redirects=False)
    assert r.status_code == 303
    r = client.get(f'/matches/{match_id}')
    assert r.status_code == 200
    assert 'Player 7' in r.text
    assert 'rating-v2' in r.text
    assert 'Match evaluation /100' in r.text
    assert 'Attack' in r.text and 'Defence' in r.text and 'Decision' in r.text
