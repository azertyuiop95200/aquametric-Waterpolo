import unittest,json
from defensive_recovery import analyze_recovery

def fixture(goal=25):
    def player(cap,x,y,dx):
        return dict(side='for',cap_number=cap,metrics={},segments=[[dict(second=t,x_m=x+dx*(t-1),y_m=y) for t in (1,1.2,1.4)]])
    r=dict(source='1',period=1,start_s=0,end_s=5,length_m=25,width_m=20,players=[player(2,12.3,4,1),player(3,14,9,2)])
    e=dict(id=7,source='1',period=1,before='for',after='against',start_s=.5,end_s=1,status='opposite_endpoints',exact_count=1)
    w=dict(source='1',period=1,transition_id=7,start_s=1,end_s=1.4,provenance='coach_review',continuous_play_reviewed=True,roster_reviewed=True,field_players_only=True,defenders=['for:2','for:3'],own_goal_x=goal)
    return r,e,w

class RecoveryTests(unittest.TestCase):
    def test_motion(self):
        v=analyze_recovery(*fixture());self.assertAlmostEqual(v['observed_s'],.4);self.assertAlmostEqual(v['mean_team_goalward_mps'],1.5);self.assertAlmostEqual(v['players'][0]['own_half_s'],.2);self.assertIsNone(v['recovery_time_s']);json.dumps(v,allow_nan=False)
    def test_reverse(self):
        v=analyze_recovery(*fixture(0));self.assertAlmostEqual(v['mean_team_goalward_mps'],-1.5);self.assertAlmostEqual(v['players'][0]['own_half_s'],.2)
    def test_missing(self):
        r,e,w=fixture();r['players'].pop();v=analyze_recovery(r,e,w);self.assertEqual(v['coverage'],0);self.assertIsNone(v['players'][0]['distance_m'])
    def test_partial(self):
        r,e,w=fixture();r['players'][1]['segments'][0].pop();v=analyze_recovery(r,e,w);self.assertAlmostEqual(v['coverage'],.5);self.assertAlmostEqual(v['players'][0]['distance_m'],.2)
    def test_unreviewed(self):
        r,e,w=fixture();w['continuous_play_reviewed']=False;self.assertRaises(ValueError,analyze_recovery,r,e,w)
    def test_before_control(self):
        r,e,w=fixture();w['start_s']=.9;self.assertRaises(ValueError,analyze_recovery,r,e,w)
    def test_wrong_source(self):
        r,e,w=fixture();w['source']='2';self.assertRaises(ValueError,analyze_recovery,r,e,w)
    def test_not_exact(self):
        r,e,w=fixture();e['exact_count']=True;self.assertRaises(ValueError,analyze_recovery,r,e,w)
    def test_overlap(self):
        r,e,w=fixture();r['players'][0]['segments']*=2;self.assertRaises(ValueError,analyze_recovery,r,e,w)
    def test_other_team(self):
        r,e,w=fixture();w['defenders']=['against:2'];self.assertRaises(ValueError,analyze_recovery,r,e,w)
if __name__=='__main__':unittest.main()
