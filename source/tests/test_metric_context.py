import unittest
from services.metric_context import event_geometry,phase_mobility

def p(n=8,s="for",x=2,X=3,y=0):
    return {"side":s,"cap_number":n,"accepted_edges":[{"start_second":0,"end_second":1,"x0":x,"y0":y,"x1":X,"y1":y}]}
def m(n,s="for"):
    return {"status":"new_candidate","match":{"side":s,"cap_number":n}}
def e(kind="pass_complete",**kw):
    return dict(key="a",counted=True,side="for",cap_number=8,receiver_cap_number=2,event_type=kind,actor_position={"second":.25},receiver_position={"second":.75},spatial_attribution={"actor":m(8),"receiver":m(2)})|kw
class ContextTests(unittest.TestCase):
    def test_pass_endpoints(self):
        r=event_geometry([e()],[p(),p(2,x=6,X=7)])["rows"][0]
        self.assertEqual(r["endpoint_separation_m"],4.5)
        self.assertEqual(r["observed_interval_s"],.5)
    def test_shot_both_goals(self):
        r=event_geometry([e("goal")],[p()])["rows"][0]
        self.assertEqual([x["range_m"] for x in r["goal_geometry"]],[2.25,22.75])
    def test_opponent_gap(self):
        r=event_geometry([e("goal")],[p(),p(8,"against",x=4,X=5)])["rows"][0]
        self.assertEqual(r["nearest_measured_opponent_m"],2)
    def test_missing_opponent_not_zero(self):
        self.assertIsNone(event_geometry([e("goal")],[p()])["rows"][0]["nearest_measured_opponent_m"])
    def test_missing_match(self):
        self.assertFalse(event_geometry([e(spatial_attribution={})],[p()])["rows"])
    def test_gap(self):
        self.assertFalse(event_geometry([e(actor_position={"second":2})],[p()])["rows"])
    def test_duplicate(self):
        self.assertEqual(len(event_geometry([e(),e()],[p()])["rows"]),1)
    def test_receiver_before_actor(self):
        r=event_geometry([e(receiver_position={"second":.1})],[p(),p(2,x=6,X=7)])["rows"][0]
        self.assertNotIn("endpoint_separation_m",r)
    def test_phase_partition(self):
        spans=[{"start_second":0,"end_second":.25,"side":"for"},{"start_second":.5,"end_second":.75,"side":"against"}]
        r=phase_mobility([p()],spans,source_revision="a",possession_revision="a")["players"][0]
        self.assertEqual([r[k]["distance_m"] for k in ("attack","defence","unknown","total")],[.25,.25,.5,1])
    def test_source_mismatch(self):
        self.assertEqual(phase_mobility([p()],[],source_revision="a",possession_revision="b")["scope"],"source_unmatched")
    def test_no_possession(self):
        r=phase_mobility([p()],[],source_revision="a",possession_revision="a")["players"][0]
        self.assertIsNone(r["attack"]["distance_m"]);self.assertEqual(r["unknown"]["distance_m"],1)
    def test_conflicting_possessions(self):
        s={"start_second":0,"end_second":1,"side":"for"}
        self.assertEqual(phase_mobility([p()],[s,s],source_revision="a",possession_revision="a")["scope"],"conflicting_possessions")
