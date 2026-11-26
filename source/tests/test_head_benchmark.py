import unittest
from services.head_benchmark import evaluate
class BenchmarkTests(unittest.TestCase):
    def test_duplicates(self):
        r=evaluate([(0,0)],[(1,0),(2,0)],3)
        self.assertEqual((r['tp'],r['fp'],r['fn']),(1,1,0))
    def test_empty(self):
        r=evaluate([],[])
        self.assertIsNone(r['precision']);self.assertIsNone(r['recall']);self.assertIsNone(r['f1'])
    def test_reassignment(self):
        r=evaluate([(0,0),(3,0)],[(1,0),(-2,0)],2)
        self.assertEqual((r['tp'],r['fp'],r['fn']),(2,0,0))
    def test_threshold(self):
        r=evaluate([(0,0)],[(21,0)],20)
        self.assertEqual((r['tp'],r['fp'],r['fn']),(0,1,1))
