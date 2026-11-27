import unittest
import numpy as np
import cv2
from services.calibration_validation import check_calibration

class CalibrationValidationTests(unittest.TestCase):
    def setUp(self):
        self.H=np.array([[.035,.014,.32],[.004,-.025,.48],[.015,.007,1.]])
        self.world=np.array([[0.,-1.5],[0.,1.5],[0.,10.],[2.,10.],[6.,10.]])
        self.anchors=cv2.perspectiveTransform(self.world[None],self.H)[0]
        self.points=np.array([[3.,-4.],[5.,5.],[12.,-5.],[18.,3.]])
        self.checks=[dict(id=str(i),image=xy.tolist(),metric=p.tolist()) for i,(xy,p) in enumerate(zip(cv2.perspectiveTransform(self.points[None],self.H)[0],self.points))]
    def test_exact_independent_geometry(self):
        r=check_calibration(self.anchors,20,25,self.checks,dimensions_verified=True)
        self.assertEqual(r["status"],"passed_declared_landmarks")
        self.assertLess(r["mean_error_m"],.0001)
    def test_unverified_dimensions(self):
        r=check_calibration(self.anchors,20,25,self.checks)
        self.assertIn("dimensions_unverified",r["reasons"])
    def test_wrong_landmark_geometry(self):
        self.checks[0]["metric"][0]+=2
        r=check_calibration(self.anchors,20,25,self.checks,dimensions_verified=True)
        self.assertIn("error_threshold_exceeded",r["reasons"])
    def test_fit_point_not_holdout(self):
        self.checks[0]["image"]=self.anchors[0].tolist()
        with self.assertRaises(ValueError):check_calibration(self.anchors,20,25,self.checks)
    def test_insufficient_spread(self):
        r=check_calibration(self.anchors,20,25,self.checks[:2],dimensions_verified=True)
        self.assertIn("insufficient_independent_spatial_coverage",r["reasons"])
    def test_duplicate_landmark(self):
        self.checks[1]["id"]=self.checks[0]["id"]
        with self.assertRaises(ValueError):check_calibration(self.anchors,20,25,self.checks)
    def test_invalid_threshold(self):
        with self.assertRaises(ValueError):check_calibration(self.anchors,20,25,self.checks,mean_limit_m=.8,max_limit_m=.3)
