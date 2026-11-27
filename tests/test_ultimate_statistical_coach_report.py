"""Synthetic integration checks for real advanced report producers and coach template."""
import unittest
from pathlib import Path
from types import SimpleNamespace
import re
from jinja2 import Environment, FileSystemLoader, select_autoescape
from services.statistical_audit import audit_rows
from services.advanced_observed_metrics import advanced_report
from services.lineup_performance import lineup_report, phase_context_report
from services.tactical_sequence_metrics import sequence_report
from services.tracking_performance import motion_report

ROOT=Path(__file__).resolve().parents[1]
ENV=Environment(loader=FileSystemLoader(str(ROOT / "source/templates")),autoescape=select_autoescape(["html"]))

def event(i,typ,note="",confidence="CONFIRMED"):
    return dict(id=i,match_id=1,event_type=typ,note=note,player_id=1,
                perspective="for",confidence=confidence,second=i,player="Joueuse test",phase="even_attack")

def render(rows):
    roster=[{"id":1,"name":"Joueuse test"}]
    audit=audit_rows(rows,roster)
    basic={r["key"]:r["value"] for r in audit["team"]}
    other={r["key"]:r["value"] for r in audit["opponent"]}
    snapshot=dict(statistics=dict(labels={"goals":"Buts","events":"Actions confirmées"},
                    note="Échantillon confirmé uniquement.",excluded_unverified_events=audit["excluded_count"],
                    team={"basic":basic},opponent={"basic":other},players=[]),
                  reference=None,tactical=None,statistical_audit=audit,
                  advanced_observed=advanced_report(rows,roster),
                  lineup_performance=lineup_report(rows,roster),phase_context=phase_context_report(rows),
                  tactical_sequences=sequence_report(rows),motion_performance=motion_report({},{}))
    match=SimpleNamespace(team=SimpleNamespace(name="Blanc"),opponent="Bleu")
    return ENV.get_template("analysis_all_measurements.html").render(snapshot=snapshot,match=match),snapshot

class CoachReportIntegration(unittest.TestCase):
    def test_empty_advanced_producers(self):
        html,s=render([])
        self.assertIn("Non mesuré",html)
        self.assertIn("Registre scientifique individuel",html)
        self.assertIn("Aucune piste attribuée",html)
        self.assertIn("Joueuse test",html)
        self.assertTrue(all(x["value"] is None for x in s["statistical_audit"]["team"]))
        ids=re.findall(r'id="(coach-[^"]+)"',html)
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),set(re.findall(r'href="#(coach-[^"]+)"',html)))

    def test_confirmed_possession_and_candidate_exclusion(self):
        rows=[event(1,"possession_start","period=1 game_clock_s=440 possession=p"),
              event(2,"pass_complete","period=1 game_clock_s=430 possession=p action_id=a"),
              event(3,"goal","period=1 game_clock_s=420 possession=p"),
              event(4,"possession_end","period=1 game_clock_s=420 possession=p outcome=goal passes_complete=yes"),
              event(5,"goal",confidence="CANDIDATE")]
        html,s=render(rows)
        self.assertEqual(s["advanced_observed"]["sides"]["for"]["possession_duration"]["value"],20)
        self.assertEqual(s["statistical_audit"]["excluded_count"],1)
        self.assertEqual(next(r["value"] for r in s["statistical_audit"]["team"] if r["key"]=="goals"),1)
        self.assertIn("possession duration",html)
        self.assertIn("20",html)
        self.assertNotIn("performance_score",html)

if __name__=="__main__":unittest.main()
