import unittest
from services.ball_continuity import associate

def row(i,points=(),cut=False):return {'frame':i,'second':i*.04,'ball_candidates':points,'cut':cut}
class BallContinuityTests(unittest.TestCase):
    def test_motion_and_missing(self):
        r=associate([row(i,[(.3+i*.005,.5,'red')] if i!=2 else []) for i in range(7)])
        self.assertEqual(r['tracklets'],1);self.assertEqual(r['counts']['observations'],6)
        self.assertEqual(r['review_examples'][0]['missing_frames'],1)
    def test_cut(self):
        r=associate([row(i,[(.3,.5,'red')],cut=i==3) for i in range(6)])
        self.assertEqual(r['tracklets'],2)
    def test_ambiguity_terminates(self):
        r=associate([row(0,[(.3,.5,'red')]),row(1,[(.299,.5,'red'),(.301,.5,'red')])])
        self.assertEqual(r['tracklets'],3);self.assertEqual(r['counts']['links'],0)
    def test_competing_tracks(self):
        r=associate([row(0,[(.299,.5,'red'),(.301,.5,'red')]),row(1,[(.3,.5,'red')])])
        self.assertEqual(r['tracklets'],3)
    def test_gap(self):
        r=associate([row(i,[(.3,.5,'red')] if i in (0,5) else []) for i in range(6)])
        self.assertEqual(r['tracklets'],2)
    def test_missing_frame(self):
        with self.assertRaises(ValueError):associate([row(0),row(2)])
    def test_invalid_point(self):
        with self.assertRaises(ValueError):associate([row(0,[(float('nan'),.5,'red')])])
    def test_empty(self):
        r=associate([row(i) for i in range(10)])
        self.assertEqual(r['counts']['frames'],10);self.assertEqual(r['tracklets'],0)
