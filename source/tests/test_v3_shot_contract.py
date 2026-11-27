"""The same shot vocabulary must be used by tactical and statistical reports."""
from types import SimpleNamespace as NS
from services.tactical_engine import analyze_match_tactics
from services.reporting import build_match_report
from services.ultimate_analytics import SHOT_EVENTS

def ev(kind, second, side="for"):
    return NS(event_type=kind,second=second,confidence="CONFIRMED",note="",context_meta=NS(perspective=side,phase_tag="even_attack"))

def test_defensive_block_is_not_an_attacking_attempt():
    match=NS(events=[ev("goal",1),ev("shot_blocked",2),ev("block",3)])
    r=build_match_report(match)
    assert next(x["value"] for x in r["headline"] if x["label"]=="Team shots")==2
    assert next(x["value"] for x in r["tactical"]["headline"] if x["label"]=="Tagged shot conversion")=="50.0%"
    seq=r["tactical"]["sequences"][0]
    assert seq["shots_for"]==2
    assert seq["blocks_for"]==1
    assert "block" not in SHOT_EVENTS

def test_unresolved_shot_counts_but_does_not_certify_conversion():
    match=NS(events=[ev("goal",1),ev("shot_unknown",2),ev("shot_unknown",3,"against")])
    r=build_match_report(match,NS(summary_json="[]",ocr_available=False))
    assert next(x["value"] for x in r["headline"] if x["label"]=="Team shots")==2
    seq=r["tactical"]["sequences"][0]
    assert seq["shots_unknown_for"]==1 and seq["shots_unknown_against"]==1
    assert not any("conversion" in x["label"] for x in r["tactical"]["headline"])
    assert r["auto_summary"]=={}
