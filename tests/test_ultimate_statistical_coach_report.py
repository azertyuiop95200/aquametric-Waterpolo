"""Synthetic integration checks for real advanced report producers and coach template."""
import unittest
from pathlib import Path
from types import SimpleNamespace
import re
import os
import json
from services.possession_evidence import report as possession_report, build_note
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
                  tactical_sequences=sequence_report(rows),motion_performance=motion_report({},{}),
                  possession_evidence=possession_report(rows))
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

    def test_partial_review_does_not_create_complete_possession(self):
        note=build_note(1,2,"for","against","observed","observed","unknown",
                        False,False,False,False,"Contrôles visibles (fixture)",1,5)
        row=event(2,"possession_transition",note)
        row.update(perspective="neutral",player_id=None,player=None)
        html,s=render([row])
        p=s["possession_evidence"]
        self.assertEqual(p["bounds"][0]["lower_bound"],1)
        self.assertIsNone(p["exact_total_changes"])
        self.assertIsNone(p["turnover_rate"])
        self.assertEqual(s["advanced_observed"]["sides"]["for"]["possessions"],[])
        self.assertIn("Contrôles opposés",html)
        self.assertIn("au moins 1 changement",html)
        self.assertIn("Non établie",html)
        self.assertEqual(html.count('id="possessionEvidence"'),1)
        out=os.getenv("AQUAMETRIC_V3_FIXTURE_DIR")
        if out:
            folder=Path(out)
            folder.mkdir(parents=True,exist_ok=True)
            (folder/"v3-synthetic.html").write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Rapport V3 synthétique</title><h1>Test synthétique — aucun match réel</h1>'+html+'</html>',encoding="utf-8")
            (folder/"v3-synthetic.json").write_text(json.dumps({"fixture":True,"snapshot":s},ensure_ascii=False,indent=2,default=str),encoding="utf-8")

    def test_reference_remains_distinct_in_coach_report(self):
        from test_review_reference_import import fixture, read
        from services.review_reference_import import summarize
        p, canonical, digest, period=read(fixture())
        _,s=render([])
        s["review_references"]=[dict(period=period,digest=digest,revision_count=0,report=summarize(p,"bleus"))]
        match=SimpleNamespace(team=SimpleNamespace(name="Blanc"),opponent="Bleu")
        html=ENV.get_template("analysis_all_measurements.html").render(snapshot=s,match=match)
        self.assertIn("distinctes des statistiques confirmées",html)
        self.assertEqual(html.count('id="reviewReferences"'),1)
        self.assertEqual(s["review_references"][0]["report"]["verified_match_event_count"],0)
        self.assertEqual(len(s["review_references"][0]["report"]["events"]),1)
        self.assertTrue(all(x["value"] is None for x in s["statistical_audit"]["team"]))
        self.assertEqual(s["possession_evidence"]["rows"],[])
        self.assertIn("&lt;script&gt;",html)
        self.assertNotIn("<script>",html)

    def test_motion_release_and_coach_report_share_snapshot(self):
        from services.advanced_motion_report import build
        _,s=render([])
        track={"id":1,"segments":[[{"second":0,"x_m":1,"y_m":-2},
            {"second":.2,"x_m":1.4,"y_m":-2},{"second":.4,"x_m":1.8,"y_m":-2}]]}
        s["automatic"]={"summary":{"metric_field_map":{"status":"estimated","goal_relative":True,
            "revision":"r","length_m":25,"width_m":20,"tracks":[track]},
            "identity_reviews":{"tracks":{"1":{"provenance":"coach_review",
                "side":"for","cap_number":4,"evidence":"synthetic review"}}}}}
        s["identity_analysis"]={"analysis_id":3,"calibration_revision":"r",
            "players":[{"side":"for","cap_number":4,"track_ids":[1]}]}
        s["advanced_motion"]=build(s)
        motion=s["advanced_motion"]
        self.assertEqual(motion["status"],"experimental_partial")
        self.assertAlmostEqual(motion["players"][0]["metrics"]["distance_m"],.8)
        self.assertIsNone(motion["playing_seconds"])
        self.assertTrue(all(x["value"] is None for x in s["statistical_audit"]["team"]))
        match=SimpleNamespace(team=SimpleNamespace(name="Blanc"),opponent="Bleu")
        html=ENV.get_template("analysis_all_measurements.html").render(snapshot=s,match=match)
        self.assertEqual(html.count('id="advancedMotion"'),1)
        self.assertIn("Distance observée",html)
        self.assertIn("0.80 m",html)
        self.assertIn("Trajectoire métrique",html)
        self.assertIn("Le temps vidéo observé n'est pas le temps de jeu",html)
        self.assertIn('id="possessionEvidence"',html)
        s["identity_analysis"]["calibration_revision"]="stale"
        s["advanced_motion"]=build(s)
        self.assertEqual(s["advanced_motion"]["status"],"unavailable")
        html=ENV.get_template("analysis_all_measurements.html").render(snapshot=s,match=match)
        self.assertNotIn("0.80 m",html)
        self.assertIn("Non mesuré : calibration exploitable et identité revue nécessaires.",html)

    def test_motion_visible_without_statistics_snapshot(self):
        from services.advanced_motion_report import build
        match=SimpleNamespace(team=SimpleNamespace(name="Blanc"),opponent="Bleu")
        html=ENV.get_template("analysis_all_measurements.html").render(
            snapshot={"advanced_motion":build({})},match=match)
        self.assertEqual(html.count('id="advancedMotion"'),1)
        self.assertIn("Non mesuré",html)

if __name__=="__main__":unittest.main()
