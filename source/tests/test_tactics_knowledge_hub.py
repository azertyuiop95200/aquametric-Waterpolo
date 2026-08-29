from fastapi.testclient import TestClient
from main import app


def test_tactics_knowledge_hub_is_served():
    client = TestClient(app)
    response = client.get('/knowledge')
    assert response.status_code == 200
    body = response.text
    assert 'Tactique &amp; Connaissance' in body or 'Tactique & Connaissance' in body
    assert 'M-zone : 6 schémas de rotation' in body
    assert 'Contre-attaque 3v2 : 6 schémas' in body
    assert '6v5 : 4-2 vers 3-3 en 5 schémas' in body
    assert 'STOP AVANT LA DÉCISION' in body
