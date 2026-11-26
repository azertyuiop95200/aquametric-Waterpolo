import unittest
from services.possession_evidence import CAUSES, validate, build_note, report
from jinja2 import Environment, FileSystemLoader, select_autoescape

class PossessionReviewTests(unittest.TestCase):
    def row(self, **kw):
        r=dict(start=1,end=2,before="for",after="against",before_state="observed",after_state="observed",
               cause="unknown",cause_verified=False,decision_verified=False,exact=False,prior_shot=False,evidence="Contrôles visibles")
        r.update(kw);return r
    def event(self,id=1,period=1,segment=5,**kw):
        r=self.row(**kw)
        return dict(id=id,event_type="possession_transition",confidence="CONFIRMED",second=r["end"],note=build_note(**r,period=period,segment=segment))
    def test_catalogue(self): self.assertEqual(len(CAUSES),52)
    def test_opposite(self): self.assertEqual(validate(**self.row())["minimum_changes"],1)
    def test_not_exact(self): self.assertIsNone(validate(**self.row())["exact_count"])
    def test_same(self): self.assertEqual(validate(**self.row(after="for"))["status"],"same_team_endpoints")
    def test_apparent(self): self.assertEqual(validate(**self.row(before_state="apparent"))["status"],"probable_opposite_endpoints")
    def test_unknown(self): self.assertEqual(validate(**self.row(after="unknown",after_state="unknown"))["status"],"unresolved")
    def test_bad_team(self):
        with self.assertRaises(ValueError):validate(**self.row(after="unknown"))
    def test_nan(self):
        with self.assertRaises(ValueError):validate(**self.row(start=float("nan")))
    def test_reverse(self):
        with self.assertRaises(ValueError):validate(**self.row(start=3))
    def test_missing_evidence(self):
        with self.assertRaises(ValueError):validate(**self.row(evidence=" "))
    def test_gesture_alone(self):
        with self.assertRaises(ValueError):validate(**self.row(cause="offensive_foul",cause_verified=True))
    def test_exact_requires_observed(self):
        with self.assertRaises(ValueError):validate(**self.row(before_state="apparent",exact=True))
    def test_cause_not_credit_without_exact(self):
        self.assertIsNone(validate(**self.row(cause="pass_intercepted",cause_verified=True))["attributed_cause"])
    def test_offensive_foul(self):
        self.assertTrue(validate(**self.row(cause="offensive_foul",cause_verified=True,decision_verified=True,exact=True))["turnover"])
    def test_block(self):
        self.assertFalse(validate(**self.row(cause="shot_blocked",cause_verified=True,exact=True))["turnover"])
    def test_water_pass(self):
        self.assertIsNone(validate(**self.row(cause="pass_into_water",cause_verified=True,exact=True))["turnover"])
    def test_duplicate(self):
        p=report([self.event(),self.event(2)])
        self.assertEqual(len(p["rows"]),1);self.assertEqual(len(p["rejected"]),1)
    def test_conflict(self):
        self.assertFalse(report([self.event(),self.event(2,after="for")])["rows"])
    def test_overlap(self):
        p=report([self.event(),self.event(2,start=1.5,end=2.5)])
        self.assertEqual(p["bounds"][0]["lower_bound"],1)
    def test_disjoint(self):
        p=report([self.event(),self.event(2,start=2.1,end=3)])
        self.assertEqual(p["bounds"][0]["lower_bound"],2)
    def test_prior(self):self.assertEqual(report([self.event(prior_shot=True)])["bounds"][0]["lower_bound"],0)
    def test_sources_separate(self):
        p=report([self.event(),self.event(2,segment=6)])
        self.assertEqual(len(p["bounds"]),2);self.assertIsNone(p["exact_total_changes"])
    def test_candidate_excluded(self):
        e=self.event();e["confidence"]="CANDIDATE";self.assertFalse(report([e])["rows"])
    def test_no_rate(self):self.assertIsNone(report([self.event()])["turnover_rate"])
    def test_tag_override(self):
        p=report([self.event(evidence="p_after=for | p_cv=1")]);self.assertEqual(p["rows"][0]["after"],"against")
    def test_restart_no_control_inference(self):
        p=report([self.event(after="unknown",after_state="unknown",decision_verified=True,restart_award="against",restart_verified=True)])
        self.assertEqual(p["rows"][0]["restart_award"],"against");self.assertIsNone(p["rows"][0]["minimum_changes"])
    def test_restart_requires_decision(self):
        with self.assertRaises(ValueError):validate(**self.row(restart_award="against",restart_verified=True))
    def test_template(self):
        env=Environment(loader=FileSystemLoader("source/templates"),autoescape=select_autoescape())
        html=env.get_template("possession_evidence.html").render(snapshot={"possession_evidence":report([self.event(evidence="<script>")])})
        self.assertIn("Contrôles opposés",html);self.assertIn("&lt;script&gt;",html)
        self.assertNotIn("<script>",html)
        self.assertIn("Aucune fenêtre",env.get_template("possession_evidence.html").render(snapshot={"possession_evidence":report([])}))
        self.assertIn("possession_transition",env.get_template("possession_evidence_controls.html").render())
