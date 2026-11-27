import unittest
from services.spatial_predecision_motion import estimate,in_bounds,estimate_reviewed
from services.spatial_context_3d import prepare,append,build
from services.shot_context_review import append as append_shot,build as shots
from test_shot_context_release import sample as shot_sample,raw as shot_raw
from test_spatial_context_release import raw

def track(points):
    return {'segments':[[dict(second=t,x_m=x,y_m=y) for t,x,y in points]]}

def moving():
    s=shot_sample()
    for p in s['advanced_motion']['players']:
        x,y=p['segments'][0][0]['x_m'],p['segments'][0][0]['y_m']
        p['segments']=track([(t,x,y+(.2*t if p['side']=='against' else 0)) for t in (0,.2,.4,.6,.8)])['segments']
        p['metrics']['observed_s']=.8
    summary=s['automatic']['summary'];metric=summary['metric_field_map'];metric['reference_second']=0
    metric['tracks']=[]
    for i,p in enumerate(s['advanced_motion']['players']):
        metric['tracks'].append(dict(id=i+1,forward_from_s=0,raw_segments=[[dict(second=q['second'],x_m=q['x_m'],y_m=q['y_m']-10) for q in seg] for seg in p['segments']]))
        summary['identity_reviews']['tracks'][str(i+1)]=dict(side=p['side'],cap_number=p['cap_number'],provenance='coach_review',evidence='Synthetic forward track')
    s['automatic']['summary']['metric_field_map']['shots'][0]['second']=.6
    s['primary_shot_events'][0]['second']=.6
    s['primary_shot_events'][1]['second']=.7
    s['automatic']['summary']['shot_context_reviews']=append_shot(s,shot_raw(s))
    s['shot_context']=shots(s,local_source=True)
    return s

def dynamic(s):
    w=raw(s);w['motion_mode']='predecision_velocity';return w

def saved():
    s=moving();s['automatic']['summary']['spatial_3d_reviews']=append(s,dynamic(s));return s

class PredecisionTests(unittest.TestCase):
    def test_constant(self):
        m=estimate(track([(0,10,5),(.2,10.2,5),(.4,10.4,5),(.6,10.6,5)]),.6,25,20)
        self.assertAlmostEqual(m['velocity'][0],1);self.assertAlmostEqual(m['support_s'],.6)
    def test_no_future(self):
        p=track([(0,10,5),(.2,10.2,5),(.4,10.4,5),(.6,10.6,5),(.8,11,5)])
        a=estimate(p,.6,25,20);p['segments'][0][-1]['x_m']=24;self.assertEqual(a,estimate(p,.6,25,20))
    def test_no_crossing_edge(self):
        self.assertIsNone(estimate(track([(0,10,5),(.2,10.2,5),(.4,10.4,5)]),.31,25,20))
    def test_gap(self):
        self.assertIsNone(estimate(track([(0,10,5),(.2,10.2,5),(.5,10.5,5),(.6,10.6,5)]),.6,25,20))
    def test_old(self):
        self.assertIsNone(estimate(track([(0,10,5),(.2,10.2,5),(.4,10.4,5)]),.6,25,20))
    def test_overlap(self):
        p=track([(0,10,5),(.2,10.2,5),(.4,10.4,5),(.6,10.6,5)]);p['segments']*=2
        self.assertIsNone(estimate(p,.6,25,20))
    def test_conflicting_switch(self):
        p=track([(0,10,5),(.2,10.2,5),(.4,10.4,5)]);p['segments']+=track([(.4,11,5),(.6,11.2,5)])['segments']
        self.assertIsNone(estimate(p,.6,25,20))
    def test_bounds(self):
        self.assertFalse(in_bounds([24,10,1],[1,0,0],2,25,20));self.assertTrue(in_bounds([24,10,1],[-1,0,0],2,25,20))
    def test_bridge(self):
        s=moving();_,r=prepare(s,dynamic(s));self.assertEqual(r['motion_mode'],'predecision_velocity')
        self.assertTrue(all(abs(d['velocity'][1]-.2)<1e-8 for d in r['defenders']))
        self.assertEqual(len(r['predecision_motion']),2)
        self.assertIsNone(r['actual_target'])
    def test_missing_support(self):
        s=moving();s['automatic']['summary']['metric_field_map']['tracks'][2]['raw_segments']=track([(.4,22,0),(.6,22,.12)])['segments']
        with self.assertRaises(ValueError):prepare(s,dynamic(s))
    def test_stale_velocity(self):
        s=saved();self.assertEqual(len(build(s,local_source=True)['rows']),1)
        p=s['automatic']['summary']['metric_field_map']['tracks'][2]['raw_segments'][0];p[0]['y_m']-=.1
        self.assertEqual(build(s,local_source=True)['rows'],[])
    def test_stationary_compatible(self):
        s=moving();_,r=prepare(s,raw(s));self.assertEqual(r['motion_mode'],'stationary_hypothesis')
        self.assertTrue(all(d['velocity']==[0,0,0] for d in r['defenders']))
    def test_reject_outside_projection(self):
        s=moving();p=s['automatic']['summary']['metric_field_map']['tracks'][3];p['raw_segments']=track([(t,23+t,0) for t in (0,.2,.4,.6,.8)])['segments']
        s['shot_context']=shots(s,local_source=True)
        with self.assertRaises(ValueError):prepare(s,dynamic(s))
    def test_raw_no_future_or_smoothed_dependence(self):
        s=moving();m=estimate_reviewed(s,'against:4',.6,25,20)
        s['advanced_motion']['players'][2]['segments'][0][0]['y_m']=18
        s['automatic']['summary']['metric_field_map']['tracks'][2]['raw_segments'][0][-1]['y_m']=9
        self.assertEqual(m,estimate_reviewed(s,'against:4',.6,25,20))
    def test_old_calibration_no_raw(self):
        s=moving();del s['automatic']['summary']['metric_field_map']['tracks'][2]['raw_segments']
        self.assertRaises(ValueError,prepare,s,dynamic(s))
    def test_future_seed(self):
        s=moving();s['automatic']['summary']['metric_field_map']['tracks'][2]['forward_from_s']=.8
        self.assertIsNone(estimate_reviewed(s,'against:4',.6,25,20))
    def test_future_reference(self):
        s=moving();s['automatic']['summary']['metric_field_map']['reference_second']=.8
        self.assertIsNone(estimate_reviewed(s,'against:4',.6,25,20))
    def test_duplicate_raw_track(self):
        s=moving();m=s['automatic']['summary']['metric_field_map'];m['tracks'].append(dict(m['tracks'][2],id=99))
        s['automatic']['summary']['identity_reviews']['tracks']['99']=s['automatic']['summary']['identity_reviews']['tracks']['3']
        self.assertIsNone(estimate_reviewed(s,'against:4',.6,25,20))
if __name__=='__main__':unittest.main()
