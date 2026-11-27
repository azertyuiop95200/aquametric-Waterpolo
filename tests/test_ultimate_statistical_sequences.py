import unittest
from services.tactical_sequence_metrics import sequence_report

def ev(i,t,c,uid="",extra="",side="for"):
    return dict(id=i,match_id=1,event_type=t,note=f"period=1 game_clock_s={c} "+(f"sequence={uid} " if uid else "")+extra,perspective=side,confidence="CONFIRMED",second=i)

class SequenceTests(unittest.TestCase):
    def test_numeric(self):
        rows=[ev(1,"power_play_start",400,"a"),ev(2,"power_play_end",387,"a","outcome=goal"),
              ev(3,"penalty_kill_start",300,"b"),ev(4,"penalty_kill_end",282,"b","outcome=no_goal")]
        d=sequence_report(rows)["sides"]["for"];m={r["kind"]:r for r in d["metrics"]}
        self.assertEqual(m["power_play"]["mean_seconds"],13)
        self.assertEqual(m["penalty_kill"]["success_pct"],100)
    def test_incomplete(self):
        d=sequence_report([ev(1,"counterattack_start",400,"a")])["sides"]["for"]
        self.assertEqual(len(d["rejected"]),1)
        self.assertEqual(d["sequences"],[])
    def test_overlap(self):
        rows=[ev(1,"power_play_start",400,"a"),ev(2,"power_play_end",380,"a"),
              ev(3,"power_play_start",390,"b"),ev(4,"power_play_end",370,"b")]
        d=sequence_report(rows)["sides"]["for"]
        self.assertEqual(len(d["rejected"]),2)
    def test_timeout_clock(self):
        rows=[ev(1,"timeout_start",300,"a"),ev(2,"timeout_end",300,"a")]
        d=sequence_report(rows)["sides"]["for"]
        self.assertIsNone(d["sequences"][0]["seconds"])
        self.assertIsNone(d["timeouts"][0]["delta_pp"])
    def test_timeout_context(self):
        rows=[ev(1,"timeout_start",300,"t"),ev(2,"timeout_end",300,"t")]
        for i,(a,b,o) in enumerate([(350,340,"save"),(330,320,"save"),(290,280,"goal"),(270,260,"goal")]):
            rows.extend([ev(10+2*i,"possession_start",a,extra=f"possession=p{i}"),
                         ev(11+2*i,"possession_end",b,extra=f"possession=p{i} outcome={o}")])
        r=sequence_report(rows)["sides"]["for"]["timeouts"][0]
        self.assertEqual(r["delta_pp"],100)
        self.assertEqual(r["before"]["n"],2)

if __name__=="__main__":unittest.main()
