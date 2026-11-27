import unittest
import cv2,numpy as np
from services.ball_motion_review import propose, scan_motion_clip

def frames():
    out=[]
    for x in (100,110,120):
        f=np.full((720,1280,3),120,np.uint8);cv2.circle(f,(x,300),6,(60,60,60),-1);out.append(f)
    return out

def seeds():return [dict(frame=1,x=90/1280,y=300/720,reviewed=True),dict(frame=2,x=100/1280,y=300/720,reviewed=True)]
class MotionTests(unittest.TestCase):
    def test_motion(self):
        r=propose(*frames(),frame_index=3,seeds=seeds());self.assertEqual(r['status'],'candidates');self.assertFalse(r['confirmed']);self.assertLess(abs(r['candidates'][0]['x']*1280-110),8)
    def test_static(self):
        f=frames()[0];r=propose(f,f,f,frame_index=3,seeds=seeds());self.assertEqual(r['candidates'],[])
    def test_cut(self):
        a,b,c=frames();a[:]=255;self.assertEqual(propose(a,b,c,frame_index=3,seeds=seeds())['status'],'scene_motion_refused')
    def test_invalid_seed(self):
        s=seeds();s[0]['reviewed']=False
        with self.assertRaises(ValueError):propose(*frames(),frame_index=3,seeds=s)
    def test_horizon(self):
        with self.assertRaises(ValueError):propose(*frames(),frame_index=8,seeds=seeds())
    def test_order(self):
        with self.assertRaises(ValueError):propose(*frames(),frame_index=3,seeds=seeds()[::-1])
    def test_shape(self):
        a,b,c=frames()
        with self.assertRaises(ValueError):propose(a,b,c[:100],frame_index=3,seeds=seeds())
    def test_unrelated_motion(self):
        a,b,c=frames();a[:]=120;b[:]=120;c[:]=120;cv2.circle(b,(800,500),6,(60,60,60),-1)
        self.assertEqual(propose(a,b,c,frame_index=3,seeds=seeds())['candidates'],[])
    def test_invalid_central_frame(self):
        a,b,c=frames()
        with self.assertRaises(ValueError):propose(a,None,c,frame_index=3,seeds=seeds())
    def test_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.avi';w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'MJPG'),25,(1280,720))
            self.assertTrue(w.isOpened())
            for i in range(6):
                f=np.full((720,1280,3),120,np.uint8);cv2.circle(f,(80+10*i,300),6,(60,60,60),-1);w.write(f)
            w.release()
            r=scan_motion_clip(p,3,seeds());self.assertEqual(r['frame_index'],3);self.assertEqual(r['status'],'candidates')
            self.assertFalse(r['pts_validated']);self.assertFalse(r['seed_review_verified_by_server'])
            with self.assertRaises(ValueError):scan_motion_clip(p,5,seeds())
    def test_invalid_path(self):
        with self.assertRaises(ValueError):scan_motion_clip('missing.mp4',3,seeds())
