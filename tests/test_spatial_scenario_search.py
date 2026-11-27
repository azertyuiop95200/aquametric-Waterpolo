import unittest
from copy import deepcopy
from services.spatial_sandbox import sandbox
from services.spatial_scenario_search import search_scenarios

def baseline():
    return dict(source="manual_video",decision_second=21.,length_m=25.,width_m=20.,goal_x=25.,
        start=[17.,10.,1.],sigma_m=.15,complete_defence=True,chosen="real",
        defenders=[dict(id="D",position=[21.,10.,1.3],velocity=[0,0,0],radius=.65,confidence=1.)],
        options=[dict(id="real",kind="shot",target=[25.,10.,.5],duration_s=.5),
                 dict(id="pass",kind="pass",target=[17.,15.,1.],duration_s=.5)])

class ScenarioSearchTests(unittest.TestCase):
    def test_acceleration(self):
        b=baseline();d=deepcopy(b["defenders"]);d[0]["acceleration"]=[0,1,0]
        r=sandbox(b,dict(delay_s=1.,carrier_acceleration=[1,0,0],defenders=d,suggest=False),16)
        self.assertEqual(r["start"],(17.5,10.,1.))
        self.assertEqual(r["defenders"][0]["position"],(21.,10.5,1.3))
        self.assertEqual(r["defenders"][0]["velocity"],(0.,1.,0.))
    def test_acceleration_bound(self):
        with self.assertRaises(ValueError):sandbox(baseline(),dict(delay_s=3,carrier_acceleration=[2,0,0]),16)
    def test_search_does_not_change_baseline(self):
        b=baseline();old=deepcopy(b); edits={};r=search_scenarios(b,edits)
        self.assertEqual(b,old);self.assertEqual(edits,{})
        self.assertEqual(len(r["scenarios"])+len(r["rejected"]),18)
        self.assertEqual(r["trials_per_option"],16)
        self.assertEqual(sum(s["reaction_sensitivity"] for s in r["scenarios"]),2)
    def test_search_missing_defence(self):
        b=baseline();b["complete_defence"]=False;r=search_scenarios(b,{})
        self.assertTrue(all(s["best_shot"] is None and s["best_pass"] is None for s in r["scenarios"]))
    def test_off_target_not_selected(self):
        b=baseline();b["options"][0]["target"]=[25,15,.5]
        r=search_scenarios(b,{})
        self.assertTrue(all(s["best_shot"] is None or s["best_shot"]["id"]!="real" for s in r["scenarios"]))

    def test_interception_exact_horizontal_speed(self):
        from math import hypot
        from services.spatial_sandbox import intercept_time
        t=intercept_time([0,0,1],[6,0,1],[2,1,0],12)
        self.assertIsNotNone(t)
        self.assertAlmostEqual(hypot(6+2*t,t),12*t,places=8)
        self.assertAlmostEqual(intercept_time([0,0,1],[6,0,1],[0,0,0],12),.5)
        self.assertIsNone(intercept_time([0,0,1],[20,0,1],[0,0,0],2))
        self.assertIsNone(intercept_time([0,0,1],[.1,0,1],[0,0,0],12))
        self.assertIsNone(intercept_time([0,0,1],[5,0,1],[3,0,0],2))

    def test_generated_options_respect_requested_speed(self):
        from math import hypot
        b=baseline()
        edits=dict(ball_speed_m_s=12,options=deepcopy(b["options"]))
        edits["options"][1]["receiver_velocity"]=[1,.5,0]
        r=sandbox(b,edits,16)
        generated=[o for o in r["options"] if o["generated"]]
        self.assertTrue(any(o["kind"]=="pass" for o in generated))
        self.assertTrue(any(o["kind"]=="shot" for o in generated))
        for o in generated:
            self.assertAlmostEqual(hypot(o["target"][0]-r["start"][0],o["target"][1]-r["start"][1])/o["flight_s"],12,places=8)

    def test_generated_options_outside_time_window_omitted(self):
        b=baseline()
        r=sandbox(b,dict(ball_speed_m_s=2),16)
        self.assertEqual(r["proposed_ids"],[])
        self.assertEqual(len(r["options"]),2)

if __name__=="__main__":unittest.main()
