import unittest
from source.spatial_decision_3d import Track, goal_angles, trajectory, assess, compare_options

class SpatialTests(unittest.TestCase):
    def test_symmetry(self):
        self.assertAlmostEqual(goal_angles((5,2,1),0,0)["horizontal_deg"],goal_angles((5,-2,1),0,0)["horizontal_deg"])
    def test_endpoints(self):
        path=trajectory((0,0,1),(5,0,.5),.5)
        self.assertEqual(path[0][1],(0,0,1))
        self.assertEqual(path[-1][1],(5,0,.5))
    def test_missing(self):
        self.assertEqual(assess((0,0,1),(5,0,1),.5,None,1)["status"],"unknown")
    def test_block(self):
        self.assertEqual(assess((0,0,1),(5,0,1),.5,[Track("d",(2.5,0,1.3))],1)["status"],"potential_obstruction")
    def test_clear(self):
        self.assertEqual(assess((0,0,1),(5,0,1),.5,[Track("d",(2.5,4,1))],1)["status"],"clear_in_model")
    def test_uncertain(self):
        self.assertEqual(assess((0,0,1),(5,0,1),.5,[Track("d",(2.5,4,1),confidence=.2)],1)["status"],"uncertain")
    def test_invalid(self):
        with self.assertRaises(ValueError): trajectory((0,0,1),(5,0,1),0)
    def test_comparison(self):
        opts=[{"id":"a","kind":"shot","target":[5,0,1],"duration_s":.5},{"id":"b","kind":"pass","target":[0,5,1],"duration_s":.5}]
        self.assertEqual(compare_options((0,0,1),opts,[Track("d",(2.5,0,1.3))],1)[0]["id"],"b")

    def test_explicit_arm_blocks_otherwise_clear_lane(self):
        from source.spatial_decision_3d import ReachSegment
        start,end=(0,0,1),(5,0,1)
        plain=Track("d",(2.5,1.3,1),radius=.3)
        arm=ReachSegment("left_arm",(0,0,0),(0,-1.3,0),.12)
        explicit=Track("d",plain.position,radius=.3,reach_segments=(arm,))
        self.assertEqual(assess(start,end,.3,[plain],1)["status"],"clear_in_model")
        r=assess(start,end,.3,[explicit],1)
        self.assertEqual(r["status"],"potential_obstruction")
        self.assertEqual(r["closest_part"],"left_arm")

    def test_capsule_endpoint_distance_and_validation(self):
        from source.spatial_decision_3d import ReachSegment, segment_distance
        self.assertAlmostEqual(segment_distance((2,0,0),(0,0,0),(1,0,0)),1)
        self.assertAlmostEqual(segment_distance((.5,1,0),(0,0,0),(1,0,0)),1)
        self.assertAlmostEqual(segment_distance((1,0,0),(0,0,0),(0,0,0)),1)
        with self.assertRaises(ValueError):
            ReachSegment("left_arm",(0,0,0),(0,3,0),.12)
        part=ReachSegment("body",(0,0,0),(0,0,1),.2)
        with self.assertRaises(ValueError):
            Track("d",(0,0,0),reach_segments=(part,part))

if __name__=="__main__": unittest.main()
