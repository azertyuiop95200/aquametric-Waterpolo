import unittest
from services.elite_performance import exposure, reduce_side
from services.statistical_audit import audit_rows
from services.advanced_observed_metrics import advanced_report, complete_possessions, pass_network, tsap, observed_numeric

def e(i,typ,note="",pid=1,side="for",confidence="CONFIRMED"):
    return dict(id=i,match_id=1,event_type=typ,note=note,player_id=pid,perspective=side,confidence=confidence,second=i,player="A",phase="even_attack")

class AuditTests(unittest.TestCase):
    def test_empty_and_roster(self):
        r=audit_rows([],roster=[{"id":1,"name":"A"}])
        self.assertTrue(all(x["value"] is None for x in r["team"]))
        self.assertEqual(len(r["players"]),1)
    def test_period_and_neutral(self):
        r=audit_rows([e(1,"goal"),e(2,"goal",side="neutral"),e(3,"goal",confidence="CANDIDATE")])
        self.assertEqual(r["confirmed_count"],2);self.assertEqual(r["excluded_count"],1)
        self.assertEqual(next(x["value"] for x in r["team"] if x["key"]=="goals"),1)
        self.assertIn("missing_period",[x["code"] for x in r["issues"]])
    def test_denominator(self):
        r=audit_rows([e(1,"goal"),e(2,"shot_off_target")])
        m=next(x for x in r["team"] if x["key"]=="shot_conversion")
        self.assertEqual((m["value"],m["denominator"]),(50,2))
    def test_unknown_shot(self):
        r=audit_rows([e(1,"goal"),e(2,"shot_unknown")])
        self.assertIsNone(next(x["value"] for x in r["team"] if x["key"]=="shot_conversion"))
    def test_team_exposure(self):
        rows=[e(1,"player_in","period=1 game_clock_s=480",1),e(2,"player_in","period=1 game_clock_s=470",2),
              e(3,"player_out","period=1 game_clock_s=400",1),e(4,"player_out","period=1 game_clock_s=420",2)]
        self.assertEqual(exposure(rows)["playing_seconds"],130)
        self.assertEqual(exposure(rows)["playing_intervals"],2)
    def test_unpaired_unknown_identity(self):
        r=exposure([e(1,"player_in","period=1 game_clock_s=480",None),e(2,"player_out","period=1 game_clock_s=400",None)])
        self.assertIsNone(r["playing_seconds"]);self.assertEqual(r["unpaired_markers"],2)
    def test_possession_rebound_not_terminal(self):
        r=[e(1,"possession_start","period=1 game_clock_s=440 possession=p"),
           e(2,"shot_on_target","period=1 game_clock_s=435 possession=p"),
           e(3,"pass_complete","period=1 game_clock_s=430 possession=p"),
           e(4,"goal","period=1 game_clock_s=420 possession=p"),
           e(5,"possession_end","period=1 game_clock_s=420 possession=p outcome=goal passes_complete=yes")]
        out=advanced_report(r,[])["sides"]["for"]
        self.assertEqual(len(out["possessions"]),1)
        self.assertEqual(out["goals_per_possession"]["value"],1)
        self.assertEqual(out["possession_duration"]["value"],20)
        self.assertEqual(out["passes_per_possession"]["value"],1)
    def test_possession_missing_end(self):
        r=[e(1,"possession_start","period=1 game_clock_s=440 possession=p"),e(2,"goal","period=1 game_clock_s=430 possession=p")]
        self.assertEqual(complete_possessions(r),([],1))
    def test_network_identity_and_action_dedup(self):
        r=[e(1,"pass_complete","receiver_id=2 action_id=a"),e(2,"assist","receiver_id=2 action_id=a"),
           e(3,"pass_complete","receiver_id=3 action_id=b"),e(4,"pass_complete","receiver_id=2")]
        n=pass_network(r,{1,2})
        self.assertEqual(n["edges"][0]["count"],1)
        self.assertEqual(n["rejected_or_unlinked"],2)
    def test_tsap(self):
        r=[e(1,"touch","tsap=rb action_id=a tsap_coverage=complete"),e(2,"touch","tsap=ob action_id=b")]
        t=tsap(r);self.assertEqual(t["volume_play"],1);self.assertEqual(t["efficiency_index"],.1);self.assertEqual(t["performance_score"],1.5)
        self.assertIsNone(tsap([e(1,"touch","tsap=rb action_id=a")])["performance_score"])
    def test_calibration(self):
        r=[e(1,"goal","shot_speed_kmh=70"),e(2,"goal","shot_speed_kmh=80 measurement=calibrated"),
           e(3,"goal","shot_speed_kmh=nan measurement=calibrated")]
        x=observed_numeric(r)["shot_speed_kmh"]["mean"];self.assertEqual((x["value"],x["n"]),(80,1))

class MotionTests(unittest.TestCase):
    def track(self,offset=0):
        return {"segments":[[{"second":0,"x_m":1+offset,"y_m":1},{"second":.2,"x_m":1.4+offset,"y_m":1}]]}
    def test_motion_overlap(self):
        from services.tracking_performance import motion_summary
        m=motion_summary([self.track(),self.track()])
        self.assertAlmostEqual(m["distance_m"],.4)
        self.assertAlmostEqual(m["observed_seconds"],.2)
        self.assertAlmostEqual(m["average_speed_mps"],2)
        self.assertAlmostEqual(sum(x["seconds"] for x in m["occupancy"]),.2)
    def test_conflict(self):
        from services.tracking_performance import motion_summary
        m=motion_summary([self.track(),self.track(2)])
        self.assertIsNone(m["distance_m"]);self.assertAlmostEqual(m["conflict_seconds"],.2)
    def test_gap(self):
        from services.tracking_performance import motion_summary
        t=self.track();t["segments"][0][1]["second"]=1
        self.assertIsNone(motion_summary([t])["average_speed_mps"])

if __name__=="__main__":unittest.main()
