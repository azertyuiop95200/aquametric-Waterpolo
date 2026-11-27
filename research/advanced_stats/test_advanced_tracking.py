import unittest
from advanced_tracking import motion, reviewed_motion, geometry, transition

def seg(xs): return [{'second':i*.2,'x_m':x,'y_m':0} for i,x in enumerate(xs)]
C=dict(sprint_mps=1.5,min_sprint_s=.35)
class Tests(unittest.TestCase):
    def test_acceleration(self):
        r=motion([seg([0,.2,.6,1.0,1.2])],**C)
        self.assertAlmostEqual(r['peak_speed_increase_mps2'],5)
        self.assertAlmostEqual(r['peak_speed_decrease_mps2'],5)
        self.assertEqual(r['sprint_count'],1)
        self.assertAlmostEqual(r['sprint_s'],.4)
    def test_no_bridge(self):
        a=seg([0,.4]); b=seg([1,1.4]); b=[{**p,'second':p['second']+1} for p in b]
        r=motion([a,b],**C); self.assertEqual(r['sprint_count'],0); self.assertIsNone(r['peak_speed_increase_mps2'])
    def test_missing(self): self.assertIsNone(motion([],**C)['sprint_count'])
    def test_overlap(self):
        with self.assertRaises(ValueError): motion([seg([0,.4]),seg([0,.4])],**C)
    def test_adapter(self):
        m={'tracks':[{'id':1,'segments':[seg([0,.4,.8])]}]}; p={'side':'for','cap_number':4,'track_ids':[1]}
        self.assertEqual(reviewed_motion(m,{'players':[p]},**C)[0]['metrics']['sprint_count'],1)
        self.assertIsNone(reviewed_motion(m,{'players':[p,p]},**C)[0]['metrics'])
    def test_geometry(self):
        r=geometry((0,0),(2,0),[(2,-2),(2,2)]); self.assertAlmostEqual(r['goal_angle_deg'],90); self.assertEqual(r['direction_to_goal_deg'],0)
        self.assertIsNone(geometry((0,0),(0,0),[(2,-2),(2,2)])['direction_to_goal_deg'])
    def test_transition(self):
        e=dict(status='opposite_endpoints',exact_count=1,start_s=2,end_s=4,source='1',period=1)
        r=transition(e,(0,0),(4,3),(1,0)); self.assertEqual(r['progress_m'],4); self.assertEqual(r['mean_progress_mps'],2); self.assertIsNone(r['recovery_s'])
        self.assertIsNone(transition({**e,'exact_count':None},(0,0),(4,3),(1,0))['progress_m'])
if __name__=='__main__': unittest.main()
