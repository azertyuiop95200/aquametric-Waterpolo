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

if __name__=="__main__": unittest.main()
