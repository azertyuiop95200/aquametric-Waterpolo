import json, unittest, copy
from services.review_reference_import import load, locate, summarize, MAX_BYTES
from jinja2 import Environment, FileSystemLoader, select_autoescape

def fixture():
    e=dict(event_id="G1",period=1,team_before="bleus",source_kind="shot",source_review_state="reference_single_review",cause="goal",cause_verified=True,video_start_s=2,video_end_s=2.2,source_observation="<script>")
    i=dict(interval_id="P1",period=1,start_s=3.6,end_s=5.1,before_team="blancs",after_team="bleus",before_state="observed",after_state="observed",cause="unknown",cause_verified=False,decision_verified=False,single_transition_verified=False,linked_prior_shot=False,linked_prior_event="G1",observation="Contrôles opposés")
    s=lambda file,start,end:dict(file=file,sha256="a"*64,bytes=100,start_s=start,end_s=end,first_local_pts_s=0.08)
    return dict(format="aquametric-review-v1",timeline=dict(duration_s=8,segments=[s("a.mp4",0,4),s("b.mp4",4,8)]),reference=dict(schema_version="2.1",source_duration_s=8,coverage_complete=False,events=[e],possession_review_intervals=[i]))
def read(p): return load(json.dumps(p).encode())

class ReviewImportTests(unittest.TestCase):
    def test_import(self):
        p,_,digest,q=read(fixture());self.assertEqual(q,1);self.assertEqual(len(digest),64)
        s=summarize(p,"bleus");self.assertEqual(s["verified_match_event_count"],0)
        self.assertEqual(s["events"][0]["side"],"Notre équipe")
        self.assertEqual(s["intervals"][0]["status"],"opposite_endpoints")
    def test_color_mapping(self):self.assertEqual(summarize(fixture(),"blancs")["events"][0]["side"],"Adversaire")
    def test_hash_stable(self):
        p=fixture();self.assertEqual(read(p)[2],load(json.dumps(p,indent=2).encode())[2])
    def test_cross_segment(self):
        s=summarize(fixture(),"blancs")["intervals"][0]
        self.assertEqual(s["location_start"]["part"],1);self.assertEqual(s["location_end"]["part"],2)
        self.assertEqual(s["location_end"]["local_s"],1.1)
    def test_boundary(self):self.assertEqual(locate(fixture()["timeline"],4)["part"],2)
    def test_gap(self):
        p=fixture();p["timeline"]["segments"][1]["start_s"]=4.1
        with self.assertRaises(ValueError):read(p)
    def test_duplicate(self):
        p=fixture();p["reference"]["events"]*=2
        with self.assertRaises(ValueError):read(p)
    def test_out_of_bounds(self):
        p=fixture();p["reference"]["events"][0]["video_end_s"]=8
        with self.assertRaises(ValueError):read(p)
    def test_dangling_link(self):
        p=fixture();p["reference"]["possession_review_intervals"][0]["linked_prior_event"]="missing"
        with self.assertRaises(ValueError):read(p)
    def test_full_claim(self):
        p=fixture();p["reference"]["coverage_complete"]=True
        with self.assertRaises(ValueError):read(p)
    def test_boolean(self):
        p=fixture();p["reference"]["events"][0]["cause_verified"]="false"
        with self.assertRaises(ValueError):read(p)
    def test_limit(self):
        with self.assertRaises(ValueError):load(b" "* (MAX_BYTES+1))
    def test_nan(self):
        p=fixture();p["reference"]["events"][0]["video_end_s"]=float("nan")
        with self.assertRaises(ValueError):read(p)
    def test_template(self):
        env=Environment(loader=FileSystemLoader("source/templates"),autoescape=select_autoescape())
        p=summarize(fixture(),"bleus")
        h=env.get_template("review_reference_report.html").render(snapshot={"review_references":[dict(period=1,digest="a"*64,report=p)]})
        self.assertIn("Contrôles opposés",h);self.assertIn("&lt;script&gt;",h);self.assertNotIn("<script>",h)
        self.assertIn("Aucune référence",env.get_template("review_reference_report.html").render(snapshot={"review_references":[]}))
        self.assertIn("review-reference",env.get_template("review_reference_form.html").render(match={"id":1,"team":{"name":"Équipe"}}))
