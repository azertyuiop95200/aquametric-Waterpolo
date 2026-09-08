import uuid
from fastapi.testclient import TestClient
from main import app
from services.simulation import absence_availability, simulate_matchup


def test_absence_deduplication_and_server_calculation():
    profile = {'roster_players': [{'name': 'Émilie Test', 'impact': 4}]}
    assert absence_availability(profile, []) == 100
    assert absence_availability(profile, ['Émilie Test', 'emilie test']) == 88
    assert absence_availability(profile, ['Inconnue']) == 95


def test_optional_plan_does_not_change_automatic_default():
    auto = simulate_matchup('Granville Water Polo', 'Lille UC Métropole Water-Polo', n=1000)
    scenario = simulate_matchup('Granville Water Polo', 'Lille UC Métropole Water-Polo', n=1000, scenario_a='defence_first')
    assert scenario['tactic_a'] == 'defence_first'
    assert auto['auto_inputs']['availability_a'] == scenario['auto_inputs']['availability_a'] == 100


def test_dashboard_and_named_absences_round_trip():
    client = TestClient(app)
    response = client.post('/register', data={'email': f'refonte-{uuid.uuid4().hex}@example.com', 'password': 'ValidPass123!', 'name': 'Coach'}, follow_redirects=False)
    assert response.status_code == 303
    dashboard = client.get('/dashboard')
    assert dashboard.status_code == 200
    assert 'Reprendre une analyse' in dashboard.text
    assert 'elite-analyst.js' not in dashboard.text
    assert '/static/workspace.css' in dashboard.text
    assert 'content-encoding' in dashboard.headers
    projection = client.get('/simulation?absences_a=Joueuse+absente&availability_a=100')
    assert projection.status_code == 200
    assert '95%' in projection.text
