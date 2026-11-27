import json
import random
import unittest
from tactical_trajectories import analyze, _exposure

class TacticalTests(unittest.TestCase):
    def run_case(self, p, q, **kwargs):
        return analyze([(0,p),(.2,q)], ['a'], ['d','e'], **kwargs)

    def test_double_not_counted_twice(self):
        p={'a':(0,0),'d':(1,0),'e':(-1,0)}
        r=self.run_case(p,p)['attackers'][0]
        self.assertAlmostEqual(r['team_proximity_s'],.2)
        self.assertAlmostEqual(r['double_proximity_s'],.2)

    def test_crossing(self):
        p={'a':(0,0),'d':(-2,0),'e':(8,0)}
        q={**p,'d':(2,0)}
        r=self.run_case(p,q)['attackers'][0]
        self.assertAlmostEqual(r['team_proximity_s'],.15)
        self.assertEqual(r['double_proximity_s'],0)

    def test_missing_defender_not_zero_pressure(self):
        p={'a':(0,0),'d':(1,0)}
        r=self.run_case(p,p)
        self.assertIsNone(r['attackers'][0]['team_proximity_s'])
        self.assertEqual(r['players'][0]['distance_m'],0)
        self.assertIsNone(r['players'][2]['distance_m'])

    def test_disjoint_and_overlap(self):
        self.assertAlmostEqual(_exposure([(0,.4),(.6,1)],1),.8)
        self.assertAlmostEqual(_exposure([(0,.8),(.2,1)],2),.6)
        self.assertEqual(_exposure([(0,.5),(.5,1)],2),0)

    def test_gap(self):
        p={'a':(0,0),'d':(1,0),'e':(2,0)}
        r=self.run_case(p,p,max_gap_s=.1)
        self.assertEqual(r['players'][0]['coverage'],0)
        self.assertIsNone(r['attackers'][0]['team_proximity_fraction'])

    def test_motion_and_offball(self):
        p={'a':(0,0),'b':(1,0),'d':(0,0)}
        q={**p,'b':(2,0)}
        r=analyze([(0,p),(.2,q)],['a','b'],['d'],carrier='a')
        self.assertEqual(r['players'][1]['distance_m'],1)
        self.assertEqual(r['players'][1]['mean_speed_mps'],5)
        self.assertEqual(r['attackers'][1]['offball_net_separation_delta_m'],1)
        self.assertIsNone(r['attackers'][0]['offball_net_separation_delta_m'])
        self.assertIsNone(analyze([(0,p),(.2,q)],['a','b'],['d'])['attackers'][1]['offball_net_separation_delta_m'])
        json.dumps(r,allow_nan=False)

    def test_bad_ids_and_times(self):
        with self.assertRaises(ValueError): analyze([],['a'],['a'])
        with self.assertRaises(ValueError): analyze([(0,{}),(0,{})],['a'],['d'])
        with self.assertRaises(ValueError): analyze([],['a'],['d'],carrier='d')

    def test_random_union_oracle(self):
        rng=random.Random(44)
        for _ in range(100):
            intervals=[tuple(sorted((rng.random(),rng.random()))) for _ in range(6)]
            for k in (1,2):
                exact=_exposure(intervals,k)
                reference=sum(sum(a<=(i+.5)/2000<b for a,b in intervals)>=k for i in range(2000))/2000
                self.assertLessEqual(abs(exact-reference),.003)

if __name__=='__main__': unittest.main()
