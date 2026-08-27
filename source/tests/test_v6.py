import os
os.environ.setdefault('DATABASE_URL','sqlite:///./test_v6.db')
from fastapi.testclient import TestClient
from main import app

client=TestClient(app)

def login_user(email='v6@example.com'):
    client.post('/register',data={'email':email,'password':'password123','name':'V6'})
    r=client.post('/login',data={'email':email,'password':'password123'},follow_redirects=False)
    assert r.status_code in (302,303)

def test_my_team_hub_and_granville_data():
    login_user('teamv6@example.com')
    r=client.get('/my-team')
    assert r.status_code==200
    assert 'Granville Water Polo' in r.text
    assert 'Vice-champion' in r.text
    assert 'Elite women weekly plan' in r.text
    assert '18 match regular season' in r.text

def test_analysis_library_and_match_tabs():
    login_user('libv6@example.com')
    r=client.get('/analysis-library')
    assert r.status_code==200
    assert 'Spain' in r.text and 'Greece' in r.text
    # find first detail id from known seeded DB by hyperlink
    import re
    m=re.search(r'/analysis-library/(\d+)',r.text)
    assert m
    d=client.get(m.group(0))
    assert d.status_code==200
    assert 'Player stats' in d.text
    assert 'Tactical notes' in d.text
    assert 'Official report' in d.text
