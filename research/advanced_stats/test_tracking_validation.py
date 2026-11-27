import unittest
from tracking_validation import evaluate

class ValidationTests(unittest.TestCase):
    def test_seed_excluded(self):
        r=evaluate({('A',0):(0,0),('A',1):(0,0)},{('A',0):(0,0),('A',1):(3,4)},seed_frames=[0]);self.assertEqual(r['expected'],1);self.assertEqual(r['median_px'],5)
    def test_missing_counts(self):
        r=evaluate({('A',1):(0,0),('B',1):(0,0)},{('A',1):(0,0)});self.assertEqual(r['coverage'],.5);self.assertEqual(r['usable_fraction'],.5)
    def test_empty(self):
        r=evaluate({},{});self.assertIsNone(r['median_px']);self.assertIsNone(r['coverage'])
    def test_no_predictions(self):
        r=evaluate({('A',1):(0,0)},{});self.assertIsNone(r['median_px']);self.assertEqual(r['usable_fraction'],0)
    def test_threshold(self):
        r=evaluate({('A',1):(0,0),('B',1):(0,0)},{('A',1):(6,8),('B',1):(11,0)});self.assertEqual(r['within_tolerance'],1);self.assertEqual(r['coverage'],1)
    def test_invalid(self):
        with self.assertRaises(ValueError):evaluate({('A',1):(0,0)},{('A',1):(float('nan'),0)})
    def test_quantile(self):
        r=evaluate({('A',1):(0,0),('B',1):(0,0)},{('A',1):(0,0),('B',1):(10,0)});self.assertAlmostEqual(r['p90_px'],9)
if __name__=='__main__':unittest.main()
