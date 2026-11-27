import unittest
from services.support_geometry import SupportAccumulator
from services.possession_geometry import analyze_window
from test_possession_geometry import fixture


def static(a=(5,5),b=(9,5),d=(9,8)):
    return {'a':(a,a),'b':(b,b),'d':(d,d)}

class SupportTests(unittest.TestCase):
    def new(self,goal=25):return SupportAccumulator(['a','b'],['d'],'a',goal,25)
    def test_open(self):
        s=self.new();s.add(static(),0,.2,{'b':'clear_2d'});r=s.result()['rows'][0];self.assertAlmostEqual(r['support_open_s'],.2);self.assertAlmostEqual(r['nearest_defender_mean_m'],3);self.assertAlmostEqual(r['carrier_distance_mean_m'],4)
    def test_blocked(self):
        s=self.new();s.add(static(),0,.2,{'b':'obstructed_2d'});r=s.result()['rows'][0];self.assertEqual(r['support_open_s'],0);self.assertEqual(r['support_unknown_s'],0)
    def test_uncertain(self):
        s=self.new();s.add(static(),0,.2,{'b':'indeterminate'});self.assertAlmostEqual(s.result()['rows'][0]['support_unknown_s'],.2)
    def test_direction(self):
        e=static();e['b']=((9,5),(9.4,5));s=self.new(0);s.add(e,0,.2,{'b':'clear_2d'});self.assertAlmostEqual(s.result()['rows'][0]['goal_progress_m'],-.4)
    def test_missing(self):self.assertIsNone(self.new().result()['rows'][0]['support_open_s'])
    def test_bound(self):
        e=static(b=(10,5),d=(10,8));e['b']=((9.9,5),(10.1,5));s=self.new();s.add(e,0,.2,{'b':'clear_2d'});self.assertEqual(s.result()['rows'][0]['support_open_s'],0);self.assertAlmostEqual(s.result()['rows'][0]['support_unknown_s'],.2)
    def test_integrated(self):
        r,w=fixture();v=analyze_window(r,w);self.assertAlmostEqual(v['offball_support']['observed_s'],v['observed_s']);self.assertEqual(len(v['offball_support']['rows']),1)
    def test_integrated_missing(self):
        r,w=fixture(missing=True);self.assertIsNone(analyze_window(r,w)['offball_support']['rows'][0]['nearest_defender_mean_m'])
if __name__=='__main__':unittest.main()
