"""Exercise persisted sessions, ownership, validation and concurrent edits."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware
from db import Base, get_db
from models import User, Club, Team, Match
from video_session_routes import router


@pytest.fixture
def workspace():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key='test-only')
    app.include_router(router)
    def database():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = database
    from fastapi import Request
    @app.post('/test-login/{uid}')
    def login(uid: int, request: Request):
        request.session['user_id'] = uid
        return {}
    with Session(engine) as db:
        db.add_all([User(id=i, email=f'{i}@example.com', password_hash='unused') for i in (1, 2)])
        db.add(Club(id=1, owner_id=1, name='Club'))
        db.add(Team(id=1, owner_id=1, club_id=1, name='Équipe'))
        db.add(Match(id=1, owner_id=1, team_id=1, opponent='Adversaire', video_url='https://youtu.be/a5Ja269h5G8'))
        db.add(Match(id=2, owner_id=2, team_id=1, opponent='Privé'))
        db.commit()
    client = TestClient(app)
    client.post('/test-login/1')
    yield client
    engine.dispose()


def payload():
    return {'title': 'Défense', 'objective': 'Fermer le centre', 'items': [
        {'match_id': 1, 'title': 'Premier passage', 'start': 10, 'end': 20, 'note': 'Observer les aides'},
        {'match_id': 1, 'title': 'Second passage', 'start': 30, 'end': 40}]}


def test_save_reload_reorder_export_and_delete(workspace):
    c = workspace
    created = c.post('/api/video-sessions', json=payload())
    assert created.status_code == 201
    row = created.json(); path = f'/api/video-sessions/{row["id"]}'
    read = c.get(path).json()
    assert read['items'][0]['note'] == 'Observer les aides'
    assert read['items'][0]['embed'].startswith('https://www.youtube.com/embed/')
    assert c.get('/api/video-sessions').json()[0]['count'] == 2
    row['items'].reverse()
    updated = c.put(path, json=row)
    assert updated.status_code == 200 and updated.json()['revision'] == 2
    assert c.get(path).json()['items'][0]['title'] == 'Second passage'
    assert c.put(path, json=row).status_code == 409
    exported = c.get(path + '/export')
    assert exported.json()['items'][1]['note'] == 'Observer les aides'
    assert 'attachment' in exported.headers['content-disposition']
    assert c.delete(path).status_code == 204
    assert c.get(path).status_code == 404


def test_owner_and_authentication_boundaries(workspace):
    c = workspace
    row = c.post('/api/video-sessions', json=payload()).json()
    path = f'/api/video-sessions/{row["id"]}'
    c.post('/test-login/2')
    assert c.get('/api/video-sessions').json() == []
    assert c.get(path).status_code == 404
    assert c.get(path + '/export').status_code == 404
    assert c.put(path, json=payload()).status_code == 404
    assert c.delete(path).status_code == 404
    assert c.post('/api/video-sessions', json=payload()).status_code == 404
    c.cookies.clear()
    assert c.get('/api/video-sessions').status_code == 401


@pytest.mark.parametrize('start,end', [(20, 10), (-1, 2), (0, 601), (5, 5)])
def test_invalid_clip_windows(workspace, start, end):
    data = payload(); data['items'][0].update(start=start, end=end)
    assert workspace.post('/api/video-sessions', json=data).status_code == 422


def test_unowned_match_and_empty_title_rejected(workspace):
    data = payload(); data['items'][0]['match_id'] = 2
    assert workspace.post('/api/video-sessions', json=data).status_code == 404
    data = payload(); data['title'] = '  '
    assert workspace.post('/api/video-sessions', json=data).status_code == 422


def test_builder_renders_without_analysis(workspace):
    response = workspace.get('/analysis/video-session-elite?match_id=1')
    assert response.status_code == 200
    assert 'session-builder' in response.text
    assert 'video-session-builder.js' in response.text
