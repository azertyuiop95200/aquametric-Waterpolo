import unittest,json
from goalkeeper_geometry import snapshot,KeeperAccumulator

class KeeperTests(unittest.TestCase):
    def snap(self,c=(15,10),k=(24,10),span=1.,goal=25):return snapshot(c,k,goal,25,20,3.,span)
    def test_center(self):
        r=self.snap();self.assertEqual(r['alignment_error_m'],0);self.assertAlmostEqual(r['projected_fraction'],1/2.7);self.assertAlmostEqual(r['keeper_depth_m'],1)
    def test_reverse(self):
        a=self.snap();b=self.snap((10,10),(1,10),1.,0);self.assertEqual(a,b)
    def test_offset(self):self.assertAlmostEqual(self.snap((15,5),(24,9.5))['alignment_error_m'],0)
    def test_outside_projection(self):self.assertEqual(self.snap(k=(24,16))['projected_fraction'],0)
    def test_behind_carrier(self):self.assertIsNone(self.snap(k=(14,10))['projected_fraction'])
    def test_no_assumption(self):self.assertIsNone(self.snap(span=None)['projected_fraction'])
    def test_goal_line(self):self.assertIsNone(self.snap(c=(25,10))['goal_angle_deg'])
    def test_invalid(self):
        with self.assertRaises(ValueError):self.snap(span=True)
    def test_missing(self):
        a=KeeperAccumulator({'provenance':'coach_review','keeper':'k','goal_width_m':3},'c',['k'],25,25,20);r=a.result();self.assertIsNone(r['means']['goal_angle_deg']);self.assertIsNone(r['lateral_distance_m'])
    def test_accumulation(self):
        a=KeeperAccumulator({'provenance':'coach_review','keeper':'k','goal_width_m':3,'assumed_lateral_span_m':1},'c',['k'],25,25,20)
        a.add({'c':((15,10),(15,10)),'k':((24,10),(24,10.2))},0,.2)
        a.add({'c':((15,10),(15,10)),'k':((24,11),(24,11.2))},1,1.2)
        r=a.result();self.assertAlmostEqual(r['lateral_distance_m'],.4);self.assertAlmostEqual(r['observed_s'],.4);self.assertIsNone(r['save_probability']);json.dumps(r,allow_nan=False)
    def test_review(self):
        with self.assertRaises(ValueError):KeeperAccumulator({'keeper':'k','goal_width_m':3},'c',['k'],25,25,20)
if __name__=='__main__':unittest.main()
