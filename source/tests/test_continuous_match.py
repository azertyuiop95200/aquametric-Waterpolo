import unittest,tempfile,json,gzip
from pathlib import Path
import numpy as np,cv2
from services.continuous_match import scan,Tracker
class Coverage(unittest.TestCase):
    def test_all_decoded_frames_even_without_detections(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);v=p/'video.mp4';w=cv2.VideoWriter(str(v),cv2.VideoWriter_fourcc(*'mp4v'),25,(160,90))
            self.assertTrue(w.isOpened())
            for i in range(50):w.write(np.full((90,160,3),(130,90,25),np.uint8))
            w.release();r=scan(v,p/'rows.gz',p/'summary.json',160)
            self.assertEqual(r['processed_frames'],50);self.assertEqual(r['frame_coverage_pct'],100)
            with gzip.open(p/'rows.gz','rt') as f:rows=[json.loads(l) for l in f]
            self.assertEqual([r['frame'] for r in rows],list(range(50)))
            self.assertEqual(sum(bool(r['tracks']) for r in rows),0)
    def test_cut_does_not_reuse_id(self):
        t=Tracker();a=np.zeros((90,160,3),np.uint8);t.step(a,0);r=t.step(np.full_like(a,255),1);self.assertTrue(r[-1])
