import unittest
from services.report_coverage import metric_table,report_coverage
class CoverageTests(unittest.TestCase):
    def test_no_sporting_zero_without_evidence(self):
        r=metric_table([{"event_type":"goal"}])
        self.assertEqual(r["metrics"]["goals"],1)
        self.assertIsNone(r["metrics"]["duels_won"])
        self.assertIsNone(r["metrics"]["pass_accuracy"])
    def test_candidate_and_verified_separate(self):
        c=[{"event_type":"goal","perspective":"for","confidence":"CONFIRMED"}]
        a={"duration_seconds":10,"coverage_percent":50,"events":[{"event_type":"shot_off_target","side":"for","cap_number":8,"counted":True},{"event_type":"goal","side":"for","cap_number":8,"counted":True,"conflict":True}]}
        r=report_coverage(c,a,[])
        self.assertEqual(r["teams"]["for"]["confirmed"]["metrics"]["goals"],1)
        self.assertIsNone(r["teams"]["for"]["candidate"]["metrics"]["goals"])
        self.assertEqual(r["candidate_players"][0]["metrics"]["shot_conversion"],0)
        self.assertEqual(r["video_coverage_percent"],50)
    def test_empty(self):
        r=report_coverage([],{},[])
        self.assertIsNone(r["video_coverage_percent"])
        self.assertIsNone(r["teams"]["against"]["confirmed"]["metrics"]["shots"])
