"""Persisted candidate lineup observations, genuine report/export handlers.
Synthetic model payload; does not establish real-video clock or identities.
"""
import json,tempfile,unittest,zipfile
from pathlib import Path
from sqlalchemy.orm import Session
from models import Match,VideoActionAnalysis
from services.video_action_runner import normalize_observations
from services.analysis_product import build_analysis_zip
from test_pass_control_http import action,segment
import test_calibrated_http_review as fixture

def lineup(side='for',a=62.,b=58.,start=0.,end=4.,caps=None,**kw):
    d=dict(side=side,period=1,clock_start=a,clock_end=b,start_second=start,end_second=end,
        in_play=caps if caps is not None else list(range(1,8)),excluded=[],complete_lineup=True,
        confidence=.9,clock_evidence='Synthetic visible game clock',lineup_evidence='Synthetic full lineup',
        team_evidence='Synthetic team')
    d.update(kw);return d

def payload():
    return dict(scene='water_polo',summary='Synthetic',observability=[],
        actions=[action(2.,'pass_complete',period=1,game_clock_seconds=60.,game_clock_evidence='Synthetic clock read',
            receiver_cap_number=3,receiver_evidence='Synthetic distinct receiver')],
        lineups=[lineup(),lineup('against',caps=list(range(1,7)),excluded=[7])])

class LineupHTTPTests(unittest.TestCase):
    def setUp(self):
        self.qa=fixture.CalibratedHTTPTests('test_owner_lifecycle')
        self.qa.setUp();self.addCleanup(self.qa.tearDown)
        self.client=self.qa.client
    def save(self,p=None):
        seg=segment();seg.update(status='complete',result=normalize_observations(p or payload(),seg))
        with Session(self.qa.engine) as db:
            db.add(VideoActionAnalysis(match_id=10,fingerprint='b'*64,status='complete',source_kind='upload',
                duration_seconds=4.,segments_json=json.dumps([seg])));db.commit()
    def test_partial_clock_exposure_and_exports(self):
        self.save();s=self.qa.snapshot();v=s['video_actions'];l=v['lineup_exposure']
        self.assertEqual(l['teams']['for']['observed_game_seconds'],4.)
        self.assertEqual(l['teams']['for']['player_seconds'],28.)
        self.assertEqual(l['teams']['against']['players'][-1]['excluded_seconds'],4.)
        self.assertIsNone(l['teams']['against']['players'][-1]['playing_seconds'])
        self.assertEqual(l['numerical_states'],[dict(for_players=7,against_players=6,seconds=4.)])
        p=v['lineup_performance']['teams']['for']['players']
        self.assertEqual(next(r for r in p if r['cap']==2)['passes_attempted'],1)
        self.assertEqual(next(r for r in p if r['cap']==3)['passes_received'],1)
        self.assertEqual(len(s['verified_events']),2)
        for url in (self.qa.report,self.qa.export):
            r=self.client.get(url);self.assertEqual(r.status_code,200,r.text[:300])
            self.assertIn('id="lineupExposure"',r.text);self.assertIn('Situations numériques simultanément observées',r.text)
        with tempfile.TemporaryDirectory() as tmp, Session(self.qa.engine) as db:
            with zipfile.ZipFile(build_analysis_zip(db,db.get(Match,10),Path(tmp))) as z:
                name=next(n for n in z.namelist() if n.endswith('lineup_exposure.json'))
                self.assertEqual(json.loads(z.read(name))['lineup_exposure']['teams']['for']['observed_game_seconds'],4.)
                name=next(n for n in z.namelist() if n.endswith('observed_player_game_time.csv'))
                self.assertIn('for,2,4.0,',z.read(name).decode())
                self.assertTrue(any(n.endswith('observed_numerical_states.csv') for n in z.namelist()))
    def test_missing_clock_and_incomplete(self):
        p=payload();p['lineups']=[lineup(complete_lineup=False),lineup('against',clock_evidence='')]
        self.save(p);l=self.qa.snapshot()['video_actions']['lineup_exposure']
        self.assertIsNone(l['teams']['for']['observed_game_seconds']);self.assertIsNone(l['teams']['against']['observed_game_seconds'])
        self.assertEqual(l['rejected_intervals'],2)
    def test_conflicting_composition(self):
        p=payload();p['lineups']=[lineup(),lineup(caps=[1,2,3,4,5,6,8])]
        self.save(p);v=self.qa.snapshot()['video_actions']
        self.assertIsNone(v['lineup_exposure']['teams']['for']['observed_game_seconds'])
        self.assertEqual(v['lineup_exposure']['teams']['for']['conflict_game_seconds'],4.)
        self.assertEqual(v['lineup_performance']['excluded']['lineup_gap_or_boundary'],1)
    def test_legacy_and_owner(self):
        self.assertIsNone(self.qa.snapshot()['video_actions']['lineup_exposure']['teams']['for']['observed_game_seconds'])
        p=payload();p.pop('lineups');self.save(p)
        self.assertIsNone(self.qa.snapshot()['video_actions']['lineup_exposure']['teams']['for']['observed_game_seconds'])
        self.client.get('/__qa_session/2')
        self.assertEqual(self.client.get(self.qa.report).status_code,404)
