import unittest
from services.ball_control import control_report, normalize_control_intervals
def r(a,b,s="for",n=8,**kw):
    return dict(start_second=a,end_second=b,side=s,cap_number=n,confidence=.9,evidence="Contrôle continu visible",identity_evidence="bonnet visible",team_evidence="équipe visible")|kw
class ControlTests(unittest.TestCase):
    def test_overlap_no_double_count(self):
        x=control_report([r(1,4),r(3,5)])
        self.assertEqual(x["teams"]["for"]["control_video_seconds"],4)
        self.assertEqual(x["teams"]["for"]["players"],[{"cap":8,"control_video_seconds":4}])
    def test_cross_team_conflict(self):
        x=control_report([r(1,4),r(3,5,"against")])
        self.assertEqual(x["teams"]["for"]["control_video_seconds"],2)
        self.assertEqual(x["teams"]["against"]["control_video_seconds"],1)
        self.assertEqual(x["teams"]["unknown"]["control_video_seconds"],1)
        self.assertEqual(x["conflicting_video_seconds"],1)
    def test_same_team_conflict(self):
        x=control_report([r(1,4),r(3,5,n=9)])
        self.assertEqual(x["teams"]["for"]["control_video_seconds"],4)
        self.assertEqual(x["teams"]["for"]["unattributed_video_seconds"],1)
    def test_gap_not_filled(self):
        x=control_report([r(0,1),r(3,4)])
        self.assertEqual(x["observed_video_seconds"],2)
        self.assertEqual(len(x["intervals"]),2)
    def test_excludes_replays_and_low_confidence(self):
        x=control_report([r(0,1,is_replay=True),r(2,3,confidence=.3)])
        self.assertEqual(x["excluded_intervals"],2)
        self.assertIsNone(x["teams"]["for"]["control_video_seconds"])
    def test_requires_team_and_number_evidence(self):
        x=control_report([r(0,1,team_evidence=""),r(2,3,identity_evidence="")])
        self.assertEqual(x["teams"]["unknown"]["control_video_seconds"],1)
        self.assertEqual(x["teams"]["for"]["unattributed_video_seconds"],1)
    def test_core_clipping(self):
        seg=dict(clip_start=10,clip_end=20,start=12,end=18,index=2)
        x=normalize_control_intervals([r(1,9)],seg,"water_polo")
        self.assertEqual((x[0]["start_second"],x[0]["end_second"]),(12,18))
        self.assertEqual(x[0]["segment_index"],2)
    def test_out_of_bounds(self):
        seg=dict(clip_start=10,clip_end=20,start=12,end=18,index=2)
        with self.assertRaises(ValueError):normalize_control_intervals([r(1,11)],seg,"water_polo")
    def test_empty(self):
        self.assertIsNone(control_report([])["teams"]["against"]["control_video_seconds"])
    def test_unknown_overlap_not_promoted(self):
        x=control_report([r(0,2),r(1,2,"unknown")])
        self.assertEqual(x["teams"]["for"]["control_video_seconds"],1)
        self.assertEqual(x["teams"]["unknown"]["control_video_seconds"],1)
