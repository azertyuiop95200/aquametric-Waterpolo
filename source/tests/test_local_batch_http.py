"""Native R7 batch integration using actual small synthetic MP4s.
The rapid and provider engines are mocked in entrypoint tests; no paid inference.
"""
import json,unittest,zipfile
from unittest.mock import patch
from pathlib import Path
import cv2,numpy as np
from sqlalchemy.orm import Session
from models import Match,AutonomousAnalysis
from services.local_scan_batch import run,plan,attach
from services.analysis_product import build_analysis_zip,run_product_analysis
from services.complete_analysis_runner import run_complete_analysis
import test_r7_http as base

class LocalBatchTests(unittest.TestCase):
    def setUp(self):
        self.b=base.R7HTTPTests('test_scan_export_and_isolation');self.b.setUp()
        self.addCleanup(self.b.doCleanups);self.qa=self.b.qa;self.path=self.b.path
    def test_plan_and_bounds(self):
        self.assertEqual(plan(20),[(0,20)])
        self.assertEqual(plan(1000),[(116,75),(347,75),(578,75),(809,75)])
        self.assertEqual(plan(1000,4,25),[(122,25),(366,25),(609,25),(853,25)])
        for args in ((0,), (100,13), (100,4,76)):
            with self.assertRaises(ValueError):plan(*args)
    def test_reuse_and_source_replacement(self):
        with Session(self.qa.engine) as db:
            m=db.get(Match,10)
            a=run(db,m,self.path,window_count=1)
            self.assertEqual(len(a['persisted_ids']),2);self.assertEqual(a['unique_sampled_frames'],13)
            self.assertFalse(a['failed']);self.assertFalse(a['statistical_use_allowed'])
            b=run(db,m,self.path,window_count=1)
            self.assertEqual(b['reused_runs'],2);self.assertEqual(b['persisted_ids'],a['persisted_ids'])
            writer=cv2.VideoWriter(str(self.path),cv2.VideoWriter_fourcc(*'mp4v'),25,(320,240))
            self.assertTrue(writer.isOpened())
            for i in range(30):writer.write(np.full((240,320,3),i*3,np.uint8))
            writer.release()
            c=run(db,m,self.path,window_count=1)
            self.assertNotEqual(c['source_sha256_at_execution'],a['source_sha256_at_execution'])
            self.assertEqual(c['reused_runs'],0)
            self.assertTrue(set(c['persisted_ids']).isdisjoint(a['persisted_ids']))
    def test_rapid_entrypoint_report_export(self):
        with Session(self.qa.engine) as db:
            m=db.get(Match,10);auto=db.get(AutonomousAnalysis,3)
            with patch('services.analysis_product.run_rapid_analysis',return_value={'autonomy':auto}),patch('services.analysis_product.build_exact_evidence_pack'):
                result=run_product_analysis(db,m,self.path.parent,self.path.parent)
            b=result['local_scan_batch'];self.assertEqual(b['planned_windows'],4);self.assertEqual(len(b['persisted_ids']),8)
            self.assertFalse(b['statistical_use_allowed'])
            saved=json.loads(auto.summary_json)['local_scan_batch'];self.assertEqual(saved,b)
            with zipfile.ZipFile(build_analysis_zip(db,m,self.path.parent)) as z:
                name=next(n for n in z.namelist() if n.endswith('/analysis.json'))
                self.assertEqual(json.loads(z.read(name))['local_scan_batch']['persisted_ids'],b['persisted_ids'])
        for url in (self.qa.report,self.qa.export):
            r=self.qa.client.get(url);self.assertEqual(r.status_code,200,r.text[:300]);self.assertIn('Scan automatique réparti de la source principale',r.text)
    def test_complete_entrypoint(self):
        with Session(self.qa.engine) as db:
            m=db.get(Match,10);auto=db.get(AutonomousAnalysis,3)
            with patch('services.complete_analysis_runner.run_rapid_analysis',return_value={'autonomy':auto}),patch('services.complete_analysis_runner._refine_score_change_focus',return_value=0),patch('services.complete_analysis_runner.build_exact_evidence_pack'),patch('services.video_action_runner.run_video_actions',return_value={'status':'disabled'}):
                result=run_complete_analysis(db,m,self.path.parent,self.path.parent)
            self.assertEqual(len(result['local_scan_batch']['persisted_ids']),8)
            self.assertEqual(result['video_actions']['status'],'disabled')
    def test_budget_and_failure(self):
        with Session(self.qa.engine) as db:
            m=db.get(Match,10);auto=db.get(AutonomousAnalysis,3)
            with patch('services.local_scan_batch.monotonic',side_effect=[0]+[99]*8):
                r=run(db,m,self.path)
            self.assertEqual(r['status'],'unavailable');self.assertEqual(len(r['failed']),8);self.assertEqual(r['unique_sampled_frames'],0)
            self.path.unlink()
            result={'autonomy':auto};b=attach(db,m,self.path,result)
            self.assertEqual(b['status'],'unavailable');self.assertFalse(b['statistical_use_allowed'])
