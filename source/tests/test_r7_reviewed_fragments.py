"""Reviewed fragment aggregation: synthetic video, actual calibration and HTTP exports."""
import copy,csv,io,unittest,zipfile
from sqlalchemy.orm import Session
from models import Match
from services.r7_metric_review import analyze,select_tracks
from services.vision_scan_evidence import save_scan
from services.analysis_product import build_analysis_zip
import test_r7_metric_review as fixture

class ReviewedFragmentTests(unittest.TestCase):
    def setUp(self):
        self.b=fixture.R7MetricTests('test_http_report_and_exports')
        self.b.setUp()
        self.addCleanup(self.b.doCleanups)
        self.scan=copy.deepcopy(self.b.scan)
        tr=self.scan['tracks'][0]
        pts=tr['points']
        tr['points']=pts[:6]
        self.scan['tracks'].append(dict(id=2,kind='head',points=pts[6:]))
        for f in self.scan['frames'][6:]:
            f['detections'][0]['track_id']=2
        self.scan.update(tracklets_total=2,tracklets_at_least_3=2,fragment_link_review=dict(
            engine='r7-fragment-links-v1',statistical_use_allowed=False,links=[
                dict(from_track_id=1,to_track_id=2,from_second=pts[5]['second'],
                     to_second=pts[6]['second'],status='review_candidate_not_verified',
                     missing_samples=0,forward_error_px=.1,reverse_error_px=.1)]))
        self.raw=copy.deepcopy(self.b.raw)
        self.raw['tracks'][0].update(fragment_track_ids=[1,2],links_reviewed=True,
                                    link_evidence='Synthetic identity review')
    def test_metrics_and_gap(self):
        p=analyze(self.b.path,self.scan,self.raw,self.b.roster)['players'][0]
        self.assertEqual(p['fragment_track_ids'],[1,2])
        self.assertEqual(p['fragment_count'],2)
        self.assertEqual(p['requested_points'],13)
        self.assertEqual(len(p['segments']),2)
        self.assertAlmostEqual(p['metrics']['observed_s'],.88,places=3)
        self.assertAlmostEqual(sum(c['seconds'] for c in p['occupation']['cells']),.88,places=3)
        self.assertIsNone(p['playing_seconds'])
    def test_invalid_requests(self):
        for changes in (dict(links_reviewed=False),dict(link_evidence=''),
                        dict(fragment_track_ids=[2,1]),dict(fragment_track_ids=[1,1]),
                        dict(track_id=True),dict(fragment_track_ids=[1,99])):
            raw=copy.deepcopy(self.raw)
            raw['tracks'][0].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                select_tracks(self.scan,raw,self.b.roster)
    def test_double_assignment(self):
        self.raw['tracks'].append(dict(track_id=2,side='against',cap_number=2,
                                      colour='blue',evidence='Synthetic reference'))
        with self.assertRaises(ValueError):
            select_tracks(self.scan,self.raw,self.b.roster)
    def test_cut_and_absent_link(self):
        self.scan['frames'][6]['scene_reset']=True
        with self.assertRaises(ValueError):
            select_tracks(self.scan,self.raw,self.b.roster)
        self.scan['frames'][6]['scene_reset']=False
        self.scan['fragment_link_review']['links']=[]
        with self.assertRaises(ValueError):
            select_tracks(self.scan,self.raw,self.b.roster)
    def test_persist_report_exports(self):
        with Session(self.b.qa.engine) as db:
            row=save_scan(db,db.get(Match,10),None,'tracklets',self.scan,self.b.path)
            self.raw['scan_digest']=row.digest
            url=f'/matches/10/analysis/r7-metric/{row.id}'
        r=self.b.client.post(url,json=self.raw)
        self.assertEqual(r.status_code,200,r.text)
        for url in (self.b.qa.report,self.b.qa.export):
            r=self.b.client.get(url)
            self.assertEqual(r.status_code,200,r.text[:200])
            self.assertIn('raccordements revus, lacunes exclues',r.text)
        with Session(self.b.qa.engine) as db:
            with zipfile.ZipFile(build_analysis_zip(db,db.get(Match,10),self.b.path.parent)) as z:
                name=next(n for n in z.namelist() if n.endswith('r7_reviewed_window_metrics.csv'))
                rows=list(csv.DictReader(io.StringIO(z.read(name).decode())))
                self.assertEqual(rows[0]['fragment_track_ids'],'1;2')
                self.assertEqual(rows[0]['fragment_count'],'2')
                self.assertEqual(rows[0]['scope'],'reviewed_window_not_match_total')
