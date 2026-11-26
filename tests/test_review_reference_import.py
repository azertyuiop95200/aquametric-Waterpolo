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

    def test_database_separate_reference(self):
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session
        from sqlalchemy.exc import IntegrityError
        from db import Base
        from models import Match, MatchReviewReference, Event, User, Team, Club
        engine=create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user=User(email="test@example.invalid",password_hash="test")
            db.add(user);db.flush()
            club=Club(name="Test",owner_id=user.id);db.add(club);db.flush()
            team=Team(name="Test",club_id=club.id,owner_id=user.id);db.add(team);db.flush()
            match=Match(owner_id=user.id,team_id=team.id,opponent="Other");db.add(match);db.flush()
            _,canonical,digest,period=read(fixture())
            db.add(MatchReviewReference(match_id=match.id,period=period,digest=digest,home_color="bleus",payload_json=canonical))
            db.commit()
            self.assertEqual(len(match.review_references),1)
            self.assertEqual(db.scalars(select(Event)).all(),[])
            db.add(MatchReviewReference(match_id=match.id,period=period,digest=digest,home_color="bleus",payload_json=canonical))
            with self.assertRaises(IntegrityError):db.commit()
            db.rollback()

    def test_referee_signal_not_decision(self):
        p=fixture(); i=p["reference"]["possession_review_intervals"][0]
        i.update(referee_signal_observed=True,cause_candidate="offensive foul possible")
        s=summarize(read(p)[0],"blancs")
        self.assertEqual(s["referee_signals"],1);self.assertEqual(s["confirmed_referee_decisions"],0)
        self.assertIsNone(s["intervals"][0]["attributed_cause"])
    def test_recomputed_bound_no_overlap_or_shot(self):
        p=fixture();i=p["reference"]["possession_review_intervals"][0]
        p["reference"]["possession_review_intervals"] += [dict(i,interval_id="P2",start_s=3.8,end_s=5.5),dict(i,interval_id="P3",start_s=6,end_s=7,linked_prior_shot=True)]
        s=summarize(read(p)[0],"bleus")
        self.assertEqual(s["lower_bound_excluding_linked_shots"],1)
        self.assertIsNone(s["exact_total_changes"])
    def test_signal_type_strict(self):
        p=fixture();p["reference"]["possession_review_intervals"][0]["referee_signal_observed"]="false"
        with self.assertRaises(ValueError):read(p)

    def test_revision_history(self):
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session
        from db import Base
        from models import Match, MatchReviewReference, MatchReviewRevision, Event, User, Team, Club
        from services.review_reference_revision import replace_reference
        engine=create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user=User(email="test@example.invalid",password_hash="test")
            db.add(user);db.flush()
            club=Club(name="Test",owner_id=user.id);db.add(club);db.flush()
            team=Team(name="Test",club_id=club.id,owner_id=user.id);db.add(team);db.flush()
            match=Match(owner_id=user.id,team_id=team.id,opponent="Other");db.add(match);db.flush()
            p,canonical,digest,period=read(fixture())
            prior=MatchReviewReference(match_id=match.id,period=period,digest=digest,home_color="bleus",payload_json=canonical)
            db.add(prior);db.commit()
            self.assertFalse(replace_reference(db,prior,p,canonical,digest,"bleus",""))
            changed=fixture()
            changed["reference"]["events"][0]["source_observation"]="Révision"
            payload,new_canonical,new_digest,_=read(changed)
            with self.assertRaises(ValueError):replace_reference(db,prior,payload,new_canonical,new_digest,"bleus","")
            with self.assertRaises(ValueError):replace_reference(db,prior,payload,new_canonical,new_digest,"blancs",digest)
            different=copy.deepcopy(changed);different["timeline"]["segments"][0]["sha256"]="b"*64
            d,dc,dd,_=read(different)
            with self.assertRaises(ValueError):replace_reference(db,prior,d,dc,dd,"bleus",digest)
            self.assertTrue(replace_reference(db,prior,payload,new_canonical,new_digest,"bleus",digest))
            db.commit()
            self.assertEqual(prior.digest,new_digest)
            self.assertEqual(len(prior.revisions),1)
            self.assertEqual(prior.revisions[0].digest,digest)
            self.assertEqual(prior.revisions[0].payload_json,canonical)
            self.assertEqual(db.scalars(select(Event)).all(),[])
            with self.assertRaises(ValueError):replace_reference(db,prior,p,canonical,digest,"bleus",digest)
