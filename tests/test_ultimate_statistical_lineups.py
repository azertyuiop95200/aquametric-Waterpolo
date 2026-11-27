import unittest
from services.lineup_performance import lineup_report, phase_context_report

def event(i,typ,c,pid=None,side="for",extra="",phase="even_attack"):
    return dict(id=i,match_id=1,event_type=typ,note=f"period=1 game_clock_s={c} {extra}",
                player_id=pid,perspective=side,confidence="CONFIRMED",second=i,phase=phase)

def fixture():
    roster=[dict(id=i,name=f"J{i}") for i in range(1,9)]
    rows=[]
    for i in range(1,8):
        rows.extend([event(10*i,"player_in",480,i),event(10*i+1,"player_out",240 if i==7 else 0,i)])
    rows.extend([event(80,"player_in",240,8),event(81,"player_out",0,8),
                 event(90,"goal",350,1),event(91,"goal",300,2),
                 event(92,"goal",200,None,"against"),event(93,"goal",100,8),
                 event(94,"period_end",0,extra="lineups_complete=yes goals_complete=yes"),
                 event(95,"period_end",0,side="against",extra="goals_complete=yes")])
    return rows,roster

class LineupTests(unittest.TestCase):
    def test_exact_lineups(self):
        rows,roster=fixture();r=lineup_report(rows,roster)
        self.assertTrue(r["quarters"][0]["valid"])
        self.assertEqual(len(r["lineups"]),2)
        self.assertEqual(sum(x["seconds"] for x in r["lineups"]),480)
        p={x["player_id"]:x for x in r["players"]}
        self.assertEqual(p[1]["playing_seconds"],480)
        self.assertEqual(p[7]["playing_seconds"],240)
        self.assertEqual(p[7]["plus_minus"],2)
        self.assertEqual(p[7]["plus_minus_per_8min"],4)
        self.assertEqual(p[8]["plus_minus"],0)
        self.assertEqual(p[1]["plus_minus"],2)
    def test_no_coverage(self):
        rows,roster=fixture();r=lineup_report(rows[:-1],roster)
        self.assertFalse(r["quarters"][0]["valid"])
        self.assertIsNone(r["players"][0]["plus_minus"])
        self.assertEqual(r["players"][0]["playing_seconds"],480)
    def test_boundary_goal(self):
        rows,roster=fixture();rows.append(event(96,"goal",240,1))
        r=lineup_report(rows,roster);self.assertEqual(r["quarters"][0]["unassigned_boundary_goals"],1)
        self.assertIsNone(r["players"][0]["plus_minus"])
    def test_duplicate_goal(self):
        rows,roster=fixture();rows.append(event(96,"goal",350,1))
        self.assertFalse(lineup_report(rows,roster)["quarters"][0]["valid"])
    def test_invalid_presence(self):
        rows,roster=fixture();rows.append(event(96,"player_in",400,1))
        r=lineup_report(rows,roster);self.assertFalse(r["quarters"][0]["valid"])
        self.assertIsNone(r["players"][0]["playing_seconds"])
    def test_eight_in_water(self):
        rows,roster=fixture();rows[14]["note"]="period=1 game_clock_s=480"
        self.assertFalse(lineup_report(rows,roster)["quarters"][0]["valid"])
    def test_counterattack(self):
        rows=[event(1,"possession_start",400,phase="counterattack",extra="possession=p"),
              event(2,"goal",395,1,extra="possession=p"),
              event(3,"possession_end",395,extra="possession=p outcome=goal")]
        r=phase_context_report(rows)["sides"]["for"]["phases"]
        x=next(x for x in r if x["phase"]=="counterattack")
        self.assertEqual(x["conversion_pct"],100)
        self.assertEqual(x["mean_seconds"],5)

if __name__=="__main__":unittest.main()
