import unittest
from services.control_mobility import control_mobility
def player():
    return {"side":"for","cap_number":8,"accepted_edges":[{"start_second":0,"end_second":1,"x0":0,"y0":0,"x1":2,"y1":0}]}
def span(a,b,side="for",n=8,status="identified"):
    return {"start_second":a,"end_second":b,"side":side,"cap_number":n,"status":status}
class ControlMobilityTests(unittest.TestCase):
    def report(self,rows,p=None,revision="x"):
        return control_mobility([p or player()],{"intervals":rows},source_revision="x",control_revision=revision)
    def test_partial_partition(self):
        r=self.report([span(.25,.5),span(.5,.75,n=9)])["players"][0]
        self.assertEqual((r["with_ball_m"],r["other_controller_m"],r["unknown_control_m"]),(0.5,0.5,1))
    def test_unobserved_not_without_ball(self):
        r=self.report([])["players"][0];self.assertIsNone(r["with_ball_m"]);self.assertIsNone(r["other_controller_m"]);self.assertEqual(r["unknown_control_m"],2)
    def test_conflict(self):
        self.assertEqual(self.report([span(0,.6),span(.5,1)])["scope"],"conflicting_control_intervals")
    def test_different_source(self):
        self.assertEqual(self.report([],revision="y")["scope"],"source_unmatched")
    def test_unknown_cap(self):
        r=self.report([span(0,1,n=None,status="unresolved_cap")])["players"][0];self.assertEqual(r["unknown_control_m"],2)
    def test_other_team_same_number(self):
        r=self.report([span(0,1,side="against")])["players"][0];self.assertEqual(r["other_controller_m"],2)
    def test_stationary(self):
        p=player();p["accepted_edges"][0]["x1"]=0
        self.assertEqual(self.report([span(0,1)],p)["players"][0]["with_ball_m"],0)
