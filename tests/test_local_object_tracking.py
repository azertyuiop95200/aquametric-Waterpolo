import unittest
import numpy as np
import cv2
from services.local_object_tracking import detect, Tracker, scan
from services.local_clip_scan import scan_clip

def point(x,y=.5,colour='cap_dark',kind='head'):
    return dict(x=x,y=y,colour=colour,kind=kind,status='candidate')

class LocalVisionTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(detect(np.zeros((720,1280,3),np.uint8)),[])
    def test_ball_proposal(self):
        hsv=np.full((720,1280,3),(90,110,150),np.uint8)
        cv2.circle(hsv,(640,360),9,(170,140,170),-1)
        ds=detect(cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR))
        self.assertTrue(any(d['kind']=='ball' and abs(d['x']-.5)<.01 and abs(d['y']-.5)<.01 for d in ds))
        self.assertTrue(all(d['status']=='candidate' for d in ds))
    def test_bad_image(self):
        with self.assertRaises(ValueError):detect(np.zeros((32,32,3),np.uint8))
    def test_same_id(self):
        t=Tracker();a=t.step(0,(720,1280),[point(.4)])[0]
        b=t.step(.08,(720,1280),[point(.401)])[0]
        self.assertEqual(a['track_id'],b['track_id'])
    def test_new_and_disappearance(self):
        t=Tracker();a=t.step(0,(720,1280),[point(.4)])[0]
        t.step(.08,(720,1280),[])
        b=t.step(.16,(720,1280),[point(.4)])[0]
        self.assertNotEqual(a['track_id'],b['track_id'])
    def test_cut(self):
        t=Tracker();a=t.step(0,(720,1280),[point(.4)])[0]
        b=t.step(.08,(720,1280),[point(.4)],cut=True)[0]
        self.assertNotEqual(a['track_id'],b['track_id'])
    def test_gap(self):
        t=Tracker();a=t.step(0,(720,1280),[point(.4)])[0]
        b=t.step(.5,(720,1280),[point(.4)])[0]
        self.assertNotEqual(a['track_id'],b['track_id'])
    def test_ambiguity(self):
        t=Tracker();a=t.step(0,(720,1280),[point(.4)])[0]
        b=t.step(.08,(720,1280),[point(.399),point(.401)])
        self.assertNotIn(a['track_id'],[r['track_id'] for r in b])
        self.assertEqual(len(set(r['track_id'] for r in b)),2)
    def test_colour_change(self):
        t=Tracker();a=t.step(0,(720,1280),[point(.4)])[0]
        b=t.step(.08,(720,1280),[point(.4,colour='cap_light')])[0]
        self.assertNotEqual(a['track_id'],b['track_id'])
    def test_bad_time(self):
        t=Tracker();t.step(1,(720,1280),[])
        with self.assertRaises(ValueError):t.step(1,(720,1280),[])
    def test_no_identity(self):
        t=Tracker();t.step(0,(720,1280),[point(.5)])
        s=t.summary();self.assertFalse(s['identity_verified']);self.assertFalse(s['metrics_validated'])
        self.assertFalse(s['tracks'][0]['identity_verified'])
    def test_scan_empty(self):
        r=scan([(0,np.zeros((720,1280,3),np.uint8))])
        self.assertEqual(len(r['frames']),1);self.assertEqual(r['tracklets_total'],0)
    def test_clip_limits(self):
        with self.assertRaises(ValueError):scan_clip('missing.mp4',0,76)
        with self.assertRaises(ValueError):scan_clip('missing.mp4',-1)
    def test_clip_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.avi'
            w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'MJPG'),25,(320,240))
            self.assertTrue(w.isOpened())
            for i in range(12):w.write(np.zeros((240,320,3),np.uint8))
            w.release()
            r=scan_clip(p,2,7)
            self.assertEqual([x['source_frame_index'] for x in r['frames']],[2,4,6,8])
            self.assertEqual(r['end_frame_exclusive'],9)
            self.assertFalse(r['pts_validated'])
