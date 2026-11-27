import unittest
from spatial_dominance import SpaceAccumulator
from possession_geometry import analyze_window
from test_possession_geometry import fixture


def static(a=(2,10),b=(23,10)):
    return {'a':(a,a),'b':(b,b)}

class DominanceTests(unittest.TestCase):
    def test_area_conservation(self):
        s=SpaceAccumulator(25,20,['a'],['b'],position_error_m=0.)
        s.add(static(),0,.2);r=s.result()
        for k in ('nominal_mean_area_m2','robust_mean_area_m2'):
            self.assertAlmostEqual(sum(r[k].values()),500)
        self.assertGreater(r['robust_mean_area_m2']['neutral_or_unresolved'],0)
        self.assertAlmostEqual(sum(c['w']*c['h'] for c in r['cells']),500)
    def test_no_error_not_zero(self):
        s=SpaceAccumulator(25,20,['a'],['b']);s.add(static(),0,.2);r=s.result()
        self.assertIsNone(r['robust_mean_area_m2']);self.assertIsNone(r['local'][0]['robust_s']);self.assertIsNotNone(r['nominal_mean_area_m2'])
    def test_no_observation(self):
        r=SpaceAccumulator(25,20,['a'],['b'],position_error_m=0.).result()
        self.assertIsNone(r['nominal_mean_area_m2']);self.assertIsNone(r['cells'][0]['nominal'])
    def test_uncertainty_monotonic(self):
        results=[]
        for e in (0.,.5,2.):
            s=SpaceAccumulator(25,20,['a'],['b'],position_error_m=e);s.add(static(),0,.2)
            results.append(s.result()['robust_mean_area_m2']['neutral_or_unresolved'])
        self.assertEqual(results,sorted(results))
    def test_local_count_self(self):
        s=SpaceAccumulator(25,20,['a'],['b'],position_error_m=.1);s.add(static(),0,.2);r=s.result()['local'][0]
        self.assertEqual(r['mean_attackers'],1);self.assertEqual(r['mean_defenders'],0);self.assertAlmostEqual(r['robust_s']['attack'],.2)
    def test_local_border(self):
        s=SpaceAccumulator(25,20,['a'],['b'],position_error_m=.2);s.add(static((2,10),(5,10)),0,.2);r=s.result()['local'][0]
        self.assertAlmostEqual(r['nominal_s']['neutral_or_unresolved'],.2);self.assertAlmostEqual(r['robust_s']['neutral_or_unresolved'],.2)
    def test_equal_positions(self):
        s=SpaceAccumulator(25,20,['a'],['b'],position_error_m=0.);s.add(static((2,10),(2,10)),0,.2);r=s.result()
        self.assertAlmostEqual(r['nominal_mean_area_m2']['neutral_or_unresolved'],500)
    def test_weighted_time(self):
        s=SpaceAccumulator(25,20,['a'],['b']);s.add(static(),0,.1);s.add(static((23,10),(2,10)),.1,.4);r=s.result()
        self.assertAlmostEqual(r['observed_s'],.4)
        self.assertAlmostEqual(sum(r['nominal_mean_area_m2'].values()),500)
    def test_integrated(self):
        r,w=fixture();w['position_error_bound_m']=.15;v=analyze_window(r,w);self.assertAlmostEqual(v['spatial_dominance']['observed_s'],v['observed_s']);self.assertEqual(v['spatial_dominance']['position_error_bound_m'],.15)
        r,w=fixture(missing=True);self.assertIsNone(analyze_window(r,w)['spatial_dominance']['nominal_mean_area_m2'])
    def test_invalid_error(self):
        with self.assertRaises(ValueError):SpaceAccumulator(25,20,['a'],['b'],position_error_m=True)
if __name__=='__main__':unittest.main()
