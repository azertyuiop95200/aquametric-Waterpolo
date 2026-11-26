import unittest
import numpy as np
import cv2
from services.sample_coverage import interval_union_seconds
from services.player_tracking import track_seed_bidirectional
from services.elite_performance import reduce_side
class CoverageAndTrackingTests(unittest.TestCase):
    def test_overlap(self):
        self.assertEqual(interval_union_seconds([(0,8),(3,12),(15,22)],20),17)
    def test_pass_subtypes_not_added_twice(self):
        r=reduce_side([{"event_type":k} for k in ("pass_complete","key_pass","assist","bad_pass")])
        self.assertEqual(r["pass_attempts"],4)
        self.assertEqual(r["passes"],3)
        self.assertEqual(r["pass_accuracy"],75)
    def test_bidirectional(self):
        frames=[]
        for i in range(17):
            f=np.full((180,320,3),100,np.uint8)
            cv2.rectangle(f,(90+i,80),(105+i,95),(245,245,245),-1)
            cv2.line(f,(90+i,80),(105+i,95),(5,5,5),2)
            frames.append((i*.125,f))
        rows,n=track_seed_bidirectional(reversed(frames[:9]),frames[8:],[{"x":105/320,"y":87/180,"colour":"light"}])
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]["points"]),17)
        self.assertEqual(rows[0]["points"][0]["second"],0)
        self.assertEqual(rows[0]["points"][-1]["second"],2)
