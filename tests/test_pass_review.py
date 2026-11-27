import copy, unittest
from services.pass_review import validate_pass_review, summarize_pass_review
from services.review_reference_import import summarize
from test_review_reference_import import fixture, read
from jinja2 import Environment, FileSystemLoader, select_autoescape

def sample():
    p=fixture()
    a=dict(id="PA1",state="observed_pass",team="bleus",window_start_frame=10,window_end_frame=47,
        release_last_held_frame=20,release_first_free_frame=22,contact_frame=30,control_frame=32,
        contact_state="observed",water_seen_frame=None,control_team="bleus",delivery="air",outcome="completed",
        sender_role="field",pressure="observed",distinct_receiver=True,direct_sequence=True,deflection_observed=None,
        related_event_id="G1",event_relation="precedes_shot",related_interval_id=None,
        observation="Passage observé <script>",evidence=["preuves/fixture.jpg"])
    p["reference"]["pass_review"]=dict(version=1,fps=25,coverage_complete=False,actions=[a])
    return p

class PassReviewTests(unittest.TestCase):
    def validate(self, **kw):
        p=sample();p["reference"]["pass_review"]["actions"][0].update(kw)
        return summarize(read(p)[0],"bleus")["pass_review"]
    def reject(self, **kw):
        with self.assertRaises((ValueError,TypeError)):self.validate(**kw)
    def test_legacy(self):self.assertIsNone(summarize(read(fixture())[0],"bleus")["pass_review"])
    def test_complete(self):
        p=self.validate();a=p["actions"][0];self.assertEqual(p["teams"]["bleus"]["completed"],1)
        self.assertEqual(a["release_to_control_evidence_s"],[.4,.48])
        self.assertIsNone(p["teams"]["bleus"]["match_completion_pct"])
    def test_contact_not_control(self):self.reject(control_frame=None,control_team=None)
    def test_apparent_contact(self):self.assertEqual(self.validate(contact_state="apparent")["actions"][0]["contact_state"],"apparent")
    def test_contact_state(self):self.reject(contact_state="unknown")
    def test_same_receiver(self):self.reject(distinct_receiver=False)
    def test_no_continuity(self):self.reject(direct_sequence=False)
    def test_opponent_receiver(self):self.reject(control_team="blancs")
    def test_order(self):self.reject(control_frame=19)
    def test_contact_before_release(self):self.reject(contact_frame=19)
    def test_invalid_frame(self):self.reject(release_first_free_frame=True)
    def test_outside_window(self):self.reject(control_frame=50)
    def test_no_delivery(self):self.reject(delivery="not_applicable")
    def test_candidate_cannot_score(self):self.reject(state="candidate")
    def test_not_pass_cannot_score(self):self.reject(state="not_pass")
    def test_wrong_team_link(self):self.reject(team="blancs",control_team="blancs")
    def test_bad_evidence_path(self):self.reject(evidence=["../private.jpg"])
    def test_later_shot_link(self):self.reject(related_event_id="unknown")
    def test_water_not_loss(self):
        p=self.validate(outcome="unknown",contact_frame=None,contact_state="unknown",control_frame=None,control_team=None,
            direct_sequence=None,delivery="unknown",water_seen_frame=33,related_event_id=None,event_relation=None)
        self.assertEqual(p["teams"]["bleus"]["unknown_outcomes"],1)
        self.assertIsNone(p["teams"]["bleus"]["match_turnover_count"])
        self.assertEqual(p["teams"]["bleus"]["intercepted"],0)
    def test_interception(self):
        p=self.validate(outcome="intercepted",control_team="blancs",related_event_id=None,event_relation=None)
        self.assertEqual(p["teams"]["bleus"]["intercepted"],1)
        self.reject(outcome="intercepted",control_team="blancs",direct_sequence=None,related_event_id=None,event_relation=None)
    def test_deflection(self):
        p=self.validate(outcome="deflected_retained",deflection_observed=True,related_event_id=None,event_relation=None)
        self.assertEqual(p["teams"]["bleus"]["deflected_retained"],1)
        self.reject(outcome="completed",deflection_observed=True)
    def test_out(self):
        p=self.validate(outcome="out_of_play",control_frame=None,control_team=None,related_event_id=None,event_relation=None)
        self.assertEqual(p["teams"]["bleus"]["out_of_play"],1)
        self.assertIsNone(p["teams"]["bleus"]["match_turnover_count"])
    def test_overlap(self):
        p=sample();a=p["reference"]["pass_review"]["actions"][0]
        p["reference"]["pass_review"]["actions"].append(dict(a,id="PA2"))
        with self.assertRaises(ValueError):read(p)
    def test_duplicate(self):
        p=sample();p["reference"]["pass_review"]["actions"]*=2
        with self.assertRaises(ValueError):read(p)
    def test_schema_bool(self):
        p=sample();p["reference"]["pass_review"]["version"]=True
        with self.assertRaises(ValueError):read(p)
    def test_claim_complete(self):
        p=sample();p["reference"]["pass_review"]["coverage_complete"]=True
        with self.assertRaises(ValueError):read(p)
    def test_bad_fps(self):
        p=sample();p["reference"]["pass_review"]["fps"]=0
        with self.assertRaises(ValueError):read(p)
    def test_template(self):
        s=summarize(read(sample())[0],"bleus")
        env=Environment(loader=FileSystemLoader("source/templates"),autoescape=select_autoescape())
        h=env.get_template("review_reference_report.html").render(snapshot={"review_references":[dict(period=1,digest="a"*64,report=s)]})
        self.assertIn("Passes — référence vidéo partielle",h);self.assertIn("&lt;script&gt;",h);self.assertNotIn("<script>",h)
        self.assertIn("PA1",h)

    def manifest(self):
        p=sample();p["reference"]["evidence_manifest"]=[
            dict(id="G1",kind="source",path="preuves/goal.jpg",sha256="a"*64,bytes=100),
            dict(id="P1",kind="interval",path="preuves/interval.jpg",sha256="b"*64,bytes=100),
            dict(id="PA1",kind="pass",path="preuves/fixture.jpg",sha256="c"*64,bytes=100)]
        return p
    def test_manifest(self):
        p=self.manifest()
        s=summarize(read(p)[0],"bleus")["evidence_manifest"]
        self.assertEqual(s["entries"],3);self.assertFalse(s["files_verified_on_server"])
    def test_manifest_missing(self):
        p=self.manifest();p["reference"]["evidence_manifest"].pop()
        with self.assertRaises(ValueError):read(p)
    def test_manifest_path_escape(self):
        p=self.manifest();p["reference"]["evidence_manifest"][0]["path"]="preuves/../goal.jpg"
        with self.assertRaises(ValueError):read(p)
    def test_manifest_conflict(self):
        p=self.manifest();p["reference"]["evidence_manifest"][1]["path"]="preuves/goal.jpg"
        with self.assertRaises(ValueError):read(p)
    def test_manifest_shared(self):
        p=self.manifest();p["reference"]["evidence_manifest"][1].update(path="preuves/goal.jpg",sha256="a"*64)
        self.assertEqual(summarize(read(p)[0],"bleus")["evidence_manifest"]["distinct_paths"],2)
    def test_manifest_duplicate(self):
        p=self.manifest();p["reference"]["evidence_manifest"].append(copy.deepcopy(p["reference"]["evidence_manifest"][0]))
        with self.assertRaises(ValueError):read(p)

    def two_passes(self, **kw):
        p=sample()
        rows=p["reference"]["pass_review"]["actions"]
        rows.append(dict(rows[0],id="PA2",release_last_held_frame=33,
            release_first_free_frame=34,contact_frame=35,control_frame=36,
            related_event_id=None,event_relation=None))
        rows[1].update(kw)
        return p
    def test_sequential_direct_passes(self):
        self.assertEqual(summarize(read(self.two_passes())[0],"bleus")["pass_review"]["teams"]["bleus"]["completed"],2)
    def test_release_before_previous_control(self):
        with self.assertRaises(ValueError):
            read(self.two_passes(release_last_held_frame=28,release_first_free_frame=29))
    def test_duplicate_direct_shot_link(self):
        with self.assertRaises(ValueError):
            read(self.two_passes(related_event_id="G1",event_relation="precedes_shot"))

    def test_temporal_link_not_assist(self):
        a=self.validate()["actions"][0]
        self.assertEqual(a["shot_link_status"],"temporal_only")
        self.assertFalse(a["key_pass_verified"])
        self.assertFalse(a["assist_verified"])
