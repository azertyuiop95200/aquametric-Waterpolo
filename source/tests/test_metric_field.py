import unittest
import cv2
import numpy as np
from services.metric_field import calibrate,project,measure
class MetricTests(unittest.TestCase):
    def test_goal_relative(self):
        # Known perspective, goal mouth and both sideline markers.
        H=np.array([[.035,.014,.32],[.004,-.025,.48],[.015,.007,1.]])
        world=np.array([[[0.,-1.5],[0.,1.5],[0.,10.],[2.,10.],[6.,10.]]])
        anchors=cv2.perspectiveTransform(world,H)[0]
        cal=calibrate(anchors,20)
        p=cv2.perspectiveTransform(np.array([[[4.,-3.]]]),H)[0,0]
        x,y=project(cal,*p)
        self.assertAlmostEqual(x,4,places=4); self.assertAlmostEqual(y,-3,places=4)
    def test_dont_bridge_gaps(self):
        pts=[{"second":i*.125,"x_m":i*.1,"y_m":0.} for i in range(8)]
        pts += [None]+[{"second":2+i*.125,"x_m":10+i*.1,"y_m":0.} for i in range(8)]
        m=measure(pts)
        self.assertEqual(len(m["segments"]),2)
        self.assertLess(m["distance_m"],1.5)
    def test_degenerate(self):
        with self.assertRaises(ValueError):calibrate([[.5,.5]]*5)
    def test_raw_preserved(self):
        p=[{"second":i*.125,"x_m":i*.1,"y_m":0.} for i in range(8)]
        m=measure(p)
        self.assertEqual(m["raw_segments"][0][0]["x_m"],0.)
        self.assertNotEqual(m["segments"][0][0]["x_m"],0.)
        m["segments"][0][0]["x_m"]=99.
        self.assertEqual(m["raw_segments"][0][0]["x_m"],0.)
