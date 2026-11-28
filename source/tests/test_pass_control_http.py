"""Actual schema -> normalization -> persisted candidate report -> HTML and ZIP.
Synthetic model output, not a video-recognition accuracy test.
"""
import json,unittest,zipfile,tempfile
from pathlib import Path
from sqlalchemy.orm import Session
from models import Match,VideoActionAnalysis
from services.video_action_runner import normalize_observations
from services.video_action_report import canonical_actions
from services.analysis_product import build_analysis_zip
import test_calibrated_http_review as fixture

def action(t,kind,**kw):
    d=dict(second=t,event_type=kind,side="for",confidence=.9,evidence="Synthetic visible ball action",
        team_evidence="Synthetic team evidence",cap_number=2,identity_evidence="Synthetic cap evidence")
    d.update(kw);return d

def interval(a,b,side="for",cap=2):
    return dict(start_second=a,end_second=b,side=side,cap_number=cap,confidence=.9,
        evidence="Synthetic continuous control",team_evidence="Synthetic team",identity_evidence="Synthetic cap")

def payload():
    return dict(scene="water_polo",summary="Synthetic",observability=[],
        actions=[action(1.0,"pass_complete",receiver_cap_number=3,receiver_evidence="Visible distinct teammate",pass_method="dry"),
            action(2.0,"pass_unknown"),action(3.0,"bad_pass")],
        ball_control=[interval(.5,1.5),interval(1.,2.),interval(1.5,2.5,"against",4)])

def segment():
    return dict(index=0,start=0.,end=4.,clip_start=0.,clip_end=4.)

class PassControlHTTPTests(unittest.TestCase):
    def setUp(self):
        self.qa=fixture.CalibratedHTTPTests('test_owner_lifecycle')
        self.qa.setUp();self.addCleanup(self.qa.tearDown)
        self.client=self.qa.client
    def save(self,p=None):
        seg=segment();seg.update(status="complete",result=normalize_observations(p or payload(),seg))
        with Session(self.qa.engine) as db:
            db.add(VideoActionAnalysis(match_id=10,fingerprint="a"*64,status="complete",source_kind="upload",
                duration_seconds=4.,segments_json=json.dumps([seg])));db.commit()
    def test_persisted_report_and_exports(self):
        self.save()
        s=self.qa.snapshot();v=s["video_actions"];p=v["pass_ledger"]["teams"]["for"]
        self.assertEqual((p["attempts"],p["completed"],p["failed"],p["unknown"]),(3,1,1,1))
        self.assertIsNone(p["completion_pct"]);self.assertEqual(p["network"],[{"from":2,"to":3,"count":1}])
        self.assertEqual(v["team"]["basic"]["pass_attempts"],3)
        self.assertIsNone(v["team"]["basic"]["pass_completion_pct"])
        b=v["ball_control"];self.assertEqual(b["observed_video_seconds"],2.)
        self.assertEqual(b["conflicting_video_seconds"],.5)
        self.assertEqual(b["teams"]["for"]["control_video_seconds"],1.)
        self.assertEqual(b["teams"]["against"]["control_video_seconds"],.5)
        self.assertEqual(len(s["verified_events"]),2)
        for url in (self.qa.report,self.qa.export):
            r=self.client.get(url);self.assertEqual(r.status_code,200,r.text[:300])
            self.assertIn('id="passControl"',r.text);self.assertIn("transmissions candidates par bonnet",r.text)
        with tempfile.TemporaryDirectory() as tmp, Session(self.qa.engine) as db:
            with zipfile.ZipFile(build_analysis_zip(db,db.get(Match,10),Path(tmp))) as z:
                name=next(n for n in z.namelist() if n.endswith('pass_control.json'))
                self.assertEqual(json.loads(z.read(name))["pass_ledger"]["teams"]["for"]["attempts"],3)
                name=next(n for n in z.namelist() if n.endswith('pass_network.csv'))
                self.assertIn('for,2,3,1',z.read(name).decode())
                self.assertTrue(any(n.endswith('ball_control_intervals.csv') for n in z.namelist()))
    def test_empty_and_legacy(self):
        v=self.qa.snapshot()["video_actions"]
        self.assertIsNone(v["pass_ledger"]["teams"]["for"]["attempts"])
        self.assertIsNone(v["ball_control"]["teams"]["for"]["control_video_seconds"])
        p=payload();p.pop("ball_control");p["actions"]=[action(1.,"pass_complete")]
        self.save(p);v=self.qa.snapshot()["video_actions"]
        self.assertEqual(v["pass_ledger"]["teams"]["for"]["completed"],1)
        self.assertEqual(v["pass_ledger"]["teams"]["for"]["network"],[])
        self.assertIsNone(v["ball_control"]["teams"]["for"]["control_video_seconds"])
    def test_conflicting_receivers(self):
        p=payload();p["actions"]=[action(1.,"pass_complete",receiver_cap_number=3,receiver_evidence="Receiver visible"),
            action(1.1,"assist",receiver_cap_number=4,receiver_evidence="Other receiver visible")]
        self.save(p);v=self.qa.snapshot()["video_actions"]
        self.assertIsNone(v["pass_ledger"]["teams"]["for"]["attempts"])
        self.assertEqual(v["excluded_count"],2)
    def test_owner_isolation(self):
        self.save();self.client.get('/__qa_session/2')
        self.assertEqual(self.client.get(self.qa.report).status_code,404)
        self.assertEqual(self.client.get(self.qa.export).status_code,404)

    def test_exact_timestamp_conflicting_receivers(self):
        p=payload();p["actions"]=[action(1.,"pass_complete",receiver_cap_number=3,receiver_evidence="Receiver visible"),
            action(1.,"pass_complete",receiver_cap_number=4,receiver_evidence="Other receiver visible")]
        self.save(p);v=self.qa.snapshot()["video_actions"]
        self.assertIsNone(v["pass_ledger"]["teams"]["for"]["attempts"])
        self.assertEqual(v["excluded_count"],2)
