"""Actual owner-scoped HTTP, persisted reviewed intervals and exports.
Uses a synthetic video; no real match annotations or detection claims.
"""
import json,unittest,zipfile
from pathlib import Path
from sqlalchemy.orm import Session
from models import Match,MatchVideoSegment,AutonomousAnalysis
import analysis_product_routes as routes
from services.analysis_product import build_analysis_zip
import test_r7_http as base

class PossessionWindowHTTPTests(unittest.TestCase):
    def setUp(self):
        self.b=base.R7HTTPTests('test_scan_export_and_isolation')
        self.b.setUp();self.addCleanup(self.b.doCleanups)
        self.qa=self.b.qa;self.client=self.b.client;self.path=self.b.path
        self.qa.app.add_api_route('/matches/{match_id}/analysis/possession-window',routes.save_possession_window,methods=['POST'])
        self.url='/matches/10/analysis/possession-window'
    def data(self,**kw):
        raw=dict(analysis_id=3,source='match',period=1,start=.2,end=.4,before='for',after='against',
            before_state='observed',after_state='observed',cause='pass_intercepted',
            cause_verified='true',exact='true',source_reviewed='true',evidence='Synthetic review only')
        raw.update(kw);return raw
    def post(self,**kw):return self.client.post(self.url,data=self.data(**kw),follow_redirects=False)
    def test_persistence_report_and_export(self):
        prior=self.qa.snapshot()
        r=self.post();self.assertEqual(r.status_code,303,r.text)
        s=self.qa.snapshot();p=s['possession_evidence'];self.assertEqual(p['status'],'experimental_partial')
        self.assertEqual(p['rows'][0]['exact_count'],1);self.assertEqual(p['rows'][0]['attributed_cause'],'pass_intercepted')
        self.assertEqual(p['bounds'][0]['lower_bound'],1)
        self.assertIsNone(p['exact_total_changes']);self.assertIsNone(p['game_duration_s'])
        self.assertEqual(s['verified_events'],prior['verified_events'])
        self.assertEqual(s['statistics'],prior['statistics'])
        for url in (self.qa.report,self.qa.export):
            r=self.client.get(url);self.assertEqual(r.status_code,200,r.text[:300]);self.assertIn('id="possessionEvidence"',r.text);self.assertIn('Synthetic review only',r.text)
        with Session(self.qa.engine) as db:
            with zipfile.ZipFile(build_analysis_zip(db,db.get(Match,10),self.path.parent)) as z:
                name=next(n for n in z.namelist() if n.endswith('possession_evidence.json'))
                self.assertEqual(json.loads(z.read(name))['rows'][0]['id'],'P1')
                name=next(n for n in z.namelist() if n.endswith('possession_windows.csv'))
                self.assertIn('pass_intercepted',z.read(name).decode())
    def test_duplicate_overlap_and_bounds(self):
        self.assertEqual(self.post().status_code,303)
        self.assertEqual(self.post().status_code,422)
        self.assertEqual(self.post(start=.3,end=.5).status_code,422)
        self.assertEqual(self.post(start=.5,end=99).status_code,422)
        self.assertEqual(self.post(start=.5,end=.7,source_reviewed='false').status_code,422)
        self.assertEqual(self.post(start=.5,end=.7,cause='offensive_foul').status_code,422)
        self.assertEqual(self.post(start=.5,end=.7,analysis_id=2).status_code,409)
        self.assertEqual(len(self.qa.snapshot()['possession_evidence']['rows']),1)
    def test_registered_source_and_period(self):
        with Session(self.qa.engine) as db:
            db.add(MatchVideoSegment(id=22,match_id=10,period=2,part_index=1,label='Q2',source_type='upload',video_path=self.path.name))
            db.commit()
        self.assertEqual(self.post().status_code,422)
        self.assertEqual(self.post(source='22',period=1).status_code,422)
        self.assertEqual(self.post(source='22',period=2).status_code,303)
        self.assertEqual(self.qa.snapshot()['possession_evidence']['rows'][0]['source'],'22')
        with Session(self.qa.engine) as db:
            seg=db.get(MatchVideoSegment,22);seg.period=3;db.commit()
        self.assertEqual(self.qa.snapshot()['possession_evidence']['rows'],[])
    def test_source_change_and_owner(self):
        self.assertEqual(self.post().status_code,303)
        self.path.write_bytes(b'changed source')
        self.assertEqual(self.post(start=.5,end=.7).status_code,422)
        self.client.get('/__qa_session/2')
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.client.get(self.qa.report).status_code,404)
    def test_unknown_not_counted(self):
        r=self.post(after='unknown',after_state='unknown',cause='unknown',cause_verified='false',exact='false')
        self.assertEqual(r.status_code,303,r.text)
        p=self.qa.snapshot()['possession_evidence']
        self.assertIsNone(p['rows'][0]['minimum_changes']);self.assertIsNone(p['rows'][0]['turnover'])
