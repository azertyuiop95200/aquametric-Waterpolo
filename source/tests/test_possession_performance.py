import unittest
from services.possession_performance import complete_possessions
from services.lineup_exposure import lineup_report
def event(kind,t,clock,**kw):
    return dict(event_type=kind,second=t,game_clock_seconds=clock,game_clock_evidence="clock",side="for",team_evidence="team",period=1,segment_index=0,counted=True)|kw
def segment(visible=True):
    return {"index":0,"status":"complete","result":{"scene":"water_polo","observability":[{"family":"possessions","status":"visible" if visible else "limited"}]}}
def lineup(side,n):
    return dict(period=1,side=side,clock_start=60,clock_end=0,start_second=0,end_second=65,confidence=.9,complete_lineup=True,in_play=list(range(1,n+1)),excluded=[],clock_evidence="clock",lineup_evidence="lineup",team_evidence="team")
def sample():
    return [event("possession_start",0,60),event("pass_complete",2,58),event("shot_on_target",5,55),event("pass_complete",7,53),event("goal",9,51),event("possession_end",10,50,possession_outcome="goal")]
class PossessionTests(unittest.TestCase):
    def report(self,rows,visible=True,ls=None):
        return complete_possessions(rows,[segment(visible)],lineup_report(ls or []))
    def test_rebound_not_new_possession(self):
        r=self.report(sample())["teams"]["for"]["overall"]
        self.assertEqual((r["possessions"],r["goal_pct"],r["detected_shots_per_possession"],r["detected_passes_per_possession"]),(1,100,2,2))
    def test_advantage(self):
        r=self.report(sample(),ls=[lineup("for",7),lineup("against",6)])
        self.assertEqual(r["teams"]["for"]["numerical"]["advantage"]["possessions"],1)
    def test_limited_visibility(self):
        self.assertIsNone(self.report(sample(),False)["teams"]["for"]["overall"]["possessions"])
    def test_missing_end(self):
        self.assertIsNone(self.report(sample()[:-1])["teams"]["for"]["overall"]["possessions"])
    def test_goal_conflict(self):
        rr=sample();rr[-1]["possession_outcome"]="save"
        self.assertEqual(self.report(rr)["rejected"]["goal_outcome_conflict"],1)
    def test_opponent_action(self):
        rr=sample();rr[1]["side"]="against"
        self.assertEqual(self.report(rr)["rejected"]["opposing_or_unknown_actions"],1)
    def test_unknown_outcome(self):
        rr=[event("possession_start",0,60),event("possession_end",5,55)]
        self.assertIsNone(self.report(rr)["teams"]["for"]["overall"]["goal_pct"])
    def test_no_numerical_guess(self):
        r=self.report(sample(),ls=[lineup("for",7)])
        self.assertEqual(r["teams"]["for"]["numerical"]["unresolved_or_changing"]["possessions"],1)

    def test_adjacent_cores(self):
        ss=[dict(segment(),start=0,end=6),dict(segment(),index=1,start=6,end=12)]
        rr=[dict(e,segment_index=int(e["second"]>=6)) for e in sample()]
        self.assertEqual(complete_possessions(rr,ss,lineup_report([]))["teams"]["for"]["overall"]["possessions"],1)
    def test_gap_breaks_chain(self):
        ss=[dict(segment(),start=0,end=6),dict(segment(),index=1,start=7,end=12)]
        rr=[dict(e,segment_index=int(e["second"]>=7)) for e in sample()]
        self.assertIsNone(complete_possessions(rr,ss,lineup_report([]))["teams"]["for"]["overall"]["possessions"])
    def test_replay_barrier(self):
        rr=sample()+[event("pass_complete",4,56,is_replay=True)]
        self.assertIsNone(self.report(rr)["teams"]["for"]["overall"]["possessions"])
    def test_period_change_breaks_chain(self):
        rr=sample()+[event("touch",4,56,period=2)]
        self.assertIsNone(self.report(rr)["teams"]["for"]["overall"]["possessions"])
