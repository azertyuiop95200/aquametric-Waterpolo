"""Synthetic evidence regression; not an analysis of a real match."""
import json
import os
from pathlib import Path
from types import SimpleNamespace as NS

from jinja2 import Environment, FileSystemLoader, select_autoescape

from services.reporting import build_match_report


def event(second, kind, side="for", confidence="CONFIRMED", phase="auto"):
    return NS(second=second, event_type=kind, confidence=confidence,
              context_meta=NS(perspective=side, phase_tag=phase))


def match(events):
    return NS(id=1, team=NS(name="Équipe fictive A"), opponent="Équipe fictive B",
              events=events)


def test_report_shot_denominator_and_missing_opponent():
    sample = match([
        event(0, "power_play_start"),
        event(2, "block"),
        event(4, "shot_blocked"),
        event(7, "goal"),
        event(9, "goal", side="against", confidence="CANDIDATE"),
    ])
    report = build_match_report(sample)
    assert report["data_quality"]["verified_events"] == 4
    assert report["data_quality"]["verified_against"] == 0
    assert report["headline"][0]["value"] == "1–—"
    assert report["headline"][1]["value"] == 2
    assert "1–—" in report["executive_summary"]
    conversion = next(row for row in report["tactical"]["headline"]
                      if row["label"] == "Tagged shot conversion")
    assert conversion["value"] == "50.0%"
    phase = report["tactical"]["sequences"][0]
    assert phase["shots_for"] == 2
    assert phase["blocks_for"] == 1
    assert phase["time_to_first_shot"] == 4
    # Export an actual rendered report using the production generator and template.
    env = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parents[1] / "templates")),
                      autoescape=select_autoescape(["html"]))
    html = env.get_template("report.html").render(
        match=sample, report=report, app_name="AquaMetric — DONNÉES SYNTHÉTIQUES",
        request=NS(url=NS(path="/matches/1/report")),
        user=NS(name="Fixture synthétique", email="test@example.invalid"),
        web_demo_mode=False,
    )
    assert "1–—" in html
    assert "50.0%" not in html or "Tagged shot conversion" in html
    assert "quality-meter" not in html
    assert "/100 score" not in html
    assert "couverture du match entier" in html
    target = os.environ.get("AQUAMETRIC_REPORT_FIXTURE_DIR")
    if target:
        path = Path(target)
        path.mkdir(parents=True, exist_ok=True)
        (path / "report-synthetic.html").write_text(html, encoding="utf-8")
        payload = {key: report[key] for key in ("headline", "data_quality", "tactical", "executive_summary")}
        (path / "report-synthetic.json").write_text(json.dumps(
            {"fixture": True, "source": "synthetic events; not a real match", **payload},
            ensure_ascii=False, indent=2), encoding="utf-8")


def test_report_empty_and_untrusted_candidate_are_not_measured():
    report = build_match_report(match([event(1, "goal", confidence="CANDIDATE")]),
                                NS(summary_json="[]", ocr_available=False))
    assert report["headline"][0]["value"] == "—–—"
    assert all(row["value"] is None for row in report["headline"][1:])
    assert report["data_quality"]["verified_events"] == 0
    assert report["auto_summary"] == {}
