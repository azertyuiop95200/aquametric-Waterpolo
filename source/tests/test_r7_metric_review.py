"""Synthetic reference-track integration; real decoding/calibration/metrics, not detection validation."""
import json,unittest,zipfile
from pathlib import Path
import cv2,numpy as np
from sqlalchemy.orm import Session
from models import Match
import analysis_product_routes as routes
from services.r7_metric_review import select_tracks,analyze
from services.r7_review_pipeline import file_hash
from services.vision_scan_evidence import save_scan
from services.analysis_product import build_analysis_zip
import test_r7_http as base

def candidate_scan(path):
    fps=25.;frames=[];points=[]
    for i in range(0,25,2):
        t=i/fps;x=.4+i*.0006;y=.5
        p=dict(second=t,x=x,y=y,point_source='detector');points.append(p)
        frames.append(dict(source_frame_index=i,second=t,detections=[dict(kind='head',track_id=1,x=x,y=y)]))
    st=path.stat()
    return dict(scan_status='completed',coordinate_system='image_normalized',source_fps_reported=fps,
        source_sha256_at_creation=file_hash(path),source_file_size=st.st_size,source_file_mtime_ns=st.st_mtime_ns,
        first_frame=0,end_frame_exclusive=25,frames=frames,tracks=[dict(id=1,kind='head',points=points)],
        tracklets_total=1,tracklets_at_least_3=1,identity_verified=False,metrics_validated=False,statistical_use_allowed=False)

def review(cap):
    return dict(period=1,reference_frame=0,length_m=25.,width_m=20.,anchors=[[.15,.455],[.15,.545],[.15,.8],[.2,.8],[.3,.8]],
        polygon=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]],all_points_reviewed=True,calibration_reviewed=True,
        nominal_time_acknowledged=True,tracks=[dict(track_id=1,side='for',cap_number=cap,colour='white',evidence='Synthetic reference for regression')])

class R7MetricTests(unittest.TestCase):
    def setUp(self):
        self.b=base.R7HTTPTests('test_scan_export_and_isolation')
        self.b.setUp();self.addCleanup(self.b.doCleanups)
        self.path=self.b.path;self.qa=self.b.qa;self.client=self.b.client
        # Fixed, richly textured synthetic camera background for the real aligner.
        rng=np.random.default_rng(42)
        image=rng.integers(0,256,(240,320,3),dtype=np.uint8)
        writer=cv2.VideoWriter(str(self.path),cv2.VideoWriter_fourcc(*'mp4v'),25,(320,240))
        self.assertTrue(writer.isOpened())
        for _ in range(30):writer.write(image)
        writer.release()
        self.scan=candidate_scan(self.path)
        with Session(self.qa.engine) as db:
            m=db.get(Match,10);self.roster=[p.cap_number for p in m.team.players]
            self.assertTrue(self.roster)
            self.raw=review(self.roster[0])
            r=save_scan(db,m,None,'tracklets',self.scan,self.path)
            self.id=r.id;self.raw['scan_digest']=r.digest
        self.qa.app.add_api_route('/matches/{match_id}/analysis/r7-metric/{scan_id}',routes.r7_metric,methods=['POST'])
        self.qa.app.add_api_route('/matches/{match_id}/analysis/r7-metric-form',routes.r7_metric_form,methods=['POST'])
        self.qa.app.add_api_route('/matches/{match_id}/analysis/r7-evidence/{scan_id}',routes.r7_evidence,methods=['GET'])
        self.url=f'/matches/10/analysis/r7-metric/{self.id}'
    def test_exact_source_and_review(self):
        result=analyze(self.path,self.scan,self.raw,self.roster)
        p=result['players'][0];m=p['metrics']
        self.assertGreater(m['observed_s'],.5)
        self.assertGreater(m['distance_m'],.1)
        self.assertLess(m['distance_m'],1.2)
        self.assertAlmostEqual(sum(c['seconds'] for c in p['occupation']['cells']),m['observed_s'])
        self.assertIsNone(p['playing_seconds'])
        self.assertFalse(result['statistical_use_allowed'])
    def test_http_report_and_exports(self):
        r=self.client.post(self.url,json=self.raw)
        self.assertEqual(r.status_code,200,r.text)
        for url in (self.qa.report,self.qa.export):
            r=self.client.get(url);self.assertEqual(r.status_code,200,r.text[:200]);self.assertIn('Fenêtre métrique R7',r.text);self.assertIn('Occupation observée',r.text)
        with Session(self.qa.engine) as db:
            z=zipfile.ZipFile(build_analysis_zip(db,db.get(Match,10),self.path.parent))
            csv_name=next(n for n in z.namelist() if n.endswith('r7_reviewed_window_metrics.csv'))
            self.assertIn('reviewed_window_not_match_total',z.read(csv_name).decode())
            js=next(n for n in z.namelist() if n.endswith('/analysis.json'))
            self.assertIn('r7_metric_review',z.read(js).decode())
        self.client.get('/__qa_session/2')
        self.assertEqual(self.client.post(self.url,json=self.raw).status_code,404)
    def test_review_guards(self):
        for changed in (dict(all_points_reviewed=False),dict(nominal_time_acknowledged=False),dict(reference_frame=1),dict(tracks=[dict(self.raw['tracks'][0],cap_number=30)])):
            with self.assertRaises(ValueError):select_tracks(self.scan,dict(self.raw,**changed),self.roster)
        self.scan['tracks'][0]['points'][2]['x']=.9
        with self.assertRaises(ValueError):select_tracks(self.scan,self.raw,self.roster)
    def test_hash_and_digest_guards(self):
        self.assertEqual(self.client.post(self.url,json=dict(self.raw,scan_digest='0'*64)).status_code,409)
        self.path.write_bytes(b'different video')
        self.assertEqual(self.client.post(self.url,json=self.raw).status_code,422)
        self.assertEqual(len(self.qa.snapshot()['vision_scan_evidence']['rows']),1)

    def test_form_and_private_evidence(self):
        evidence=f'/matches/10/analysis/r7-evidence/{self.id}'
        r=self.client.get(evidence)
        self.assertEqual(r.status_code,200);self.assertEqual(r.headers.get('cache-control'),'private, no-store')
        self.assertEqual(r.json()['digest'],self.raw['scan_digest'])
        data=dict(scan_ref=f"{self.id}:{self.raw['scan_digest']}",period=1,reference_frame=0,length_m=25,width_m=20,
            anchors_json=json.dumps(self.raw['anchors']),polygon_json=json.dumps(self.raw['polygon']),tracks_json=json.dumps(self.raw['tracks']),
            all_points_reviewed='true',calibration_reviewed='true',nominal_time_acknowledged='true')
        url='/matches/10/analysis/r7-metric-form'
        r=self.client.post(url,data=data,follow_redirects=False)
        self.assertEqual(r.status_code,303,r.text)
        self.assertIn('#visionR7',r.headers['location'])
        self.assertIn('Preuve du scan',self.client.get(self.qa.report).text)
        self.client.get('/__qa_session/2')
        self.assertEqual(self.client.get(evidence).status_code,404)
        self.assertEqual(self.client.post(url,data=data).status_code,404)
