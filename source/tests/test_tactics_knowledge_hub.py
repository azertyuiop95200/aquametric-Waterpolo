from fastapi.testclient import TestClient
from main import app


def test_tactics_knowledge_hub_is_served():
    client = TestClient(app)
    response = client.get('/knowledge')
    assert response.status_code == 200
    body = response.text
    assert 'Tactique &amp; Connaissance' in body or 'Tactique & Connaissance' in body
    assert 'Séance vidéo coach' in body
    assert 'M-zone · 8 images de rotation' in body
    assert 'Créer une entrée centre · 6 images' in body
    assert '3v2 · 6 images' in body
    assert '6v5 puis 5v6 · 10 images' in body
    assert 'Stop avant décision' in body
    assert 'VIDEO → ARRÊT → LECTURE → CORRECTION → PISCINE' in body
