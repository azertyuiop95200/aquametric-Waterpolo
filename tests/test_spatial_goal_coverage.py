import unittest
from copy import deepcopy
from spatial_decision_3d import Track
from services.spatial_goal_coverage import goal_coverage
from services.spatial_sandbox import sandbox
from services.spatial_scenario_search import search_scenarios

def scene():
    return dict(source="manual_video",decision_second=21.,length_m=25.,width_m=20.,goal_x=25.,
        start=[17.,10.,1.],sigma_m=.15,complete_defence=True,chosen="real",
        defenders=[dict(id="G",position=[24.,10.,.5],velocity=[0,0,0],radius=.65,confidence=1.),
                   dict(id="D",position=[21.,10.,1.],velocity=[0,0,0],radius=.65,confidence=1.)],
        options=[dict(id="real",kind="shot",target=[25.,10.,.5],duration_s=.5),
                 dict(id="pass",kind="pass",target=[17.,15.,1.],duration_s=.5)])

class GoalCoverageTests(unittest.TestCase):
    def test_grid_and_separate_defence(self):
        tracks=[Track("G",(24.,10.,.5)),Track("D",(21.,10.,1.))]
        r=goal_coverage((17.,10.,1.),25,20,tracks,"G",True,12)
        self.assertEqual(len(r["cells"]),27)
        self.assertEqual(r["keeper"]["evaluated"],27)
        self.assertLessEqual(r["defence"]["clear"],r["keeper"]["clear"])
        self.assertIsNone(r["goal_probability"])
        self.assertAlmostEqual(r["cell_area_m2"]*27,r["ball_center_aperture_m2"])
        self.assertTrue(all(8.61<=c["target"][1]<=11.39 and .11<=c["target"][2]<=.79 for c in r["cells"]))

    def test_unknown_and_infeasible(self):
        tracks=[Track("G",(24.,10.,.5))]
        r=goal_coverage((17.,10.,1.),25,20,tracks,"G",False,12)
        self.assertEqual(r["keeper"]["evaluated"],27)
        self.assertIsNone(r["defence"]["clear"])
        self.assertIsNone(goal_coverage((17.,10.,1.),25,20,tracks,"missing",True,12)["keeper"]["clear"])
        r=goal_coverage((0.,10.,1.),25,20,tracks,"G",True,2)
        self.assertIsNone(r["keeper"]["clear"])
        self.assertTrue(all(c["keeper_status"]=="outside_flight_window" for c in r["cells"]))

    def test_mirror(self):
        a=goal_coverage((17.,9.,1.),25,20,[Track("G",(24.,9.5,.5))],"G",True,12)
        b=goal_coverage((8.,9.,1.),0,20,[Track("G",(1.,9.5,.5))],"G",True,12)
        self.assertEqual([c["keeper_status"] for c in a["cells"]],[c["keeper_status"] for c in b["cells"]])

    def test_sandbox_and_timing(self):
        x=scene();old=deepcopy(x)
        self.assertNotIn("goal_coverage",sandbox(x,{"suggest":False},16))
        r=sandbox(x,{"keeper_id":"G","suggest":False},16)
        self.assertEqual(r["goal_coverage"]["keeper_id"],"G")
        with self.assertRaises(ValueError):sandbox(x,{"keeper_id":"unknown"},16)
        search=search_scenarios(x,{"keeper_id":"G"})
        self.assertEqual([w["delay_s"] for w in search["timing_samples"]],[0,.25,.5,1,1.5,2])
        self.assertEqual(x,old)

if __name__=="__main__":unittest.main()
