import unittest
from spatial_report_detail import map_scale, spatial_options, pass_network
from match_tactical_report import build_report
from test_match_tactical_report import Tests as Fixture

class PrecisionTests(unittest.TestCase):
    def test_density(self):
        r={'players':[{'map':{'observed_s':4,'cells':[{'share':.5,'w':2,'h':2},{'share':.5,'w':1,'h':2}]}}],'start_s':0,'end_s':8}
        map_scale(r); p=r['players'][0]; self.assertEqual(p['video_coverage'],.5); self.assertEqual([c['opacity'] for c in p['map']['cells']],[.5,1.])
    def test_options(self):
        r={'model_version':'replay-1','start':[2,2,1],'chosen':'a','complete_defence':True,'options':[{'id':'a','kind':'pass','target':[5,6,1],'clearance_m':.5,'status':'clear_in_model'},{'id':'b','kind':'shot','target':[25,10,1],'status':'potential_obstruction','clearance_m':-.1}]}
        o=spatial_options(r,25,20); self.assertEqual(o[0]['planar_length_m'],5); self.assertFalse(o[1]['chosen']); self.assertIsNone(o[0]['sport_probability']);r['complete_defence']=False; self.assertIsNone(spatial_options(r,25,20)[0]['clearance_m'])
    def test_duplicate_options(self):
        self.assertEqual(spatial_options({'model_version':'replay-1','start':[2,2,1],'chosen':'a','options':[{'id':'a'},{'id':'a'}]},25,20),[])
    def fixture(self):
        f=Fixture().fixture();f['events'][0]['perspective']='for';f.update(pass_summary={'source':'1','period':1,'coverage_complete':False,'actions':[{'id':'p','state':'observed_pass','outcome':'completed','team':'blancs','release_first_free_s':60,'control_s':60.5,'related_event_id':1,'event_relation':'same_action'}]},pass_links={'p':{'source':'1','period':1,'provenance':'coach_review','side':'for','sender_id':'4','receiver_id':'6'}},team_to_side={'blancs':'for','bleus':'against'});return f
    def test_network_join(self):
        r=build_report(**self.fixture()); self.assertEqual(r['pass_network']['edges'][0]['count'],1);self.assertEqual(r['pass_network']['identity_coverage'],1);self.assertIsNone(r['pass_network']['match_completion_rate'])
    def test_unknown_receiver(self):
        f=self.fixture();f['pass_links']={};r=build_report(**f)['pass_network'];self.assertEqual(r['identity_coverage'],0);self.assertEqual(r['edges'],[])
    def test_cross_source(self):
        f=self.fixture();f['pass_summary']['source']='2';self.assertRaises(ValueError,build_report,**f)
    def test_conflict(self):
        f=self.fixture();f['events'][0]['perspective']='against';r=build_report(**f)['pass_network'];self.assertEqual(r['excluded'],{'event_conflict':1})
    def test_duplicate_pass(self):
        f=self.fixture();f['pass_summary']['actions']*=2;self.assertRaises(ValueError,build_report,**f)
    def test_wrong_dimensions(self):
        f=self.fixture();f['metric']['length_m']=30;self.assertRaises(ValueError,build_report,**f)
if __name__=='__main__':unittest.main()
