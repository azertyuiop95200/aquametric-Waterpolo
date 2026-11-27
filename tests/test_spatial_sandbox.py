import unittest
from copy import deepcopy
from services.spatial_sandbox import sandbox

def baseline():
    return dict(source="manual_video",decision_second=21.,length_m=25.,width_m=20.,goal_x=25.,
        start=[17.,10.,1.],sigma_m=.15,complete_defence=True,chosen="real",
        defenders=[dict(id="D",position=[21.,10.,1.3],velocity=[0,0,0],radius=.65,confidence=1.)],
        options=[dict(id="real",kind="shot",target=[25.,10.,.5],duration_s=.5),
                 dict(id="pass",kind="pass",target=[17.,15.,1.],duration_s=.5)])

class SandboxTests(unittest.TestCase):
    def test_baseline_immutable(self):
        b=baseline(); original=deepcopy(b)
        r=sandbox(b,dict(start=[17,11,1]),trials=16)
        self.assertEqual(b,original)
        self.assertEqual(r["mode"],"coach_hypothesis")
        self.assertEqual(r["start"],(17.,11.,1.))
        self.assertTrue(all(o["hypothetical"] for o in r["options"]))
    def test_moving_defender_opens_lane(self):
        b=baseline(); a=sandbox(b,dict(suggest=False),16)
        d=deepcopy(b["defenders"]);d[0]["position"][1]=14
        r=sandbox(b,dict(defenders=d,suggest=False),16)
        self.assertGreater(r["options"][0]["clearance_m"],a["options"][0]["clearance_m"])
    def test_delay_and_receiver_motion(self):
        b=baseline();o=deepcopy(b["options"]);o[1]["receiver_velocity"]=[1,0,0]
        d=deepcopy(b["defenders"]);d[0]["velocity"]=[0,1,0]
        r=sandbox(b,dict(options=o,defenders=d,carrier_velocity=[1,0,0],delay_s=.5,suggest=False),16)
        self.assertEqual(r["start"],(17.5,10.,1.))
        self.assertEqual(r["defenders"][0]["position"],(21.,10.5,1.3))
        self.assertEqual(r["options"][1]["target"],(18.,15.,1.))
    def test_generated_options(self):
        r=sandbox(baseline(),{},16)
        self.assertTrue(any(o["generated"] and o["kind"]=="shot" for o in r["options"]))
        self.assertTrue(any(o["generated"] and o["kind"]=="pass" for o in r["options"]))
        self.assertTrue(all(o["goal_probability"] is None for o in r["options"]))
        self.assertLessEqual(len(r["options"]),12)
    def test_unknown_defence(self):
        b=baseline();b["complete_defence"]=False
        self.assertTrue(all(o["clearance_frequency"] is None for o in sandbox(b,{},16)["options"]))
    def test_reject_out_of_pool(self):
        with self.assertRaises(ValueError):sandbox(baseline(),dict(start=[25,10,1],carrier_velocity=[1,0,0],delay_s=1),16)
    def test_reject_roster_changes(self):
        with self.assertRaises(ValueError):sandbox(baseline(),dict(defenders=[]),16)
    def test_no_generation(self):
        self.assertEqual(len(sandbox(baseline(),dict(suggest=False),16)["options"]),2)

if __name__=="__main__":unittest.main()
