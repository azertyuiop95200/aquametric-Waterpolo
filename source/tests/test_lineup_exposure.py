import unittest
from services.lineup_exposure import lineup_report, normalize_lineups

def r(a=60,b=40,side="for",caps=None,excluded=None,p=1,**kw):
    return dict(period=p,side=side,clock_start=a,clock_end=b,start_second=0,end_second=30,confidence=.9,complete_lineup=True,in_play=caps if caps is not None else list(range(1,8)),excluded=excluded or [],clock_evidence="chrono général lisible",lineup_evidence="composition visible en continu",team_evidence="équipe visible")|kw

class LineupTests(unittest.TestCase):
    def test_clock_not_video(self):
        t=lineup_report([r()])["teams"]["for"]
        self.assertEqual(t["observed_game_seconds"],20)
        self.assertEqual(t["player_seconds"],140)
        self.assertEqual(t["players"][0]["playing_seconds"],20)
    def test_overlap(self):
        t=lineup_report([r(),r(50,30)])["teams"]["for"]
        self.assertEqual(t["observed_game_seconds"],30)
    def test_conflict(self):
        t=lineup_report([r(),r(50,30,caps=[1,2,3,4,5,6,8])])["teams"]["for"]
        self.assertEqual(t["observed_game_seconds"],20)
        self.assertEqual(t["conflict_game_seconds"],10)
    def test_exclusion_early_return(self):
        t=lineup_report([r(60,55,caps=[1,2,3,4,5,6],excluded=[7]),r(55,40)])["teams"]["for"]
        x=t["players"][-1]
        self.assertEqual((x["playing_seconds"],x["excluded_seconds"]),(15,5))
    def test_no_inferred_bench_or_exclusion(self):
        t=lineup_report([r(caps=[1,2,3,4,5,6])])["teams"]["for"]
        self.assertEqual(len(t["players"]),6)
        self.assertIsNone(t["players"][0]["excluded_seconds"])
    def test_numerical_intersection(self):
        x=lineup_report([r(),r(50,30,side="against",caps=[1,2,3,4,5,6])])
        self.assertEqual(x["numerical_states"],[{"for_players":7,"against_players":6,"seconds":10}])
    def test_four_periods(self):
        t=lineup_report([r(p=p) for p in range(1,5)])["teams"]["for"]
        self.assertEqual(t["players"][0]["playing_seconds"],80)
    def test_invalid_and_replay(self):
        x=lineup_report([r(40,60),r(is_replay=True),r(100,10),r(complete_lineup=False),r(caps=[1,1]),r(excluded=[1]),r(clock_evidence="")])
        self.assertEqual(x["rejected_intervals"],7)
        self.assertIsNone(x["teams"]["for"]["observed_game_seconds"])
    def test_short_profile(self):
        self.assertEqual(lineup_report([r(400,380)],max_period_seconds=360)["rejected_intervals"],1)
    def test_gap_not_filled(self):
        t=lineup_report([r(60,55),r(45,40)])["teams"]["for"]
        self.assertEqual(t["observed_game_seconds"],10)
    def test_core_boundary_no_clock_interpolation(self):
        s=dict(clip_start=10,clip_end=50,start=15,end=30,index=1)
        x=normalize_lineups([r()],s,"water_polo")[0]
        self.assertEqual((x["start_second"],x["end_second"],x["clock_start"],x["clock_end"]),(10,40,60,40))
    def test_incomplete_exclusion_evidence(self):
        t=lineup_report([r(caps=[1,2,3,4,5,6],excluded=[7]),r(caps=[1,2,3,4,5,6])])["teams"]["for"]
        self.assertEqual(len(t["players"]),6)
