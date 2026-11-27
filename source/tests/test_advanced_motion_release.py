import unittest,json
from services.advanced_motion_report import build

def fixture():
    t={'id':1,'segments':[[{'second':0,'x_m':1,'y_m':-2},{'second':.2,'x_m':1.4,'y_m':-2},{'second':.4,'x_m':1.8,'y_m':-2}]]}
    return {'automatic':{'summary':{'metric_field_map':{'status':'estimated','goal_relative':True,'revision':'r','length_m':25,'width_m':20,'tracks':[t]},'identity_reviews':{'tracks':{'1':{'provenance':'coach_review','side':'for','cap_number':4,'evidence':'reviewed'}}}}},'identity_analysis':{'analysis_id':3,'calibration_revision':'r','players':[{'side':'for','cap_number':4,'track_ids':[1]}]}}
class ReleaseTests(unittest.TestCase):
    def test_motion(self):
        r=build(fixture());self.assertEqual(r['status'],'experimental_partial');p=r['players'][0];self.assertAlmostEqual(p['metrics']['distance_m'],.8);self.assertEqual(p['segments'][0][0]['y_m'],8);self.assertIsNone(r['playing_seconds']);json.dumps(r,allow_nan=False)
    def test_missing(self):self.assertEqual(build({})['status'],'unavailable')
    def test_stale(self):
        f=fixture();f['identity_analysis']['calibration_revision']='stale';self.assertEqual(build(f)['status'],'unavailable')
    def test_unreviewed(self):
        f=fixture();f['automatic']['summary']['identity_reviews']={};self.assertEqual(build(f)['players'],[])
    def test_unverified_source(self):
        f=fixture();f['automatic']['summary']['analysis_outcome']='source_unverified';self.assertEqual(build(f)['status'],'unavailable')
    def test_gap(self):
        f=fixture();f['automatic']['summary']['metric_field_map']['tracks'][0]['segments'][0][1]['y_m']=99;self.assertEqual(build(f)['status'],'unavailable')
    def test_duplicate_identity(self):
        f=fixture();f['identity_analysis']['players']*=2;self.assertEqual(build(f)['status'],'unavailable')
if __name__=='__main__':unittest.main()
