import unittest
from services.spatial_predecision_motion import estimate,in_bounds
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
        s=moving();s['advanced_motion']['players'][2]['segments']=track([(.4,22,10),(.6,22,10.12)])['segments']
        with self.assertRaises(ValueError):prepare(s,dynamic(s))
    def test_stale_velocity(self):
        s=saved();self.assertEqual(len(build(s,local_source=True)['rows']),1)
        p=s['advanced_motion']['players'][2]['segments'][0];p[0]['y_m']-=.1
        self.assertEqual(build(s,local_source=True)['rows'],[])
    def test_stationary_compatible(self):
        s=moving();_,r=prepare(s,raw(s));self.assertEqual(r['motion_mode'],'stationary_hypothesis')
        self.assertTrue(all(d['velocity']==[0,0,0] for d in r['defenders']))
    def test_reject_outside_projection(self):
        s=moving();p=s['advanced_motion']['players'][3];p['segments']=track([(t,23+t,10) for t in (0,.2,.4,.6,.8)])['segments']
        s['shot_context']=shots(s,local_source=True)
        with self.assertRaises(ValueError):prepare(s,dynamic(s))
if __name__=='__main__':unittest.main()
