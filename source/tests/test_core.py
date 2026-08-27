import os
os.environ["DATABASE_URL"]="sqlite:///./test_aquametric.db"
from fastapi.testclient import TestClient
from main import app
client=TestClient(app)

def test_health():
    r=client.get('/health')
    assert r.status_code==200
    assert r.json()['ok'] is True

def test_home():
    r=client.get('/')
    assert r.status_code==200
    assert 'WATER POLO INTELLIGENCE' in r.text
