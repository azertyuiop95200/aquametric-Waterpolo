import unittest
from match_report_sequence import build_match_sequence
from test_match_tactical_report import Tests as BaseFixture

class SequenceTests(unittest.TestCase):
    def fixture(self): return BaseFixture().fixture()
    def test_motion_buckets(self):
        f=self.fixture(); f['bucket_s']=5; f['metric']['tracks'][0]['segments']=[[{'second':4.9,'x_m':1.,'y_m':1.},{'second':5.1,'x_m':1.4,'y_m':1.}]]
        r=build_match_sequence([f])['reports'][0]['timeline']; self.assertAlmostEqual(r[0]['movement'][0]['metrics']['distance_m'],.2); self.assertAlmostEqual(r[1]['movement'][0]['metrics']['distance_m'],.2); self.assertIsNone(r[2]['movement'][0]['metrics']['distance_m'])
    def test_nonadditive(self):
        f=self.fixture(); g=self.fixture(); g['source']=g['metric']['source']=g['events'][0]['source']='2'; g['events'][0]['id']=2
        r=build_match_sequence([f,g]); self.assertEqual(len(r['reports']),2); self.assertIsNone(r['global_totals'])
    def test_overlap(self):
        with self.assertRaises(ValueError):build_match_sequence([self.fixture(),self.fixture()])
    def test_event_duplicate(self):
        f=self.fixture();g=self.fixture();g['source']=g['metric']['source']=g['events'][0]['source']='2'
        with self.assertRaises(ValueError):build_match_sequence([f,g])
    def test_transition(self):
        f=self.fixture(); e=dict(id=9,status='opposite_endpoints',exact_count=1,start_s=2,end_s=4,source='1',period=1)
        f['transition_records']=[dict(evidence=e,metric_endpoints_reviewed=True,ball_start=(0,0),ball_end=(4,3),attack_axis=(1,0))]; r=build_match_sequence([f]); self.assertEqual(r['reports'][0]['transitions'][0]['progress_m'],4)
        f['transition_records'][0]['metric_endpoints_reviewed']=False; self.assertEqual(build_match_sequence([f])['reports'][0]['transitions'],[])
if __name__=='__main__':unittest.main()
