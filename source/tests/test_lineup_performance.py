import unittest
from services.lineup_performance import analyze_performance
from services.lineup_exposure import lineup_report
def r(side="for",a=60,b=0,caps=None,p=1):
    return dict(period=p,side=side,clock_start=a,clock_end=b,start_second=0,end_second=65,confidence=.9,complete_lineup=True,in_play=caps if caps is not None else list(range(1,8)),excluded=[],clock_evidence="clock",lineup_evidence="lineup",team_evidence="team")
def e(kind="goal",key="a",side="for",n=1,t=30,**kw):
    return dict(event_type=kind,key=key,side=side,cap_number=n,period=1,game_clock_seconds=t,game_clock_evidence="clock",team_evidence="team",identity_evidence="cap",counted=True)|kw
class PerformanceTests(unittest.TestCase):
    def run_report(self,events,rows=None):
        return analyze_performance(events,lineup_report(rows if rows is not None else [r(),r("against")]))
    def test_goal_difference_and_rate(self):
        x=self.run_report([e()]);a,b=x["teams"]["for"]["players"],x["teams"]["against"]["players"]
        self.assertEqual(a[0]["goals_per_min"],1);self.assertEqual(a[1]["observed_goal_diff"],1);self.assertEqual(b[0]["observed_goal_diff"],-1)
    def test_no_other_lineup(self):
        x=self.run_report([e()],[r()]);self.assertIsNone(x["teams"]["for"]["players"][0]["observed_goal_diff"])
    def test_clock_boundary(self):
        x=self.run_report([e(t=60)]);self.assertEqual(x["excluded"]["lineup_gap_or_boundary"],1)
    def test_bad_actor(self):
        x=self.run_report([e(n=9)]);self.assertEqual(x["excluded"]["actor_lineup_conflict"],1)
    def test_missing_clock_evidence(self):
        x=self.run_report([e(game_clock_evidence="")]);self.assertEqual(x["excluded"]["clock_or_team_missing"],1)
    def test_duplicate_and_replay(self):
        x=self.run_report([e(),e(),e(key="b",is_replay=True)]);self.assertEqual(x["teams"]["for"]["players"][0]["goals"],1)
    def test_pass_reception(self):
        x=self.run_report([e("assist",receiver_cap_number=2,receiver_evidence="cap")]);p=x["teams"]["for"]["players"]
        self.assertEqual(p[0]["passes_attempted"],1);self.assertEqual(p[1]["passes_received"],1);self.assertEqual(p[0]["assists"],1)
    def test_numerical(self):
        x=self.run_report([e()],[r(),r("against",caps=[1,2,3,4,5,6])]);n=x["teams"]["for"]["numerical"][0]
        self.assertEqual((n["players"],n["opponents"],n["seconds"],n["goals"]),(7,6,60,1))
    def test_gap_and_period(self):
        x=self.run_report([e(t=30),e(key="b",period=2)],[r(a=60,b=40),r(a=20,b=0)]);self.assertEqual(x["excluded"]["lineup_gap_or_boundary"],2)
    def test_no_events(self):
        x=self.run_report([]);p=x["teams"]["for"]["players"][0];self.assertIsNone(p["goals_per_min"]);self.assertIsNone(p["observed_goal_diff"])
