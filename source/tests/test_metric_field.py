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

    def test_linear_preserves_endpoints_and_input(self):
        import copy
        pts=[dict(second=i*.125,x_m=i*.1,y_m=0.) for i in range(8)]
        original=copy.deepcopy(pts);r=measure(pts)
        self.assertEqual(pts,original)
        self.assertEqual(r["distance_m"],.7)
        self.assertEqual(r["raw_distance_m"],.7)
        self.assertEqual(r["segments"][0][-1]["raw_x_m"],pts[-1]["x_m"])
    def test_invalid_and_short(self):
        pts=[dict(second=i*.125,x_m=i*.1,y_m=0.) for i in range(4)]
        r=measure(pts+[dict(second=1,x_m=float("nan"),y_m=0)])
        self.assertEqual(r["invalid_points"],1)
        self.assertEqual(r["short_segment_points"],4)
        self.assertIsNone(r["distance_m"])
    def test_final_speed(self):
        import random,math
        rng=random.Random(12)
        for _ in range(100):
            pts=[dict(second=0,x_m=0.,y_m=0.)]
            for i in range(1,12):
                a=rng.random()*6.28;d=rng.uniform(.02,.4)
                pts.append(dict(second=i*.125,x_m=pts[-1]["x_m"]+d*math.cos(a),y_m=pts[-1]["y_m"]+d*math.sin(a)))
            for seg in measure(pts)["segments"]:
                for a,b in zip(seg,seg[1:]):
                    self.assertLessEqual(math.hypot(b["x_m"]-a["x_m"],b["y_m"]-a["y_m"]),3.5*(b["second"]-a["second"])+1e-9)

    def test_repeated_track(self):
        p=[dict(second=i*.125,x_m=i*.1,y_m=0.) for i in range(8)]
        r=measure(p*2)
        self.assertEqual(r["distance_m"],.7)
        self.assertEqual(r["observed_seconds"],.875)
        self.assertEqual(r["nonmonotonic_points"],8)
    def test_gap_does_not_reset(self):
        p=[dict(second=i*.125,x_m=i*.1,y_m=0.) for i in range(8)]
        self.assertEqual(measure(p+[None]+p)["nonmonotonic_points"],8)
    def test_ordered(self):
        p=[dict(second=i*.125,x_m=i*.1,y_m=0.) for i in range(8)]
        self.assertEqual(measure(p+[dict(q,second=q["second"]+2) for q in p])["distance_m"],1.4)
    def test_duplicate_breaks(self):
        p=[dict(second=i*.125,x_m=i*.1,y_m=0.) for i in range(8)]
        r=measure(p[:4]+[p[3]]+p[4:])
        self.assertEqual(r["nonmonotonic_points"],1)
        self.assertIsNone(r["distance_m"])
