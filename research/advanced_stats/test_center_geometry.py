import unittest
from services.center_geometry import CenterAccumulator
from services.possession_geometry import analyze_window
from test_possession_geometry import fixture


def make(goal=25,error=None):
    return CenterAccumulator({'provenance':'coach_review','center':'a','marker':'d'},['a'],['d'],goal,25,20,error=error)

class CenterTests(unittest.TestCase):
    def test_static(self):
        c=make();c.add({'a':((22,10),(22,10)),'d':((23,10),(23,10))},0,.2);r=c.result();self.assertAlmostEqual(r['zone_s'],.2);self.assertAlmostEqual(r['marker_goal_side_s'],.2);self.assertAlmostEqual(r['marker_proximity_s'],.2);self.assertIsNone(r['proximity_lower_s'])
    def test_crossing_zone(self):
        c=make();c.add({'a':((20.8,10),(21.2,10)),'d':((22,10),(22,10))},0,.2);self.assertAlmostEqual(c.result()['zone_s'],.1)
    def test_goal_reversed(self):
        c=make(0);c.add({'a':((3,10),(3,10)),'d':((2,10),(2,10))},0,.2);self.assertAlmostEqual(c.result()['marker_goal_side_s'],.2)
    def test_goal_side_crossing(self):
        c=make();c.add({'a':((22,10),(22,10)),'d':((21.8,10),(22.2,10))},0,.2);self.assertAlmostEqual(c.result()['marker_goal_side_s'],.1)
    def test_neutral(self):
        c=make();c.add({'a':((22,10),(22,10)),'d':((22,11),(22,11))},0,.2);self.assertEqual(c.result()['marker_goal_side_s'],0)
    def test_uncertainty(self):
        c=make(error=.2);c.add({'a':((22,10),(22,10)),'d':((23.4,10),(23.4,10))},0,.2);r=c.result();self.assertEqual(r['proximity_lower_s'],0);self.assertAlmostEqual(r['proximity_upper_s'],.2)
    def test_unreviewed(self):
        with self.assertRaises(ValueError):CenterAccumulator({'center':'a','marker':'d'},['a'],['d'],25,25,20)
    def test_integration(self):
        r,w=fixture();self.assertIsNone(analyze_window(r,w)['center_geometry']);w['center_review']={'provenance':'coach_review','center':'for:2','marker':'against:1'};self.assertAlmostEqual(analyze_window(r,w)['center_geometry']['observed_s'],.2)
    def test_missing(self):
        r,w=fixture(missing=True);w['center_review']={'provenance':'coach_review','center':'for:2','marker':'against:1'};self.assertIsNone(analyze_window(r,w)['center_geometry']['zone_s'])
