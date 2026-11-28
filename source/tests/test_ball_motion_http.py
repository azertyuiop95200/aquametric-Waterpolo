"""Real decoder and HTTP integration on a synthetic moving ball."""
import json,unittest,zipfile
import cv2,numpy as np
from sqlalchemy.orm import Session
from models import Match
import analysis_product_routes as routes
from services.analysis_product import build_analysis_zip
import test_r7_http as base

class BallMotionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.b=base.R7HTTPTests('test_scan_export_and_isolation')
        self.b.setUp();self.addCleanup(self.b.doCleanups)
        self.qa=self.b.qa;self.client=self.b.client;self.path=self.b.path
        self.qa.app.add_api_route('/matches/{match_id}/analysis/r7-ball-motion',routes.r7_ball_motion,methods=['POST'])
        self.url='/matches/10/analysis/r7-ball-motion'
        writer=cv2.VideoWriter(str(self.path),cv2.VideoWriter_fourcc(*'mp4v'),25,(1280,720))
        self.assertTrue(writer.isOpened())
        for i in range(8):
            f=np.full((720,1280,3),120,np.uint8)
            cv2.circle(f,(80+10*i,300),6,(60,60,60),-1)
            writer.write(f)
        writer.release()
        self.seeds=[dict(frame=1,x=90/1280,y=300/720,reviewed=True),dict(frame=2,x=100/1280,y=300/720,reviewed=True)]
    def post(self,**kw):
        data=dict(frame_index=3,seeds_json=json.dumps(self.seeds));data.update(kw)
        return self.client.post(self.url,data=data,follow_redirects=False)
    def test_persistence_and_exports(self):
        before=self.qa.snapshot()
        r=self.post();self.assertEqual(r.status_code,303,r.text)
        s=self.qa.snapshot();v=s['vision_scan_evidence'];self.assertEqual(len(v['rows']),1)
        b=v['rows'][0]['ball_motion_review']
        self.assertEqual(b['status'],'candidates');self.assertFalse(b['confirmed'])
        self.assertFalse(b['statistical_use_allowed']);self.assertFalse(b['pts_validated'])
        self.assertLess(abs(b['candidates'][0]['x']*1280-110),8)
        self.assertEqual(s['verified_events'],before['verified_events'])
        self.assertEqual(s['statistics'],before['statistics'])
        self.assertEqual(self.post().status_code,303)
        self.assertEqual(len(self.qa.snapshot()['vision_scan_evidence']['rows']),1)
        for url in (self.qa.report,self.qa.export):
            r=self.client.get(url);self.assertEqual(r.status_code,200);self.assertIn('Recherche assistée du ballon — scan',r.text)
        with Session(self.qa.engine) as db:
            with zipfile.ZipFile(build_analysis_zip(db,db.get(Match,10),self.path.parent)) as z:
                name=next(n for n in z.namelist() if '/vision_scans/' in n)
                self.assertEqual(json.loads(z.read(name))['result'],b)
    def test_guardrails(self):
        self.assertEqual(self.post(frame_index=7).status_code,422)
        self.assertEqual(self.post(seeds_json='{}').status_code,422)
        self.assertEqual(self.post(seeds_json='not-json').status_code,422)
        self.assertEqual(self.post(segment_id=999).status_code,404)
        self.assertEqual(self.qa.snapshot()['vision_scan_evidence']['rows'],[])
        self.client.get('/__qa_session/2')
        self.assertEqual(self.post().status_code,404)
    def test_no_candidate_is_not_absence(self):
        w=cv2.VideoWriter(str(self.path),cv2.VideoWriter_fourcc(*'mp4v'),25,(1280,720))
        self.assertTrue(w.isOpened())
        for _ in range(8):w.write(np.full((720,1280,3),120,np.uint8))
        w.release()
        self.assertEqual(self.post().status_code,303)
        b=self.qa.snapshot()['vision_scan_evidence']['rows'][0]['ball_motion_review']
        self.assertEqual(b['status'],'no_supported_candidate');self.assertFalse(b['confirmed'])
        self.assertIn('ne signifie pas absence du ballon',self.client.get(self.qa.report).text)
