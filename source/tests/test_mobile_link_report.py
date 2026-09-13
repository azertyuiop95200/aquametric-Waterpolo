import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select
from main import app
from db import SessionLocal
from models import Match, Event
from services.analysis_product import analysis_snapshot


def registered():
    client = TestClient(app)
    result = client.post('/register', data={'name':'Mobile test', 'email':f'mobile-{uuid.uuid4().hex}@example.com','password':'TestMobile123!'}, follow_redirects=False)
    assert result.status_code == 303
    return client


def create(client, device='phone', url='https://example.com/match-test'):
    return client.post('/analysis/url/create', data={'team_name':'Équipe mobile test', 'opponent':'Adversaire test', 'category':'Men','video_url':url,'input_device':device}, follow_redirects=False)


def test_phone_link_saves_without_desktop_capture_and_reopens():
    client = registered()
    response = create(client)
    assert response.status_code == 303
    target = response.headers['location']
    assert target.endswith('/analysis/result') and 'browser-capture' not in target
    match_id = int(target.split('/')[2])
    page = client.get(target)
    assert page.status_code == 200
    assert 'Vidéo identifiée mais non analysée' in page.text
    assert 'mobileLinkSaved' in page.text
    with SessionLocal() as db:
        match = db.get(Match, match_id)
        assert match.status == 'source_link_saved' and match.video_url == 'https://example.com/match-test'
        assert len(match.events) == 0
    export = client.get(f'/matches/{match_id}/analysis/report.html')
    assert export.status_code == 200
    assert 'attachment' in export.headers['content-disposition']
    assert 'Non mesuré' in export.text
    assert 'Vidéo identifiée mais non analysée' in export.text
    assert registered().get(f'/matches/{match_id}/analysis/report.html').status_code == 404
    assert 'Équipe mobile test' in client.get('/analysis-library').text


def test_desktop_capture_and_invalid_input():
    client = registered()
    assert '/analysis/browser-capture?' in create(client, 'desktop').headers['location']
    assert create(client, 'phone', 'javascript:alert(1)').status_code == 400
    assert create(client, 'unsupported').status_code == 400


def test_unverified_events_are_not_reported_as_confirmed():
    client = registered()
    match_id = int(create(client).headers['location'].split('/')[2])
    with SessionLocal() as db:
        db.add_all([Event(match_id=match_id,second=10,event_type='goal',confidence='CANDIDATE'),
                    Event(match_id=match_id,second=20,event_type='save',confidence='CONFIRMED',note='<script>bad()</script>')])
        db.commit()
        snapshot = analysis_snapshot(db, db.get(Match,match_id))
        assert [e['event_type'] for e in snapshot['verified_events']] == ['save']
    export = client.get(f'/matches/{match_id}/analysis/report.html')
    assert '<script>bad()</script>' not in export.text
    assert '&lt;script&gt;' in export.text
