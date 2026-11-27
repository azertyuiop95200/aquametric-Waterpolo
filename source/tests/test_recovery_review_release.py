import unittest,json
from services.recovery_review import append,build
from services.collective_review import context
from test_collective_review_release import fixture

def sample():
    s=fixture()
    for p in s['advanced_motion']['players']:
        x,y=p['segments'][0][0]['x_m'],p['segments'][0][0]['y_m']
        p['segments']=[[dict(second=t,x_m=x+(t-1),y_m=y) for t in (1,1.2,1.4)]]
        p['metrics']['observed_s']=.4
    return s

def raw(s):
    return dict(binding=context(s),before_s=.5,after_s=1,start_s=1,end_s=1.4,period=1,losing_side='for',own_goal_x=25,defenders=['for:2','for:3'],evidence='QA synthetic opposite control',unique_change_reviewed=True,continuous_play_reviewed=True,roster_reviewed=True,field_players_only=True)

def saved():
    s=sample();s['automatic']['summary']['recovery_reviews']=append(s,raw(s));return s

class RecoveryReleaseTests(unittest.TestCase):
    def test_report(self):
        r=build(saved(),local_source=True);self.assertEqual(r['status'],'experimental_partial');t=r['reports'][0]['transitions'][0];self.assertEqual(t['id'],'R1');v=t['recovery'];self.assertAlmostEqual(v['observed_s'],.4);self.assertAlmostEqual(v['mean_team_goalward_mps'],1);self.assertIsNone(v['recovery_time_s']);json.dumps(r,allow_nan=False)
    def test_no_review(self):self.assertEqual(build(sample(),local_source=True)['reports'],[])
    def test_remote(self):self.assertEqual(build(saved(),local_source=False)['status'],'unavailable')
    def test_stale(self):
        s=saved();s['automatic']['summary']['metric_field_map']['revision']='stale';self.assertEqual(build(s,local_source=True)['reports'],[])
    def test_identity_change(self):
        s=saved();s['automatic']['summary']['identity_reviews']['tracks']['1']['cap_number']=6;self.assertEqual(build(s,local_source=True)['reports'],[])
    def test_overlap(self):
        s=saved();self.assertRaises(ValueError,append,s,raw(s))
    def test_before_control(self):
        s=sample();r=raw(s);r['start_s']=.8;self.assertRaises(ValueError,append,s,r)
    def test_missing_review(self):
        s=sample();r=raw(s);r['unique_change_reviewed']=False;self.assertRaises(ValueError,append,s,r)
    def test_wrong_side(self):
        s=sample();r=raw(s);r['defenders']=['against:4'];self.assertRaises(ValueError,append,s,r)
    def test_goal_required(self):
        s=sample();r=raw(s);r['own_goal_x']=False;self.assertRaises(ValueError,append,s,r)
    def test_no_common_support(self):
        s=saved();s['advanced_motion']['players'][0]['segments']=[];r=build(s,local_source=True)['reports'][0]['transitions'][0]['recovery'];self.assertEqual(r['coverage'],0);self.assertIsNone(r['mean_team_goalward_mps'])
    def test_no_keeper_claim(self):
        s=sample();r=raw(s);r['field_players_only']=False;self.assertRaises(ValueError,append,s,r)
if __name__=='__main__':unittest.main()
