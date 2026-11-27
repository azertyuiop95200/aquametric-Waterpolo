import unittest
from copy import deepcopy
from services.spatial_sandbox import sandbox

def scene():
    return dict(source="manual_video",decision_second=21.,length_m=25.,width_m=20.,goal_x=25.,
        start=[17.,10.,1.],sigma_m=.15,complete_defence=True,chosen="real",
        defenders=[dict(id="G",position=[24.,10.,.5],velocity=[0,0,0],radius=.65,confidence=1.),
                   dict(id="D",position=[21.,10.,1.],velocity=[0,0,0],radius=.65,confidence=1.)],
        options=[dict(id="real",kind="shot",target=[25.,10.,.5],duration_s=.5),
                 dict(id="pass",kind="pass",target=[17.,15.,1.],duration_s=.5)])

class TwoStepTests(unittest.TestCase):
    def run_scene(self,x,**edits):
        return sandbox(x,dict(keeper_id="G",two_step=True,suggest=False,**edits),16)["two_step"]

    def test_bottleneck_and_reception(self):
        x=scene();old=deepcopy(x)
        r=self.run_scene(x,reception_s=.25)
        o=r["alternatives"][0]
        self.assertEqual(o["shot_release_s"],.75)
        self.assertEqual(o["shot_start"],(17.,15.,1.))
        self.assertEqual(o["joint_clearance_m"],min(o["pass_clearance_m"],o["shot_clearance_m"]))
        self.assertAlmostEqual(o["direct_clearance_delta_m"],o["joint_clearance_m"]-r["direct_best"]["defence_clearance_m"])
        self.assertIsNone(o["goal_probability"])
        self.assertEqual(x,old)

    def test_blocked_pass_cannot_be_clear_sequence(self):
        x=scene();x["defenders"][1]["position"]=[17.,12.5,1.3]
        o=self.run_scene(x)["alternatives"][0]
        self.assertLessEqual(o["pass_clearance_m"],0)
        self.assertEqual(o["status"],"potential_obstruction")

    def test_budget_and_unknown(self):
        x=scene()
        self.assertEqual(self.run_scene(x,sequence_budget_s=.6)["alternatives"][0]["status"],"outside_bounds_or_budget")
        x["complete_defence"]=False
        r=self.run_scene(x)
        self.assertIsNone(r["direct_best"])
        self.assertIsNone(r["alternatives"][0]["joint_clearance_m"])
        self.assertEqual(r["alternatives"][0]["status"],"unknown")

    def test_moving_receiver_at_second_release(self):
        x=scene();opts=deepcopy(x["options"]);opts[1]["receiver_velocity"]=[1,0,0]
        o=self.run_scene(x,reception_s=.25,options=opts)["alternatives"][0]
        self.assertEqual(o["shot_start"],(17.75,15.,1.))
        self.assertGreater(o["total_duration_s"],o["shot_release_s"])

    def test_defender_outside_pool_not_clipped(self):
        x=scene();x["defenders"][0]["position"]=[24.8,10,.5];x["defenders"][0]["velocity"]=[1,0,0]
        o=self.run_scene(x)["alternatives"][0]
        self.assertEqual(o["status"],"defender_projection_outside_bounds")
        self.assertIsNone(o["joint_clearance_m"])

    def test_opt_in_and_explicit_keeper(self):
        x=scene()
        self.assertNotIn("two_step",sandbox(x,{"suggest":False},16))
        with self.assertRaises(ValueError):sandbox(x,{"two_step":True},16)

if __name__=="__main__":unittest.main()
