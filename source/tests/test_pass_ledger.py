import unittest
from services.pass_ledger import pass_ledger
from services.elite_performance import reduce_side
from services.video_action_schema import ActionObservation
class PassTests(unittest.TestCase):
    def test_unknown_not_failure_and_receive_not_double(self):
        rows=[{"side":"for","event_type":"assist","cap_number":2,"identity_evidence":"visible","receiver_cap_number":8,"receiver_evidence":"visible"},
              {"side":"for","event_type":"pass_unknown","cap_number":2,"identity_evidence":"visible"},
              {"side":"for","event_type":"bad_pass","cap_number":3,"identity_evidence":"visible"},
              {"side":"for","event_type":"goalkeeper_restart"}]
        r=pass_ledger(rows)["teams"]["for"]
        self.assertEqual((r["attempts"],r["completed"],r["failed"],r["unknown"]),(3,1,1,1))
        self.assertEqual(r["received"],{8:1})
        self.assertIsNone(r["completion_pct"])
        s=reduce_side(rows)
        self.assertEqual(s["pass_attempts"],3)
        self.assertIsNone(s["pass_accuracy"])
    def test_side_separation_and_unobserved(self):
        r=pass_ledger([{"side":"against","event_type":"pass_complete","cap_number":2}])["teams"]
        self.assertIsNone(r["for"]["attempts"])
        self.assertEqual(r["against"]["attempts"],1)
        self.assertEqual(r["against"]["unattributed_passers"],1)
    def test_replay_conflict_excluded(self):
        rows=[{"side":"for","event_type":"pass_complete","is_replay":True},{"side":"for","event_type":"pass_complete","conflict":"incompatible"}]
        self.assertIsNone(pass_ledger(rows)["teams"]["for"]["attempts"])
    def test_receiver_needs_evidence(self):
        d=dict(second=2,event_type="pass_complete",side="for",confidence=.9,evidence="Transmission visible",team_evidence="club visible",cap_number=2,identity_evidence="bonnet visible",receiver_cap_number=8)
        self.assertIsNone(ActionObservation(**d).receiver_cap_number)
        self.assertEqual(ActionObservation(**dict(d,receiver_evidence="bonnet partenaire visible")).receiver_cap_number,8)
        self.assertIsNone(ActionObservation(**dict(d,receiver_cap_number=2,receiver_evidence="visible")).receiver_cap_number)
