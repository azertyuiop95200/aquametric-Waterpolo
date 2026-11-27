import unittest
from copy import deepcopy
from services.spatial_replay import review

def scene():
    return dict(source="manual_video",decision_second=21.,length_m=25.,width_m=20.,goal_x=25.,
        start=[17.,10.,1.],sigma_m=.15,complete_defence=True,chosen="real",
        defenders=[dict(id="D",position=[21.,10.,1.3],velocity=[0,0,0],radius=.65,confidence=1.)],
        options=[dict(id="real",kind="shot",target=[25.,10.,.5],duration_s=.5),
                 dict(id="pass",kind="pass",target=[17.,15.,1.],duration_s=.5)])

class ReviewTests(unittest.TestCase):
    def test_compare_and_reproducibility(self):
        a=review(scene(),trials=32)
        b=review(scene(),trials=32)
        self.assertEqual(a,b)
        self.assertLess(a["options"][0]["clearance_frequency"],a["options"][1]["clearance_frequency"])
        for o in a["options"]:
            self.assertIsNone(o["goal_probability"])
            self.assertIsNone(o["pass_completion_probability"])
            self.assertTrue(0<=o["simulation_interval"][0]<=o["simulation_interval"][1]<=1)
    def test_missing_coverage(self):
        x=scene();x["complete_defence"]=False
        for o in review(x,16)["options"]:
            self.assertEqual(o["status"],"unknown")
            self.assertIsNone(o["clearance_frequency"])
            self.assertIsNone(o["clearance_m"])
    def test_unknown_uncertainty(self):
        x=scene();x["sigma_m"]=0
        self.assertIsNone(review(x,16)["options"][0]["clearance_frequency"])
    def test_off_target_actual_shot(self):
        x=scene();x["options"][0]["target"]=[25.,14.,.7]
        self.assertFalse(review(x,16)["options"][0]["target_in_goal"])
    def test_illegal_alternative_goal_target(self):
        x=scene();x["options"][1].update(kind="shot",target=[25.,14.,.7])
        with self.assertRaises(ValueError):review(x,16)
    def test_invalid_nonfinite(self):
        x=scene();x["start"][0]=float("nan")
        with self.assertRaises(ValueError):review(x,16)
    def test_duplicate(self):
        x=scene();x["options"][1]["id"]="real"
        with self.assertRaises(ValueError):review(x,16)
    def test_no_defenders(self):
        x=scene();x["defenders"]=[]
        self.assertFalse(review(x,16)["complete_defence"])
    def test_mirror(self):
        x=scene();a=review(x,16)
        x["start"][0]=25-x["start"][0];x["goal_x"]=0
        for d in x["defenders"]:d["position"][0]=25-d["position"][0]
        for o in x["options"]:o["target"][0]=25-o["target"][0]
        b=review(x,16)
        self.assertAlmostEqual(a["options"][0]["clearance_m"],b["options"][0]["clearance_m"])

    def test_reach_geometry_survives_replay_and_sandbox(self):
        from services.spatial_sandbox import sandbox
        x=scene()
        x["defenders"][0].update(position=[21.,11.3,1.],radius=.3)
        x["options"][0]["duration_s"]=.3
        a=review(x,32)
        x["defenders"][0]["reach_segments"]=[dict(part="left_arm",start_offset=[0,0,0],end_offset=[0,-1.3,0],radius=.12)]
        b=review(x,32)
        self.assertLess(b["options"][0]["clearance_m"],a["options"][0]["clearance_m"])
        self.assertLessEqual(b["options"][0]["clearance_frequency"],a["options"][0]["clearance_frequency"])
        self.assertEqual(b["options"][0]["closest_part"],"left_arm")
        self.assertEqual(b["defenders"][0]["reach_segments"][0]["part"],"left_arm")
        c=sandbox(x,dict(suggest=False),32)
        self.assertEqual(c["options"][0]["closest_part"],"left_arm")
        x["complete_defence"]=False
        self.assertIsNone(review(x,16)["options"][0]["closest_part"])

if __name__=="__main__":unittest.main()
