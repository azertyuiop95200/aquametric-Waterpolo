import unittest
import numpy as np
from services.dynamic_calibration import fit_reference,transform,choose_projection
class CalibrationTests(unittest.TestCase):
    def test_metric_projection(self):
        p=np.array([[0,0],[25,0],[25,20],[0,20],[12.5,10]])
        h,e=fit_reference(p*10+20,p)
        self.assertAlmostEqual(e,0,places=5)
        self.assertTrue(np.allclose(transform(h,(145,120)),(12.5,10)))
    def test_disagree(self):
        a={'x_m':2,'y_m':1,'alignment_error_px':.2};b=dict(a,x_m=4)
        self.assertIsNone(choose_projection([a,b]))
    def test_consensus(self):
        a={'x_m':2,'y_m':1,'alignment_error_px':.2};b=dict(a,x_m=2.2,alignment_error_px=.1)
        self.assertEqual(choose_projection([a,b]),b)
    def test_degenerate(self):
        with self.assertRaises(ValueError):fit_reference([[i,0] for i in range(5)],[[i,0] for i in range(5)])
    def test_invalid(self):
        with self.assertRaises(ValueError):fit_reference([[0,0]],[[0,0]])
    def test_empty(self):self.assertIsNone(choose_projection([]))
