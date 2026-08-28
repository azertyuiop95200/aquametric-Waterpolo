import os
import uuid
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import Club, Team, OfficialDataSource
from services.official_data import parse_rfen_fixtures, parse_rfen_standings, parse_rfen_team_stats


def _register(client):
    email=f"v4-{uuid.uuid4().hex[:8]}@example.com"
    r=client.post('/register', data={'name':'V4','email':email,'password':'password123'}, follow_redirects=False)
    assert r.status_code==303


def _demo_club():
    db=SessionLocal()
    try:
        return db.scalar(select(Club).where(Club.name=='Granville Water Polo')).id
    finally:
        db.close()


def test_rfen_result_parser_extracts_score_and_metadata():
    html='''<html><body><h1>25/26 División de Honor Femenina</h1>
    <a>Jornada 22 16/05/2026 17:00 Finalizado</a>
    <a>U.e. Horta</a><span>10</span><span>1</span><span>1</span><span>2</span><span>6</span>
    <a>C.d. Waterpolo Iruña 98 02</a><span>14</span><span>4</span><span>4</span><span>3</span><span>3</span>
    </body></html>'''
    rows=parse_rfen_fixtures(html, 'https://rfen.es/example', '25/26 División de Honor Femenina')
    assert len(rows)==1
    assert rows[0]['home_team']=='U.e. Horta'
    assert rows[0]['away_team']=='C.d. Waterpolo Iruña 98 02'
    assert rows[0]['home_score']==10 and rows[0]['away_score']==14
    assert rows[0]['category']=='Women'


def test_rfen_standings_parser_extracts_table():
    html='''<html><body><div>Posición</div><div>Nombre</div><div>P</div><div>PJ</div><div>PG</div><div>PP</div><div>PGP</div><div>PPP</div><div>GF</div><div>GC</div><div>DG</div>
    <div>1</div><div>C.N. SANT ANDREU</div><div>65</div><div>22</div><div>21</div><div>0</div><div>1</div><div>0</div><div>408</div><div>165</div><div>243</div>
    <div>2</div><div>Assolim C.N. MATARÓ</div><div>58</div><div>22</div><div>19</div><div>2</div><div>0</div><div>1</div><div>357</div><div>191</div><div>166</div>
    </body></html>'''
    rows=parse_rfen_standings(html, 'https://rfen.es/standing', '25/26 División de Honor Femenina')
    assert len(rows)==2
    assert rows[0]['position']==1 and rows[0]['points']==65 and rows[0]['goal_diff']==243
    assert rows[1]['team_name']=='Assolim C.N. MATARÓ'



def test_rfen_team_stats_parser_extracts_metrics():
    html='''<html><body><div>Nombre</div><div>G</div><div>GP</div><div>GP-5P</div><div>PE-F</div><div>EX20</div><div>ED-SS</div><div>EX-PE</div><div>EX-BR</div><div>ED-CS</div><div>TR</div><div>PE</div>
    <div>C. ASKARTZA</div><div>226</div><div>35</div><div>19</div><div>13</div><div>191</div><div>0</div><div>0</div><div>0</div><div>4</div><div>0</div><div>40</div>
    </body></html>'''
    rows=parse_rfen_team_stats(html, 'https://rfen.es/stats', '25/26 Primera División Masculina')
    metrics={r['metric']:r['value'] for r in rows if r['team_name']=='C. ASKARTZA'}
    assert metrics['G']==226 and metrics['EX20']==191 and metrics['PE']==40

def test_calendar_competitions_and_tactical_report_render():
    client=TestClient(app)
    _register(client)
    club_id=_demo_club()
    team_name=f"Tactical {uuid.uuid4().hex[:6]}"
    client.post('/teams', data={'name':team_name,'club_id':str(club_id),'category':'Women'})
    db=SessionLocal()
    try:
        team=db.scalar(select(Team).where(Team.name==team_name))
        team_id=team.id
        assert db.scalars(select(OfficialDataSource)).first() is not None
    finally:
        db.close()
    r=client.post('/matches', data={'team_id':team_id,'opponent':'High Level Opponent','competition':'Test Cup','match_date':'2026-09-01','video_url':''}, follow_redirects=False)
    match_id=int(r.headers['location'].split('/')[-1])
    client.post(f'/matches/{match_id}/events', data={'event_type':'power_play_start','second':'10','perspective':'for','phase_tag':'power_play','note':'Numerical advantage starts'})
    client.post(f'/matches/{match_id}/events', data={'event_type':'pass_complete','second':'13','perspective':'for','phase_tag':'power_play','note':'Ball circulation'})
    client.post(f'/matches/{match_id}/events', data={'event_type':'shot_on_target','second':'17','perspective':'for','phase_tag':'power_play','note':'First shot'})
    client.post(f'/matches/{match_id}/events', data={'event_type':'goal','second':'18','perspective':'for','phase_tag':'power_play','note':'Goal'})
    page=client.get(f'/matches/{match_id}/tactics')
    assert page.status_code==200
    assert 'TACTICAL INTELLIGENCE' in page.text
    assert 'Power Play' in page.text
    assert '1 tagged sequences' in page.text
    assert client.get('/calendar').status_code==200
    assert client.get('/competitions').status_code==200


def test_knowledge_page_contains_visual_tactical_synthesis_without_source_registry():
    client=TestClient(app)
    page=client.get('/knowledge')
    assert page.status_code==200
    assert "Understand tactics like on a coach's tablet" in page.text
    assert 'Press defence' in page.text
    assert 'Zone+ 4–2' in page.text
    assert 'Zone− compact 5 v 6' in page.text
    assert 'SCIENCE + COACHING' not in page.text
    assert 'Secrets of a Serbian Water Polo Coach' not in page.text


def test_official_benchmark_spain_greece_full_match_and_exact_url():
    from services.benchmark_matches import benchmark_for_url
    from services.video import youtube_embed, timestamped_video_url
    url = 'https://www.youtube.com/watch?v=bF-Am10VtF4&list=PLg25OJAWYpDJJ1AWc5bkzcyv7Mt8Wfpdy&index=17'
    benchmark = benchmark_for_url(url)
    assert benchmark is not None
    assert benchmark['video_type'] == 'full_match'
    assert benchmark['duration_seconds'] == 5222
    assert benchmark['final_score'] == [11, 9]
    assert benchmark['quarters'] == [[0, 3], [3, 4], [3, 0], [5, 2]]
    assert benchmark['extra_player']['Spain'] == {'goals': 4, 'attempts': 9}
    assert benchmark['extra_player']['Greece'] == {'goals': 2, 'attempts': 6}
    assert youtube_embed(url).endswith('bF-Am10VtF4?enablejsapi=1&playsinline=1')
    assert timestamped_video_url(url, 123).endswith('&t=123s')
    client=TestClient(app)
    page=client.get('/benchmarks')
    assert page.status_code == 200
    assert 'Spain vs Greece' in page.text
    assert '11–9' in page.text
