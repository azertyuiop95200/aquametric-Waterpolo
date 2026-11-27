import unittest
from services.possession_context import decisions
from jinja2 import Environment,FileSystemLoader
def fixture():
    e=dict(interval_id="P1",start_s=1,end_s=3,before_team="blancs",after_team="blancs",before_state="observed",after_state="observed")
    e["context_review"]=dict(next_s=4,next_team="blancs",next_kind="carry",path_consistent=True,intervening_opponent_control="not_observed",intervening_restart="not_observed",reason="Contrôle et progression",alternative="Reprise masquée possible",evidence=["preuves/a.jpg"])
    return dict(possession_review_intervals=[e],events=[],evidence_manifest=[dict(id="P1",path="preuves/a.jpg",kind="interval")])
def result(r):return decisions(r,10)["decisions"]["P1"]
class PossessionContextTests(unittest.TestCase):
    def test_retained(self):
        d=result(fixture());self.assertEqual(d["status"],"probable_retained");self.assertFalse(d["direct_transition_verified"]);self.assertIsNone(d["cause_attributed"])
    def test_apparent(self):
        r=fixture();r["possession_review_intervals"][0]["before_state"]="apparent";self.assertEqual(result(r)["status"],"probable_retained_initial_apparent")
    def test_change(self):
        r=fixture();r["possession_review_intervals"][0]["before_team"]="bleus";self.assertEqual(result(r)["status"],"change_between_observed_controls")
    def test_unknown_path(self):
        r=fixture();r["possession_review_intervals"][0]["context_review"]["path_consistent"]=None;self.assertEqual(result(r)["status"],"later_control_only")
    def test_restart(self):
        r=fixture();r["possession_review_intervals"][0]["context_review"]["intervening_restart"]="observed";self.assertEqual(result(r)["status"],"retention_not_supported")
    def test_conflict(self):
        r=fixture();r["possession_review_intervals"].append(dict(interval_id="P2",start_s=2,end_s=2.5,before_state="observed",before_team="bleus",after_state="apparent",after_team="blancs"));d=result(r);self.assertEqual(d["status"],"retention_not_supported");self.assertEqual(d["conflict_ids"],["P2"])
    def test_shot(self):
        r=fixture();r["events"].append(dict(event_id="G1",source_kind="shot",source_review_state="reference_single_review",team_before="blancs",video_start_s=4,video_end_s=4.2));r["possession_review_intervals"][0]["context_review"].update(next_kind="shot",next_event_id="G1");self.assertEqual(result(r)["next_event_id"],"G1")
        r["events"][0]["team_before"]="bleus"
        with self.assertRaises(ValueError):result(r)
    def test_proof(self):
        r=fixture();r["evidence_manifest"]=[]
        with self.assertRaises(ValueError):result(r)
    def test_time(self):
        r=fixture();r["possession_review_intervals"][0]["context_review"]["next_s"]=3
        with self.assertRaises(ValueError):result(r)
    def test_unknown_after(self):
        r=fixture();r["possession_review_intervals"][0]["after_state"]="apparent"
        with self.assertRaises(ValueError):result(r)
    def test_legacy(self):
        r=fixture();r["possession_review_intervals"][0].pop("context_review");self.assertEqual(decisions(r,10)["decisions"],{})

    def test_conflicting_endpoint_overrides_change(self):
        r=fixture();r["possession_review_intervals"][0]["before_team"]="bleus"
        r["possession_review_intervals"].append(dict(interval_id="P2",start_s=3,end_s=5,before_state="observed",before_team="bleus",after_state="apparent",after_team="blancs"))
        d=result(r);self.assertEqual(d["status"],"endpoint_conflict");self.assertEqual(d["endpoint_conflict_ids"],["P2"])
    def test_null_legacy_manifest(self):
        r=fixture();r["possession_review_intervals"][0].pop("context_review");r["evidence_manifest"]=None
        self.assertEqual(decisions(r,10)["decisions"],{})
    def test_separate_ledger(self):
        r=fixture();r["possession_context_fps"]=25;r["evidence_manifest"][0].update(sha256="a"*64,bytes=100)
        r["possession_context_review_windows"]=[dict(id="W1",first_frame=25,last_frame=75,step_frames=5,view="full_frame",sample_count=11,sheets=[dict(path="preuves/a.jpg",sha256="a"*64,bytes=100)])]
        self.assertEqual(decisions(r,10)["review_coverage"]["distinct_full_frame_samples"],11)
        r["possession_context_review_windows"][0]["sheets"][0]["sha256"]="b"*64
        with self.assertRaises(ValueError):decisions(r,10)
