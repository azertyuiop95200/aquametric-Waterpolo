"""R7 integration tests: actual decoder, handlers, persistence, HTML and ZIP.
Synthetic video; no claim about real detection accuracy or weights.
"""
import json, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
from sqlalchemy.orm import Session
from models import Match,VisionScanEvidence
import analysis_product_routes as routes
import test_calibrated_http_review as fixture
from services.analysis_product import build_analysis_zip
from services.r7_initial_scan import initial_scan
from services.learned_head import hog
from services.vision_scan_evidence import save_scan

class R7HTTPTests(unittest.TestCase):
    def setUp(self):
        self.qa=fixture.CalibratedHTTPTests('test_owner_lifecycle')
        self.qa.setUp();self.addCleanup(self.qa.tearDown)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'qa-primary.mp4'
        writer=cv2.VideoWriter(str(self.path),cv2.VideoWriter_fourcc(*'mp4v'),25,(320,240))
        self.assertTrue(writer.isOpened())
        for i in range(30):
            f=np.full((240,320,3),(180,135,0),dtype=np.uint8)
            cv2.circle(f,(80+i,120),6,(250,250,250),-1)
            writer.write(f)
        writer.release()
        self.assertTrue(self.path.is_file())
        p=patch.object(routes,'UPLOAD_DIR',Path(self.tmp.name));p.start();self.addCleanup(p.stop)
        for suffix,handler in [('r7-scan',routes.r7_scan),('r7-packet',routes.r7_packet),('r7-review/{scan_id}',routes.r7_review)]:
            self.qa.app.add_api_route('/matches/{match_id}/analysis/'+suffix,handler,methods=['POST'])
        self.client=self.qa.client;self.base='/matches/10/analysis/'
    def test_scan_export_and_isolation(self):
        data=dict(start_frame=0,frame_count=25,tracking_mode='head_flow')
        r=self.client.post(self.base+'r7-scan',data=data,follow_redirects=False)
        self.assertEqual(r.status_code,303,r.text)
        s=self.qa.snapshot();v=s['vision_scan_evidence']
        self.assertEqual(v['status'],'experimental_partial');self.assertEqual(len(v['rows']),1)
        self.assertEqual(v['rows'][0]['sampled_frames'],13)
        self.assertFalse(v['statistical_use_allowed'])
        self.assertEqual(self.client.post(self.base+'r7-scan',data=data,follow_redirects=False).status_code,303)
        self.assertEqual(len(self.qa.snapshot()['vision_scan_evidence']['rows']),1)
        for p in (self.qa.report,self.qa.export):
            r=self.client.get(p);self.assertEqual(r.status_code,200);self.assertIn('id="visionR7"',r.text)
        with Session(self.qa.engine) as db:
            buf=build_analysis_zip(db,db.get(Match,10),Path(self.tmp.name))
            with zipfile.ZipFile(buf) as z:
                names=[n for n in z.namelist() if '/vision_scans/' in n];self.assertEqual(len(names),1)
                result=json.loads(z.read(names[0]))['result'];self.assertEqual(len(result['frames']),13);self.assertFalse(result['statistical_use_allowed'])
        self.client.get('/__qa_session/2')
        self.assertEqual(self.client.post(self.base+'r7-scan',data=data).status_code,404)
    def test_initial_scan_and_missing_source(self):
        with Session(self.qa.engine) as db:
            m=db.get(Match,10);self.assertIsNotNone(initial_scan(db,m,self.path))
            self.assertRaises(ValueError,save_scan,db,m,None,'tracklets',dict(identity_verified=True),self.path)
        self.assertEqual(self.qa.snapshot()['vision_scan_evidence']['rows'][0]['scan_status'],'completed')
        self.path.unlink()
        self.assertEqual(self.client.post(self.base+'r7-scan',data={}).status_code,404)
    def test_packet_review(self):
        weights=Path(self.tmp.name)/'synthetic_weights.json'
        weights.write_text(json.dumps(dict(weights=[0.0]*hog().getDescriptorSize(),bias=1.)))
        with patch.dict('os.environ',{'AQUAMETRIC_R7_PRIVATE_WEIGHTS':str(weights)}):
            r=self.client.post(self.base+'r7-packet',data=dict(frame_index=2,budget=3))
        self.assertEqual(r.status_code,200,r.text)
        x=r.json();p=x['packet'];self.assertFalse(p['statistical_use_allowed'])
        decisions=[dict(candidate_id=c['candidate_id'],label='uncertain') for c in p['candidates']]
        url=self.base+'r7-review/'+str(x['scan_id'])
        r=self.client.post(url,json=dict(packet_sha256=p['packet_sha256'],decisions=decisions))
        self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()['review']['statistical_use_allowed'])
        self.assertEqual(len(self.qa.snapshot()['vision_scan_evidence']['rows']),2)
        self.assertEqual(self.client.post(url,json=dict(packet_sha256='0'*64,decisions=[])).status_code,422)
        self.path.write_bytes(b'changed source')
        self.assertEqual(self.client.post(url,json=dict(packet_sha256=p['packet_sha256'],decisions=[])).status_code,409)
    def test_unconfigured_and_invalid_window(self):
        with patch.dict('os.environ',{'AQUAMETRIC_R7_PRIVATE_WEIGHTS':''}):
            self.assertEqual(self.client.post(self.base+'r7-packet',data=dict(frame_index=2)).status_code,409)
        self.assertEqual(self.client.post(self.base+'r7-scan',data=dict(frame_count=76)).status_code,422)
        self.assertEqual(self.qa.snapshot()['vision_scan_evidence']['rows'],[])
