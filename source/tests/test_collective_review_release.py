import unittest
from services.collective_review import append,build,context,validate

def fixture():
    def player(side,cap,x,y):
        return dict(side=side,cap_number=cap,metrics={'observed_s':.2},segments=[[dict(second=0,x_m=x,y_m=y),dict(second=.2,x_m=x,y_m=y)]])
    return {'advanced_motion':{'status':'experimental_partial','analysis_id':3,'length_m':25,'width_m':20,'players':[player('for',2,14,10),player('for',3,20,8),player('against',4,22,10),player('against',1,24,10)]},'automatic':{'summary':{'metric_field_map':{'calibration_provenance':'manual_reviewed_anchors','revision':'abc'},'identity_reviews':{'tracks':{'1':{'side':'for','cap_number':2}}}}}}

def input_row(s):
    return dict(binding=context(s),start_s=0,end_s=.2,period=1,attacking_side='for',attackers=['for:2','for:3'],defenders=['against:4','against:1'],carrier='for:2',goal_x=25,control_reviewed=True,roster_reviewed=True,evidence='QA synthetic',center='for:3',marker='against:4',keeper='against:1',goal_width_m=3,assumed_lateral_span_m=1.2)

def saved():
    s=fixture();s['automatic']['summary']['collective_reviews']=append(s,input_row(s));return s

class CollectiveReleaseTests(unittest.TestCase):
    def test_build(self):
        r=build(saved(),local_source=True);self.assertEqual(r['status'],'experimental_partial');p=r['reports'][0]['possession_geometry'][0];self.assertAlmostEqual(p['observed_s'],.2);self.assertEqual(p['keeper_geometry']['keeper'],'against:1');self.assertEqual(p['center_geometry']['center'],'for:3');self.assertAlmostEqual(sum(p['spatial_dominance']['nominal_mean_area_m2'].values()),500)
    def test_no_review(self):self.assertEqual(build(fixture(),local_source=True)['reports'],[])
    def test_nonlocal(self):self.assertEqual(build(saved(),local_source=False)['status'],'unavailable')
    def test_stale_identity(self):
        s=saved();s['automatic']['summary']['identity_reviews']['tracks']['1']['cap_number']=5;self.assertEqual(build(s,local_source=True)['reports'],[])
    def test_stale_calibration(self):
        s=saved();s['automatic']['summary']['metric_field_map']['revision']='new';self.assertEqual(build(s,local_source=True)['reports'],[])
    def test_overlap(self):
        s=saved();self.assertRaises(ValueError,append,s,input_row(s))
    def test_wrong_team(self):
        s=fixture();r=input_row(s);r['attackers'].append('against:1');self.assertRaises(ValueError,append,s,r)
    def test_bad_role(self):
        s=fixture();r=input_row(s);r['keeper']='against:4';self.assertRaises(ValueError,append,s,r)
    def test_missing_control(self):
        s=fixture();r=input_row(s);r['control_reviewed']=False;self.assertRaises(ValueError,append,s,r)
    def test_long_window(self):
        s=fixture();r=input_row(s);r['end_s']=16;self.assertRaises(ValueError,append,s,r)
    def test_forged_binding(self):
        s=fixture();r=input_row(s);r['binding']['analysis_id']=7;self.assertRaises(ValueError,append,s,r)
    def test_no_support(self):
        s=saved();s['advanced_motion']['players'][0]['segments']=[];p=build(s,local_source=True)['reports'][0]['possession_geometry'][0];self.assertEqual(p['coverage'],0);self.assertIsNone(p['shape']['attack']['width_m'])
if __name__=='__main__':unittest.main()
