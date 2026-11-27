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

    def conflict_sample(self, state="observed", start=1.5, end=1.8):
        p=sample()
        i=p["reference"]["possession_review_intervals"][0]
        i.update(start_s=start,end_s=end,before_state=state,after_team="bleus")
        return summarize(read(p)[0],"bleus")["pass_review"]["actions"][0]
    def test_observed_opponent_conflict(self):
        a=self.conflict_sample()
        self.assertEqual(a["shot_link_status"],"opponent_control_observed")
        self.assertEqual(a["shot_link_conflict_ids"],["P1"])
        self.assertFalse(a["key_pass_verified"])
        self.assertFalse(a["assist_verified"])
    def test_apparent_opponent_not_conflict(self):
        a=self.conflict_sample(state="apparent")
        self.assertEqual(a["shot_link_status"],"temporal_only")
        self.assertEqual(a["shot_link_conflict_ids"],[])
    def test_opponent_outside_gap(self):
        a=self.conflict_sample(start=2.3,end=2.5)
        self.assertEqual(a["shot_link_status"],"temporal_only")
    def test_conflict_at_shot_boundary(self):
        self.assertEqual(self.conflict_sample(start=2,end=2.1)["shot_link_status"],"opponent_control_observed")
    def test_conflict_rendered(self):
        p=sample()
        p["reference"]["possession_review_intervals"][0].update(start_s=1.5,end_s=1.8)
        s=summarize(read(p)[0],"bleus")
        env=Environment(loader=FileSystemLoader("source/templates"),autoescape=select_autoescape())
        h=env.get_template("review_reference_report.html").render(snapshot={"review_references":[dict(period=1,digest="a"*64,report=s)]})
        self.assertIn("Contrôle adverse observé",h)
        self.assertIn("Fenêtres contradictoires : P1",h)

    def test_quality_independent_of_success(self):
        p=self.validate(accuracy="inaccurate",reception_quality="adjusted")
        s=p["teams"]["bleus"]
        self.assertEqual(s["completed"],1)
        self.assertEqual(s["accuracy_counts"]["inaccurate"],1)
        self.assertEqual(s["reception_quality_counts"]["adjusted"],1)
        self.assertEqual(s["observed_resolved_completion_pct"],100)
        self.assertIsNone(s["match_completion_pct"])
    def test_clean_requires_first_contact_control(self):
        self.reject(reception_quality="clean")
        self.assertEqual(self.validate(reception_quality="clean",control_frame=30)["actions"][0]["reception_quality"],"clean")
    def test_legacy_quality_unknown(self):
        self.assertEqual(self.validate()["teams"]["bleus"]["accuracy_counts"],{"unknown":1})
    def test_unknown_not_failure(self):
        p=self.validate(outcome="unknown",contact_frame=None,contact_state="unknown",control_frame=None,control_team=None,related_event_id=None,event_relation=None)
        s=p["teams"]["bleus"]
        self.assertEqual(s["confirmed_failed"],0)
        self.assertEqual(s["unclassified_completion"],1)
        self.assertIsNone(s["observed_resolved_completion_pct"])
    def test_deflection_not_automatically_failed(self):
        s=self.validate(outcome="deflected_retained",deflection_observed=True,defensive_intervention="deflected",related_event_id=None,event_relation=None)["teams"]["bleus"]
        self.assertEqual(s["confirmed_failed"],0)
        self.assertEqual(s["unclassified_completion"],1)
    def test_invalid_quality(self):
        self.reject(accuracy="perfect")
        self.reject(defensive_intervention="deflected")
        self.reject(reception_quality="failed")

    def arrival(self, **kw):
        return dict(state="arrival_only",team=None,arrival_first_frame=22,
            release_last_held_frame=None,release_first_free_frame=None,
            outcome="unknown",distinct_receiver=None,direct_sequence=None,
            sender_role="unknown",related_event_id=None,event_relation=None,**kw)
    def test_arrival_control_not_pass(self):
        p=self.validate(**self.arrival());a=p["actions"][0]
        self.assertEqual(a["arrival_to_control_evidence_s"],.4)
        self.assertIsNone(a["release_to_control_evidence_s"])
        self.assertEqual(a["control_team"],"bleus")
        self.assertEqual(p["states"]["arrival_only"],1)
        self.assertEqual(p["teams"]["bleus"]["observed_attempts"],0)
        self.assertIsNone(p["teams"]["bleus"]["observed_resolved_completion_pct"])
    def test_arrival_no_control(self):
        p=self.validate(**self.arrival(control_frame=None,control_team=None,contact_frame=None,contact_state="unknown"))
        self.assertIsNone(p["actions"][0]["arrival_to_control_evidence_s"])
    def test_arrival_invalid_order(self):
        self.reject(**self.arrival(control_frame=21))
    def test_arrival_no_sender_or_success(self):
        a=self.arrival();a["team"]="bleus";self.reject(**a)
        a=self.arrival();a["outcome"]="completed";self.reject(**a)
        a=self.arrival();a["direct_sequence"]=True;self.reject(**a)
    def test_arrival_requires_no_release(self):
        a=self.arrival();a.update(release_last_held_frame=20,release_first_free_frame=21);self.reject(**a)
    def test_arrival_before_water(self):
        self.reject(**self.arrival(water_seen_frame=21))
    def test_arrival_render(self):
        p=self.validate(**self.arrival())
        env=Environment(loader=FileSystemLoader("source/templates"),autoescape=select_autoescape())
        html=env.get_template("pass_review_report.html").render(p={"pass_review":p,"home_color":"bleus"},ref={"period":1})
        self.assertIn("Arrivée seule, origine inconnue",html)
        self.assertIn("Arriv",html)
        self.assertIn("pas un temps de vol",html)

    def test_observed_reception_delay(self):
        self.assertEqual(self.validate()["actions"][0]["contact_to_control_evidence_s"],.08)
        self.assertEqual(self.validate(control_frame=30)["actions"][0]["contact_to_control_evidence_s"],0)
        self.assertIsNone(self.validate(contact_state="apparent")["actions"][0]["contact_to_control_evidence_s"])
        self.assertIsNone(self.validate(**self.arrival())["actions"][0]["contact_to_control_evidence_s"])
    def test_resolved_outcome_coverage(self):
        p=self.validate()
        self.assertEqual(p["teams"]["bleus"]["resolved_outcome_coverage_pct"],100)
        self.assertIsNone(p["teams"]["blancs"]["resolved_outcome_coverage_pct"])
        p=self.validate(outcome="unknown",related_event_id=None,event_relation=None)
        self.assertEqual(p["teams"]["bleus"]["resolved_outcome_coverage_pct"],0)
