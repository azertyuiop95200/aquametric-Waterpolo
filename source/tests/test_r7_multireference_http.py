"""Multi-reference integration; true decoder, synthetic scene and reference tracks."""
import json,unittest,zipfile
from types import SimpleNamespace
import numpy as np
from sqlalchemy.orm import Session
from models import Match
from services.r7_metric_review import analyze
from services.r7_multireference import consensus
from services.analysis_product import build_analysis_zip
import test_r7_metric_review as base

class ConsensusTests(unittest.TestCase):
    def test_strict_consensus(self):
        model=SimpleNamespace(w=640,h=360,length_m=25.,width_m=20.)
        a=dict(matrix=np.array([[.02,0,0],[0,.04,-7.2],[0,0,1.]]),reference=0,alignment_error_px=.1)
        b=dict(a,reference=2,matrix=a['matrix'].copy())
        b['matrix'][0,2]=.2
        q=consensus(model,[a,b],.4,.5)
        self.assertEqual(q['support'],2);self.assertAlmostEqual(q['spread_m'],.2)
        self.assertIsNone(consensus(model,[a],.4,.5))
        b['matrix'][0,2]=1.
        self.assertIsNone(consensus(model,[a,b],.4,.5))
        b['matrix'][0,2]=30.
        self.assertIsNone(consensus(model,[a,b],.4,.5))

class MultiReferenceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.b=base.R7MetricTests('test_http_report_and_exports')
        self.b.setUp();self.addCleanup(self.b.doCleanups)
        self.raw=dict(self.b.raw,additional_references=[dict(reference_frame=2,anchors=self.b.raw['anchors'],polygon=self.b.raw['polygon'])],same_goal_and_side_reviewed=True)
    def test_consensus_and_exports(self):
        r=self.b.client.post(self.b.url,json=self.raw)
        self.assertEqual(r.status_code,200,r.text)
        m=self.b.qa.snapshot()['vision_scan_evidence']['rows'][-1]['metric_review']
        self.assertEqual(m['calibration_mode'],'multi_reference_consensus')
        self.assertEqual(len(m['reference_details']),2)
        self.assertTrue(all(q['accepted'] and q['support']==2 for q in m['projection_quality']))
        self.assertGreater(m['players'][0]['metrics']['observed_s'],.5)
        self.assertFalse(m['independent_metric_accuracy_validated'])
        self.assertFalse(m['statistical_use_allowed'])
        for url in (self.b.qa.report,self.b.qa.export):
            r=self.b.client.get(url);self.assertEqual(r.status_code,200,r.text[:300]);self.assertIn('Calibration dynamique : 2 références',r.text)
        with Session(self.b.qa.engine) as db:
            with zipfile.ZipFile(build_analysis_zip(db,db.get(Match,10),self.b.path.parent)) as z:
                name=next(n for n in z.namelist() if n.endswith('r7_calibration_consensus.csv'))
                self.assertEqual(len(z.read(name).decode().splitlines()),14)
    def test_invalid_references(self):
        for changed in (dict(same_goal_and_side_reviewed=False),dict(additional_references=[]),
                dict(additional_references=[dict(self.raw['additional_references'][0],reference_frame=0)]),
                dict(additional_references=[dict(self.raw['additional_references'][0],reference_frame=1)])):
            r=self.b.client.post(self.b.url,json=dict(self.raw,**changed))
            self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(len(self.b.qa.snapshot()['vision_scan_evidence']['rows']),1)
    def test_incompatible_geometry_rejected(self):
        alt=dict(self.raw['additional_references'][0],anchors=[[x+.1,y] for x,y in self.raw['anchors']])
        r=self.b.client.post(self.b.url,json=dict(self.raw,additional_references=[alt]))
        self.assertEqual(r.status_code,422,r.text)
    def test_cut_splits_measurement(self):
        scan=json.loads(json.dumps(self.b.scan));scan['frames'][6]['scene_reset']=True
        m=analyze(self.b.path,scan,self.raw,self.b.roster)
        self.assertEqual(len(m['players'][0]['segments']),2)
        self.assertLess(m['players'][0]['metrics']['observed_s'],.96)
