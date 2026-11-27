import unittest
from tracklet_union import merge_tracklets
from directional_effort import directional_effort
from advanced_tracking import reviewed_motion
from match_report_sequence import build_match_sequence
from test_match_tactical_report import Tests as Fixture


def seg(rows): return [dict(second=t,x_m=x,y_m=y) for t,x,y in rows]
def tr(i,*segments): return dict(id=i,segments=list(segments))
C=dict(sprint_mps=1.5,min_sprint_s=.15)


class UnionTests(unittest.TestCase):
    def test_duplicates(self):
        a=seg([(0,0,0),(.2,.4,0),(.4,.8,0)])
        r=merge_tracklets([tr(1,a),tr(2,a)])
        self.assertAlmostEqual(r['observed_s'],.4); self.assertAlmostEqual(r['overlap_s'],.4); self.assertEqual(len(r['segments']),1)
    def test_conflict(self):
        a=seg([(0,0,0),(.2,.4,0)]); b=seg([(0,0,1),(.2,.4,1)])
        r=merge_tracklets([tr(1,a),tr(2,b)]); self.assertEqual(r['observed_s'],0); self.assertAlmostEqual(r['conflict_s'],.2)
    def test_fragment_gap(self):
        a=seg([(0,0,0),(.2,.4,0)]); b=seg([(1,1,0),(1.2,1.4,0)])
        r=merge_tracklets([tr(1,a),tr(2,b)]); self.assertAlmostEqual(r['observed_s'],.4); self.assertEqual(len(r['segments']),2)
        self.assertIsNone(directional_effort(r['segments'],**C)['peak_vector_acceleration_mps2'])
    def test_partial_conflict_at_endpoint(self):
        a=seg([(0,0,0),(.2,.6,0)]); b=seg([(0,.8,0),(.2,.6,0)])
        r=merge_tracklets([tr(1,a),tr(2,b)]); self.assertAlmostEqual(r['conflict_s'],.2)
    def test_turn(self):
        a=seg([(0,0,0),(.2,.4,0),(.4,.4,.4)])
        r=directional_effort([a],**C); self.assertEqual(r['turn_count'],1); self.assertAlmostEqual(r['turns'][0]['angle_deg'],90); self.assertAlmostEqual(r['peak_vector_acceleration_mps2'],2**.5*10)
    def test_repeated(self):
        a=seg([(0,0,0),(.2,.4,0),(.4,.4,0),(.6,.8,0)])
        r=directional_effort([a],**C); self.assertEqual(r['repeated_sprint_pairs'],1); self.assertAlmostEqual(r['observed_inter_sprint_gaps_s'][0],.2)
        b=seg([(0,0,0),(.2,.4,0),(1,.4,0),(1.2,.8,0)])
        self.assertEqual(directional_effort([b],**C)['repeated_sprint_pairs'],0)
    def test_report_integration(self):
        f=Fixture().fixture(); a=seg([(0,1,1),(.2,1.4,1)]); b=seg([(1,2,1),(1.2,2.4,1)])
        f['metric']['tracks']=[tr(1,a),tr(2,b)]; f['identity']['players'][0]['track_ids']=[1,2]
        r=build_match_sequence([f])['reports'][0]; p=r['players'][0]
        self.assertAlmostEqual(p['metrics']['distance_m'],.8); self.assertAlmostEqual(p['map']['observed_s'],.4); self.assertAlmostEqual(r['timeline'][0]['movement'][0]['metrics']['distance_m'],.8)
    def test_unobservable_turn(self):
        a=seg([(0,0,0),(.2,0,0),(.4,0,0)]); self.assertIsNone(directional_effort([a],**C)['turn_count'])
if __name__=='__main__':unittest.main()
