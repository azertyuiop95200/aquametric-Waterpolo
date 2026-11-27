import unittest,json
from services.spatial_context_3d import append,build,prepare
from services.shot_context_review import build as shots
from test_shot_context_release import saved as saved_shot

def sample():
    s=saved_shot();s['shot_context']=shots(s,local_source=True);return s

def raw(s):
    return dict(binding=s['shot_context']['context'],event_id=11,release_height_m=1.,defender_height_m=.8,radius_m=.35,horizontal_speed_mps=12.,sigma_m=.1,hypotheses_reviewed=True,motion_mode='stationary_hypothesis',evidence='Synthetic geometry test',receivers=['for:3'],receiver_height_m=1.,reception_s=.2,budget_s=3.)

def saved():
    s=sample();s['automatic']['summary']['spatial_3d_reviews']=append(s,raw(s));return s

class SpatialContextTests(unittest.TestCase):
    def test_integration(self):
        r=build(saved(),local_source=True);self.assertEqual(r['status'],'experimental_partial');a=r['rows'][0];self.assertEqual(a['model_version'],'replay-3');self.assertEqual(len(a['goal_coverage']['cells']),27);self.assertEqual(len(a['options']),7);self.assertIsNone(a['actual_target']);self.assertTrue(a['reference_is_hypothetical']);self.assertEqual(len(a['two_step']['alternatives']),1);self.assertTrue(all(o['goal_probability'] is None for o in a['options']));json.dumps(r,allow_nan=False)
    def test_missing_defence(self):
        s=sample();s['shot_context']['rows'][0]['complete_geometry']=False;self.assertRaises(ValueError,prepare,s,raw(s))
    def test_missing_keeper(self):
        s=sample();s['shot_context']['rows'][0]['keeper_id']=None;self.assertRaises(ValueError,prepare,s,raw(s))
    def test_wrong_width(self):
        s=sample();s['shot_context']['rows'][0]['goal_width_m']=2.5;self.assertRaises(ValueError,prepare,s,raw(s))
    def test_no_hypotheses(self):
        s=sample();w=raw(s);w['hypotheses_reviewed']=False;self.assertRaises(ValueError,prepare,s,w)
    def test_other_team(self):
        s=sample();w=raw(s);w['receivers']=['against:4'];self.assertRaises(ValueError,prepare,s,w)
    def test_stale_receiver(self):
        s=saved();s['advanced_motion']['players'][1]['segments']=[];self.assertEqual(build(s,local_source=True)['rows'],[])
    def test_stale_event(self):
        s=saved();s['shot_context']['rows'][0]['event']['kind']='goal';self.assertEqual(build(s,local_source=True)['rows'],[])
    def test_stale_context(self):
        s=saved();s['shot_context']['context']['revision']='stale';self.assertEqual(build(s,local_source=True)['rows'],[])
    def test_remote(self):
        self.assertEqual(build(saved(),local_source=False)['status'],'unavailable')
    def test_arm(self):
        s=sample();w=raw(s);w['reach_segments']={'against:1':[dict(part='left_arm',start_offset=[0,0,0],end_offset=[0,.6,.4],radius=.1)]};_,r=prepare(s,w);self.assertEqual(r['defenders'][0]['reach_segments'][0]['part'],'left_arm')
    def test_no_sigma(self):
        s=sample();w=raw(s);w['sigma_m']=0;_,r=prepare(s,w);self.assertTrue(all(o['clearance_frequency'] is None for o in r['options']))
if __name__=='__main__':unittest.main()
