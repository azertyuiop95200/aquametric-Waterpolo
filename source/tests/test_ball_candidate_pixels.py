import unittest
import tempfile
from pathlib import Path
import cv2
import numpy as np
from services.ball_candidate import scan_windows

class BallPixelTests(unittest.TestCase):
    def test_video_pixels(self):
        with tempfile.TemporaryDirectory() as d:
            for mode in ('moving','static','ambiguous','absent'):
                p=Path(d)/(mode+'.mp4')
                out=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'mp4v'),8,(320,180))
                self.assertTrue(out.isOpened())
                for i in range(32):
                    frame=np.full((180,320,3),(170,110,25),dtype=np.uint8)
                    cv2.rectangle(frame,(0,0),(320,18),(20,20,20),-1)
                    cv2.circle(frame,(35,9),5,(0,230,255),-1)
                    if mode in ('moving','ambiguous','static'):
                        x=65+4*i if mode!='static' else 65
                        cv2.circle(frame,(x,85),5,(0,230,255),-1)
                    if mode=='ambiguous': cv2.circle(frame,(250-2*i,115),5,(0,230,255),-1)
                    out.write(frame)
                out.release()
                result=scan_windows(p,4,[{'second':1.5}])
                self.assertEqual(len(result['tracks']),1 if mode=='moving' else 0,mode)
                if mode=='moving':
                    self.assertGreaterEqual(len(result['tracks'][0]['points']),20)
