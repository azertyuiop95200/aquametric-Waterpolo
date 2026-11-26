import unittest
from services.spatial_attribution import attribute_events,SpatialAttribution
def track(i,x):
    return {"id":i,"points":[{"second":0.1*j,"x":x,"y":.5} for j in range(11)]}
def review(n,side="for"):
    return {"side":side,"cap_number":n,"provenance":"coach_review","evidence":"number visible"}
def pos(x=.3,t=.5):return {"second":t,"x":x,"y":.5,"evidence":"head visible"}
def event(**kw):
    return dict(counted=True,side="for",event_type="pass_complete",cap_number=None,actor_position=pos(),source_revision="a")|kw
class SpatialTests(unittest.TestCase):
    def report(self,events,tracks=None,reviews=None,revision="a"):
        tracks=tracks if tracks is not None else [track(1,.3)]
        return attribute_events(events,{"tracks":tracks,"source_revision":"a"},{"tracks":tracks,"source_revision":revision},{"tracks":reviews if reviews is not None else {"1":review(8)}})
    def test_new(self):
        r=self.report([event()]);self.assertEqual(r["events"][0]["cap_number"],8);self.assertEqual(r["counts"]["actor_new_candidate"],1)
    def test_unreviewed_competitor(self):
        r=self.report([event()],tracks=[track(1,.3),track(2,.304)])
        self.assertIsNone(r["events"][0]["cap_number"]);self.assertEqual(r["counts"]["actor_ambiguous"],1)
    def test_no_bridge(self):
        a=track(1,.3);a["points"]=a["points"][:2]+a["points"][-2:]
        self.assertEqual(self.report([event()],tracks=[a])["counts"]["actor_no_track"],1)
    def test_source_mismatch(self):
        self.assertIsNone(self.report([event()],revision="b")["events"][0]["cap_number"])
    def test_conflicting_direct_cap(self):
        r=self.report([event(cap_number=9)]);self.assertIsNone(r["events"][0]["cap_number"]);self.assertEqual(r["counts"]["actor_identity_conflict"],1)
    def test_receiver_time(self):
        r=self.report([event(receiver_position=pos(.5,.8))],tracks=[track(1,.3),track(2,.5)],reviews={"1":review(8),"2":review(2)})
        self.assertEqual(r["events"][0]["receiver_cap_number"],2);self.assertEqual(r["pass_ledger"]["teams"]["for"]["network"],[{"from":8,"to":2,"count":1}])
    def test_duplicate_identity(self):
        r=self.report([event()],tracks=[track(1,.3),track(2,.5)],reviews={"1":review(8),"2":review(8)})
        self.assertEqual(r["counts"]["actor_duplicate_identity"],1)
    def test_opposing_receiver(self):
        r=self.report([event(receiver_position=pos(.5,.8))],tracks=[track(1,.3),track(2,.5)],reviews={"1":review(8),"2":review(2,"against")})
        self.assertIsNone(r["events"][0]["receiver_cap_number"])
    def test_replay(self):
        self.assertEqual(self.report([event(is_replay=True)])["events"],[])

    def test_actor_conflict_blocks_receiver(self):
        r=self.report([event(cap_number=9,receiver_position=pos(.5,.8))],tracks=[track(1,.3),track(2,.5)],reviews={"1":review(8),"2":review(2)})
        self.assertIsNone(r["events"][0]["receiver_cap_number"])
        self.assertEqual(r["counts"]["receiver_actor_conflict"],1)
