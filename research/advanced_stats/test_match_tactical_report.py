import unittest,json
from match_tactical_report import build_report,occupancy,adapt_metric

def pts(x0,x1): return [{'second':0.,'x_m':x0,'y_m':1.},{'second':.2,'x_m':x1,'y_m':1.}]
class Tests(unittest.TestCase):
    def fixture(self):
        return dict(source='1',period=1,start=0,end=120,length=25,width=20,metric={'coordinate_system':'pool_metric_2d','source':'1','period':1,'tracks':[{'id':1,'segments':[pts(1.8,2.2)]}]},identity={'players':[{'side':'for','cap_number':4,'track_ids':[1]}]},events=[{'id':1,'source':'1','period':1,'confidence':'VERIFIED','second':60,'event_type':'pass_complete'}],spatial_reviews={},sprint_mps=1.5,min_sprint_s=.35)
    def test_map(self):
        r=occupancy([pts(1.8,2.2)],25,20,2,0,1); self.assertAlmostEqual(r['observed_s'],.2); self.assertEqual(len(r['cells']),2); self.assertAlmostEqual(r['cells'][0]['seconds'],.1)
    def test_timeline(self):
        r=build_report(**self.fixture()); self.assertEqual(r['timeline'][0]['confirmed_counts'],{}); self.assertEqual(r['timeline'][1]['cumulative_confirmed_counts'],{'pass_complete':1}); self.assertIsNone(r['event_coverage']); json.dumps(r,allow_nan=False)
    def test_review(self):
        f=self.fixture(); f['spatial_reviews']={1:{'video_source':'1','period':1,'result':{'decision_second':59,'length_m':25,'width_m':20,'start':[1,1,1],'chosen':'p','complete_defence':True,'options':[{'id':'p','kind':'pass','target':[2,2,1],'clearance_m':.5,'status':'clear_in_model'}]}}}; r=build_report(**f); self.assertEqual(r['actions'][0]['spatial']['clearance_m'],.5); f['spatial_reviews'][1].pop('video_source'); self.assertIsNone(build_report(**f)['actions'][0]['spatial'])
    def test_candidate(self):
        f=self.fixture(); f['events'][0]['confidence']='candidate'; self.assertEqual(build_report(**f)['actions'],[])
    def test_duplicate(self):
        f=self.fixture(); f['events']*=2
        with self.assertRaises(ValueError):build_report(**f)
    def test_wrong_scope(self):
        f=self.fixture(); f['metric']['coordinate_system']='image_normalized'
        with self.assertRaises(ValueError):build_report(**f)
    def test_missing(self):
        f=self.fixture(); f['metric']['tracks']=[]; self.assertIsNone(build_report(**f)['players'][0]['map'])
    def test_coordinate_adapter(self):
        raw={'status':'estimated','goal_relative':True,'length_m':25,'width_m':20,'tracks':[{'id':1,'segments':[[{'second':0,'x_m':2,'y_m':-3},{'second':.1,'x_m':-1,'y_m':0},{'second':.2,'x_m':3,'y_m':2}]]}]}
        r=adapt_metric(raw,source='1',period=1,reference_goal_x=25,lateral_sign=-1)
        self.assertEqual(r['tracks'][0]['segments'][0][0],{'second':0,'x_m':23,'y_m':13}); self.assertEqual(len(r['tracks'][0]['segments']),2); self.assertEqual(raw['tracks'][0]['segments'][0][0]['x_m'],2)
    def test_map_overlap(self):
        with self.assertRaises(ValueError): occupancy([pts(1.8,2.2),pts(1.8,2.2)],25,20,2,0,1)
if __name__=='__main__':unittest.main()
