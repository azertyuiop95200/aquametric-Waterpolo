import unittest
from possession_geometry import analyze_window, segment_distance
from match_report_sequence import build_match_sequence
from test_match_tactical_report import Tests as Fixture


def fixture(block=False,missing=False):
    report=dict(source='1',period=1,start_s=0,end_s=.2,length_m=25,width_m=20,players=[])
    for side,cap,x,y in [('for',1,5,5),('for',2,9,5),('against',1,7,5 if block else 8),('against',2,5,6)]:
        if missing and side=='against' and cap==2: continue
        report['players'].append(dict(side=side,cap_number=cap,metrics={},segments=[[dict(second=t,x_m=x,y_m=y) for t in (0,.2)]]))
    w=dict(id='p1',source='1',period=1,start_s=0,end_s=.2,attacking_side='for',control_reviewed=True,roster_reviewed=True,attackers=['for:1','for:2'],defenders=['against:1','against:2'],carrier='for:1',goal_x=25)
    return report,w

class GeometryTests(unittest.TestCase):
    def test_clear(self):
        r=analyze_window(*fixture()); self.assertAlmostEqual(r['lanes'][0]['clear_s'],.2); self.assertEqual(r['lanes'][0]['obstructed_s'],0); self.assertAlmostEqual(r['shape']['attack']['depth_m'],4)
    def test_blocked(self):
        r=analyze_window(*fixture(block=True)); self.assertAlmostEqual(r['lanes'][0]['obstructed_s'],.2); self.assertAlmostEqual(r['pressure'][0]['proximity_s'],.2)
    def test_missing(self):
        r=analyze_window(*fixture(missing=True)); self.assertEqual(r['coverage'],0); self.assertIsNone(r['lanes'][0]['clear_s']); self.assertIsNone(r['shape']['attack']['width_m'])
    def test_unverified(self):
        r,w=fixture(); w['control_reviewed']=False
        with self.assertRaises(ValueError): analyze_window(r,w)
    def test_other_source(self):
        r,w=fixture(); w['source']='2'
        with self.assertRaises(ValueError): analyze_window(r,w)
    def test_indeterminate(self):
        r,w=fixture(); r['players'][2]['segments'][0][0]['y_m']=5.5; r['players'][2]['segments'][0][1]['y_m']=5.8
        s=analyze_window(r,w,max_step_s=.2)['lanes'][0]; self.assertAlmostEqual(s['indeterminate_s'],.2); self.assertAlmostEqual(sum(s[k] for k in ('clear_s','obstructed_s','indeterminate_s')),.2)
    def test_segment_endpoint(self): self.assertAlmostEqual(segment_distance((5,1),(0,0),(2,0)),10**.5)
    def test_integration_missing(self):
        f=Fixture().fixture(); _,w=fixture(); f['possession_windows']=[w]; result=build_match_sequence([f])['reports'][0]['possession_geometry'][0]; self.assertEqual(result['coverage'],0)
    def test_overlap(self):
        f=Fixture().fixture(); _,w=fixture(); f['possession_windows']=[w,{**w,'id':'p2'}]
        with self.assertRaises(ValueError):build_match_sequence([f])
if __name__=='__main__':unittest.main()
