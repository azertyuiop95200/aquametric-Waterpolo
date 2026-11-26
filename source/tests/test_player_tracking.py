import unittest
import cv2
import numpy as np
from services.player_tracking import track_frames
class TrackingTests(unittest.TestCase):
    def test_seeded_motion_and_missing_identity(self):
        frames=[]
        for i in range(12):
            f=np.full((180,320,3),(160,110,20),np.uint8)
            cv2.rectangle(f,(90+i*2,80),(105+i*2,95),(245,245,245),-1)
            cv2.line(f,(90+i*2,80),(105+i*2,95),(10,10,10),2)
            frames.append((i*.125,f))
        tracks,n=track_frames(frames,[{"x":97/320,"y":87/180,"colour":"light"}])
        self.assertEqual(len(tracks),1)
        self.assertGreater(tracks[0]["points"][-1]["x"],tracks[0]["points"][0]["x"]+.04)
        self.assertIsNone(tracks[0]["cap_number"])
        self.assertIsNone(tracks[0]["team"])
    def test_no_bridge_over_cut(self):
        a=np.zeros((100,100,3),np.uint8); b=np.full_like(a,255)
        tracks,n=track_frames([(0.,a),(.125,b)],[{"x":.5,"y":.5}])
        self.assertEqual(tracks,[])
