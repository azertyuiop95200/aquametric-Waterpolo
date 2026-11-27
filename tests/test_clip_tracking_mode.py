import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
from services.local_clip_scan import scan_clip

class ClipModesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'test.avi';w=cv2.VideoWriter(str(self.p),cv2.VideoWriter_fourcc(*'MJPG'),25,(320,240));self.assertTrue(w.isOpened())
        for i in range(12):w.write(np.zeros((240,320,3),np.uint8))
        w.release()
    def test_default_unchanged(self):
        r=scan_clip(self.p,2,7);self.assertEqual(r['engine'],'local-colour-tracklets-v1');self.assertEqual([x['source_frame_index'] for x in r['frames']],[2,4,6,8]);self.assertEqual(r['object_scope'],'heads_and_ball_candidates')
    def test_optical_flow(self):
        r=scan_clip(self.p,2,7,tracking_mode='head_flow');self.assertEqual(r['engine'],'head-flow-tracklets-v2');self.assertEqual(r['object_scope'],'heads_only');self.assertEqual([x['source_frame_index'] for x in r['frames']],[2,4,6,8]);self.assertFalse(r['statistical_use_allowed']);self.assertFalse(r['metrics_validated']);self.assertFalse(r['identity_verified']);self.assertFalse(r['pts_validated'])
    def test_invalid_mode(self):
        for v in ('auto',None,[],True):
            with self.assertRaises(ValueError):scan_clip(self.p,tracking_mode=v)
    def test_refuse_dropped_frames(self):
        with patch.dict('services.local_clip_scan.MODES',{'baseline':lambda frames:{'frames':[]}}):
            with self.assertRaises(ValueError):scan_clip(self.p,2,7)
    def test_refuse_wrong_timing(self):
        with patch.dict('services.local_clip_scan.MODES',{'baseline':lambda frames:{'frames':[{'second':999} for _ in frames]}}):
            with self.assertRaises(ValueError):scan_clip(self.p,2,7)
    def test_tail(self):
        r=scan_clip(self.p,10,75,tracking_mode='head_flow');self.assertEqual(r['end_frame_exclusive'],12);self.assertEqual([f['source_frame_index'] for f in r['frames']],[10])
