import os
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from db import SessionLocal
from main import app
from models import AnalysisJob, AutonomousAnalysis, Club, Match, Team, User, VisionAnalysis

ROOT = Path(__file__).resolve().parents[1]


def _register(client, email):
    r = client.post('/register', data={'name':'V122 User','email':email,'password':'password123'}, follow_redirects=False)
    assert r.status_code == 303


def test_v122_templates_expose_visual_tactics_player_links_and_five_languages():
    knowledge = (ROOT / 'templates' / 'knowledge.html').read_text(encoding='utf-8')
    scouting = (ROOT / 'templates' / 'scouting_detail.html').read_text(encoding='utf-8')
    base = (ROOT / 'templates' / 'base.html').read_text(encoding='utf-8')
    locale_pack = (ROOT / 'static' / 'i18n-v122-locales.js').read_text(encoding='utf-8')
    assert knowledge.count("board('") >= 9
    assert 'tactic-board-card' in knowledge
    assert 'source-row' not in knowledge and 'reference-row' not in knowledge
    assert '/intelligence/player?name=' in scouting
    assert 'scout-player-card' in scouting
    assert base.count('data-lang-choice=') == 5
    assert '/analysis-history' in base
    assert 'i18n-v122-locales.js?v=' in base
    for marker in ('Historique analyses', 'Storico analisi', 'Historial de análisis', 'История анализов'):
        assert marker in locale_pack


def test_v122_analysis_history_keeps_multiple_runs_for_same_match():
    token = uuid.uuid4().hex[:10]
    email = f'v122-history-{token}@example.com'
    client = TestClient(app)
    _register(client, email)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        club = db.scalar(select(Club).where(Club.owner_id.is_(None)).order_by(Club.id))
        assert user and club
        team = Team(name=f'History Team {token}', club_id=club.id, owner_id=user.id, category='Women')
        db.add(team); db.flush()
        match = Match(owner_id=user.id, team_id=team.id, opponent='History Opponent', competition='History Cup', match_date='2026-08-28')
        db.add(match); db.flush()
        db.add_all([
            AnalysisJob(match_id=match.id, stage='baseline', progress=100, status='complete', message='HISTORY-LEGACY-RUN'),
            VisionAnalysis(match_id=match.id, status='complete', engine_version='vision-v122-a', sample_count=12, confidence='MEDIUM'),
            VisionAnalysis(match_id=match.id, status='complete', engine_version='vision-v122-b', sample_count=24, confidence='HIGH'),
            AutonomousAnalysis(match_id=match.id, status='complete', engine_version='auto-v122-a'),
            AutonomousAnalysis(match_id=match.id, status='complete', engine_version='auto-v122-b'),
        ])
        db.commit()
    finally:
        db.close()
    r = client.get('/analysis-history')
    assert r.status_code == 200
    assert 'HISTORY-LEGACY-RUN' in r.text
    assert 'vision-v122-a' in r.text and 'vision-v122-b' in r.text
    assert 'auto-v122-a' in r.text and 'auto-v122-b' in r.text


def test_v122_case_insensitive_player_resolver_and_enriched_cecilia_profile():
    token = uuid.uuid4().hex[:10]
    client = TestClient(app)
    _register(client, f'v122-profile-{token}@example.com')
    r = client.get('/intelligence/player?name=cecilia%20nardini', follow_redirects=False)
    assert r.status_code == 303
    assert '/profiles/players/' in r.headers['location']
    profile = client.get(r.headers['location'])
    assert profile.status_code == 200
    assert 'career-panel' in profile.text
    assert 'Rapallo Pallanuoto' in profile.text
    assert '7 buts en finale du championnat 2026' in profile.text
    assert 'Championne de France Elite' in profile.text


def test_v122_team_discovery_is_broad_and_knowledge_route_is_visual():
    token = uuid.uuid4().hex[:10]
    client = TestClient(app)
    _register(client, f'v122-teams-{token}@example.com')
    scouting = client.get('/scouting?kind=all')
    assert scouting.status_code == 200
    for team in ('Granville', 'Lille', 'Bordeaux', 'Nice', 'Taverny', 'Marseille'):
        assert team in scouting.text
    knowledge = client.get('/knowledge')
    assert knowledge.status_code == 200
    assert knowledge.text.count('tactic-board-card') >= 9
    assert 'RULE AUTHORITY' not in knowledge.text
