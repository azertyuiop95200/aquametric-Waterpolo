import unittest
from timeline_audit import audit
class Tests(unittest.TestCase):
    def fixture(self): return {'source_duration_s':2,'clips':[{'file':'a','source_start_s':0,'source_end_s':1,'duration_s':1},{'file':'b','source_start_s':1,'source_end_s':2,'duration_s':1}]}
    def test_clean(self):
        r=audit(self.fixture()); self.assertEqual(r['issues'],[]); self.assertFalse(r['offsets_verified'])
    def test_gap(self):
        m=self.fixture(); m['clips'][1]['source_start_s']=1.1; self.assertEqual(audit(m)['issues'][0]['kind'],'boundary_gap_s')
    def test_overlap(self):
        m=self.fixture(); m['clips'][1]['source_start_s']=.8; self.assertLess(audit(m)['issues'][0]['seconds'],0)
    def test_duplicate(self):
        m=self.fixture(); m['clips'][1]['file']='a'; self.assertRaises(ValueError,audit,m)
    def test_nan(self):
        m=self.fixture(); m['clips'][0]['duration_s']=float('nan'); self.assertRaises(ValueError,audit,m)
    def test_end(self):
        m=self.fixture(); m['source_duration_s']=2.2; self.assertEqual(audit(m)['issues'][-1]['kind'],'source_end_delta_s')
    def test_empty(self): self.assertRaises(ValueError,audit,{'source_duration_s':0,'clips':[]})
if __name__=='__main__': unittest.main()
