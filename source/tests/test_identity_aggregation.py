import unittest
from services.identity_aggregation import build_identity_report,distance_union,validate_reviews

def tr(i,offset=0):
    return {"id":i,"colour":"light","segments":[[{"second":j/8,"x_m":j/8+offset,"y_m":0} for j in range(9)]]}
def review(side,cap):
    return {"side":side,"cap_number":cap,"colour":"white","evidence":"bonnet visible","provenance":"coach_review"}
def evt(i,side,kind,pid=None):
    return {"id":i,"second":i,"perspective":side,"event_type":kind,"confidence":"CONFIRMED","player_id":pid}
class IdentityTests(unittest.TestCase):
    def test_overlap_and_conflict(self):
        self.assertEqual(distance_union([tr(1),tr(2)])["distance_m"],1)
        self.assertIsNone(distance_union([tr(1),tr(2,3)])["distance_m"])
        self.assertEqual(distance_union([tr(1),tr(2,3)])["conflict_seconds"],1)
    def test_same_cap_opposite_teams_and_unassigned(self):
        metric={"tracks":[tr(1),tr(2),tr(3),tr(4)]}
        events=[evt(1,"for","goal",10),evt(2,"against","shot_off_target"),evt(3,"for","shot_off_target")]
        reviews={"tracks":{"1":review("for",4),"2":review("for",4),"3":review("against",4)},"events":{"2":review("against",4)}}
        r=build_identity_report(metric,events,{},[{"id":10,"cap_number":4,"name":"A"}],reviews)
        self.assertEqual(len(r["players"]),2)
        self.assertEqual(r["teams"]["for"]["distance_m"],1)
        self.assertEqual(r["teams"]["against"]["distance_m"],1)
        self.assertEqual(r["teams"]["for"]["stats"]["shot_conversion"],50)
        self.assertEqual(r["teams"]["for"]["unassigned_events"],1)
        self.assertEqual(r["unassigned_tracks"],1)
    def test_unassigned_not_zero_and_conflicting_side(self):
        r=build_identity_report({"tracks":[tr(1)]},[],{},[],{})
        self.assertIsNone(r["teams"]["for"]["distance_m"])
        with self.assertRaises(ValueError):validate_reviews({"events":{"1":review("against",4)}},{},{"1":"for"},{})
    def test_reject_duplicate_roster_cap(self):
        r=build_identity_report({},[evt(1,"for","goal",10)],{},[{"id":10,"cap_number":4,"name":"A"},{"id":11,"cap_number":4,"name":"B"}],{"events":{"1":review("for",4)}})
        self.assertFalse(r["players"])
