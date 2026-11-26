import unittest
from services.mobility import summarize_tracks

def tr(a=0,b=1,x=0,X=1,y=0,Y=0):
    return {'segments':[[{'second':a+(b-a)*i/8,'x_m':x+(X-x)*i/8,'y_m':y+(Y-y)*i/8} for i in range(9)]]}
class MobilityTests(unittest.TestCase):
    def test_distance_and_speed(self):
        r=summarize_tracks([tr()]);self.assertEqual(r['distance_m'],1);self.assertEqual(r['mean_speed_m_s'],1)
    def test_duplicate(self):
        r=summarize_tracks([tr(),tr()]);self.assertEqual(r['distance_m'],1);self.assertEqual(r['overlap_seconds'],1)
    def test_conflict(self):
        r=summarize_tracks([tr(),tr(x=3,X=4)]);self.assertIsNone(r['distance_m']);self.assertEqual(r['conflict_seconds'],1)
    def test_no_bridge(self):
        r=summarize_tracks([tr(),tr(a=3,b=4,x=7,X=8)]);self.assertEqual(r['observed_seconds'],2);self.assertEqual(r['distance_m'],2)
    def test_grid_crossing(self):
        r=summarize_tracks([tr(x=1,X=3)]);self.assertEqual([x['seconds'] for x in r['heatmap']['cells']],[.5,.5])
    def test_stationary(self):
        r=summarize_tracks([tr(X=0)]);self.assertEqual(r['distance_m'],0);self.assertEqual(r['mean_speed_m_s'],0);self.assertEqual(r['heatmap']['cells'][0]['seconds'],1)
    def test_outside_and_fast_rejected(self):
        self.assertIsNone(summarize_tracks([tr(x=-1,X=-1)])['distance_m']);self.assertIsNone(summarize_tracks([tr(X=10)])['distance_m'])
    def test_empty(self):
        self.assertIsNone(summarize_tracks([])['p90_speed_m_s'])
    def test_weighted_speed(self):
        r=summarize_tracks([tr(a=0,b=1,X=1),tr(a=2,b=4,x=3,X=7)]);self.assertEqual(r['median_speed_m_s'],2);self.assertEqual(r['p90_speed_m_s'],2)
