import unittest
from services.decision_space import gap,geometry,scene_options,decision_report
class DecisionTests(unittest.TestCase):
    def test_segment_not_infinite_line(self):
        self.assertAlmostEqual(gap((0,0),(2,0),(4,1)),5**.5)
    def test_angle_central(self):
        self.assertAlmostEqual(geometry((3,0),0)["angle_deg"],53.130102,places=5)
    def test_goal_plane_undefined(self):
        self.assertIsNone(geometry((0,0),0)["angle_deg"])
    def test_no_opponents_unknown(self):
        r=scene_options((8,0),[(2,(4,1))],[],0)
        self.assertIsNone(r["actor_shot"]["sampled_unobstructed_fraction"])
        self.assertIsNone(r["alternatives"][0]["lane_min_gap_m"])
        self.assertFalse(r["alternatives"][0]["pareto_candidate"])
    def test_blocked_lane(self):
        r=scene_options((8,0),[(2,(4,0))],[(6,0)],0)
        self.assertEqual(r["alternatives"][0]["lane_min_gap_m"],0)
        self.assertEqual(r["alternatives"][0]["lane_scenario"],"near_measured_defender")
    def test_direction_reverses_gain(self):
        a=scene_options((8,0),[(2,(4,0))],[(6,2)],0)["alternatives"][0]
        b=scene_options((8,0),[(2,(4,0))],[(6,2)],25)["alternatives"][0]
        self.assertEqual((a["longitudinal_gain_m"],b["longitudinal_gain_m"]),(4,-4))
    def test_no_future_player(self):
        def p(n,a,b):return {"side":"for","cap_number":n,"accepted_edges":[{"start_second":a,"end_second":b,"x0":4,"y0":0,"x1":4,"y1":0}]}
        e={"key":"a","counted":True,"event_type":"bad_pass","side":"for","cap_number":8,"actor_position":{"second":.5},"spatial_attribution":{"actor":{"status":"corroborated","match":{"side":"for","cap_number":8}}}}
        r=decision_report([e],[p(8,0,1),p(2,1,2)])["rows"][0]
        self.assertEqual(len(r["points"]),1)
        self.assertFalse(r["direction_verified"]);self.assertFalse(r["failed_pass_target_known"])
    def test_duplicate_and_replay(self):
        self.assertFalse(decision_report([{"key":"a","event_type":"bad_pass","counted":True,"is_replay":True}],[])["rows"])
