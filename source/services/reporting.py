from __future__ import annotations
from collections import Counter
from services.tactical_engine import analyze_match_tactics


def _perspective(event):
    return getattr(getattr(event, 'context_meta', None), 'perspective', 'for')


def build_match_report(match, auto_analysis=None, auto_candidates=None):
    events = sorted(match.events, key=lambda e: e.second)
    counts = Counter(e.event_type for e in events)
    tactical = analyze_match_tactics(match)
    for_events = [e for e in events if _perspective(e) == 'for']
    against_events = [e for e in events if _perspective(e) == 'against']
    counts_for = Counter(e.event_type for e in for_events)
    counts_against = Counter(e.event_type for e in against_events)
    pp_for = [e for e in for_events if getattr(getattr(e, 'context_meta', None), 'phase_tag', '') == 'power_play']
    pp_against = [e for e in against_events if getattr(getattr(e, 'context_meta', None), 'phase_tag', '') == 'power_play']
    team_shots = sum(counts_for.get(x, 0) for x in ('shot_on_target','shot_off_target','shot_blocked','goal'))
    headline = [
        {"label": "Tagged score", "value": f"{counts_for.get('goal',0)}–{counts_against.get('goal',0)}", "detail": "from verified perspective tags"},
        {"label": "Team shots", "value": team_shots, "detail": "visible verified attempts"},
        {"label": "Turnovers", "value": counts_for.get('turnover', 0) + counts_for.get('bad_pass', 0), "detail": "team possession losses"},
        {"label": "Blocks + steals", "value": counts_for.get('block', 0) + counts_for.get('interception', 0), "detail": "team defensive events"},
    ]
    auto_summary = {}
    if auto_analysis:
        import json
        try: auto_summary = json.loads(auto_analysis.summary_json or '{}')
        except Exception: auto_summary = {}
    candidates = list(auto_candidates or [])
    data_quality = {
        "verified_events": len(events),
        "auto_candidates": len(candidates),
        "ocr_available": bool(getattr(auto_analysis, 'ocr_available', False)) if auto_analysis else False,
        "tactical_confidence": tactical.get("confidence", "INSUFFICIENT DATA"),
    }
    return {
        "headline": headline,
        "event_counts": counts,
        "counts_for": counts_for,
        "counts_against": counts_against,
        "tactical": tactical,
        "auto_summary": auto_summary,
        "auto_candidates": candidates,
        "data_quality": data_quality,
        "power_play_for_events": len(pp_for),
        "power_play_against_events": len(pp_against),
        "timeline": events,
        "executive_summary": _executive_summary(counts_for, counts_against, tactical, auto_summary),
    }


def _executive_summary(counts_for, counts_against, tactical, auto_summary):
    parts = []
    if counts_for.get('goal', 0) or counts_against.get('goal', 0):
        parts.append(f"Tagged score evidence currently reads {counts_for.get('goal',0)}–{counts_against.get('goal',0)}.")
    losses = counts_for.get('turnover',0)+counts_for.get('bad_pass',0)
    if losses:
        parts.append(f"{losses} verified team possession losses should be reviewed with their preceding sequence.")
    if tactical.get("event_count", 0):
        parts.append(f"Tactical interpretation currently has {tactical.get('confidence', 'insufficient data').lower()} confidence from {tactical.get('event_count', 0)} verified events.")
    if auto_summary.get('goal_candidates'):
        parts.append(f"The autonomous layer found {auto_summary['goal_candidates']} scoreboard-supported goal candidates that remain separate from verified truth.")
    if not parts:
        parts.append("The report is structurally ready, but more verified or automatically-supported evidence is required before strong conclusions are justified.")
    return " ".join(parts)
