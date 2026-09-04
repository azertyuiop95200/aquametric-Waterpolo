"""Autonomous evidence interpreter.

This layer converts low-level visual/OCR observations into candidates. It never
fabricates player/ball events. Score changes are bracketed by scoreboard evidence
and, when possible, focused on the strongest visual peak inside that bracket so the
review clip is materially closer to the action than the next sparse OCR sample.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class AutoCandidate:
    second: float
    event_type: str
    confidence: float
    confidence_label: str
    summary: str
    evidence: dict[str, Any]

    def to_dict(self):
        return asdict(self)


def confidence_label(value: float) -> str:
    if value >= 0.88:
        return "HIGH"
    if value >= 0.68:
        return "MODERATE"
    return "LOW"


def _stable_score(obs: list[dict]) -> list[dict]:
    result = []
    last = None
    for row in sorted(obs, key=lambda x: float(x.get("second", 0))):
        h, a = row.get("home_score"), row.get("away_score")
        if h is None or a is None:
            continue
        if not (0 <= int(h) <= 40 and 0 <= int(a) <= 40):
            continue
        current = (int(h), int(a))
        if last is not None:
            if current[0] < last[0] or current[1] < last[1]:
                continue
            if current[0] - last[0] > 2 or current[1] - last[1] > 2:
                continue
        row = dict(row)
        row["home_score"], row["away_score"] = current
        result.append(row)
        last = current
    return result


def infer_periods(observations: list[dict], duration: float) -> list[dict]:
    by_period: dict[int, list[dict]] = {}
    for row in observations:
        q = row.get("period")
        if q in (1, 2, 3, 4):
            by_period.setdefault(int(q), []).append(row)
    periods = []
    for q in sorted(by_period):
        rows = sorted(by_period[q], key=lambda x: float(x.get("second", 0)))
        start = float(rows[0]["second"])
        end = float(rows[-1]["second"])
        periods.append({
            "period": q, "start_second": round(start, 2), "end_second": round(end, 2),
            "confidence": confidence_label(min(0.95, 0.55 + 0.08 * len(rows))),
            "evidence_count": len(rows),
        })
    return periods


def _best_visual_focus(interesting_moments: list[dict], start: float, end: float):
    inside = [
        item for item in interesting_moments
        if start <= float(item.get("second", -1)) <= end
    ]
    if not inside:
        return None
    return max(inside, key=lambda item: float(item.get("score", 0) or 0))


def _score_change_candidate(prev: dict, row: dict, side: str, delta: int, interesting_moments: list[dict]) -> AutoCandidate:
    start = float(prev.get("second", 0) or 0)
    end = float(row.get("second", start) or start)
    focus = _best_visual_focus(interesting_moments, start, end)
    ocr_conf = min(float(row.get("ocr_confidence", 0.5)), float(prev.get("ocr_confidence", 0.5)))
    visual_score = float(focus.get("score", 0) or 0) if focus else 0.0
    # The score change itself is strong evidence that scoring occurred in the bracket;
    # the visual peak improves clip focus but never makes the exact goal time certain.
    base = ocr_conf * (0.92 if delta == 1 else 0.78)
    conf = min(0.9, base + min(0.08, visual_score * 0.08))
    second = float(focus["second"]) if focus else end
    before_score = [prev["home_score"], prev["away_score"]]
    after_score = [row["home_score"], row["away_score"]]
    team_label = "home" if side == "home" else "away"
    event_type = f"goal_candidate_{team_label}" if delta == 1 else f"score_change_window_{team_label}"
    if focus:
        summary = (
            f"Scoreboard changed {before_score[0]}-{before_score[1]} → {after_score[0]}-{after_score[1]} "
            f"between {start:.1f}s and {end:.1f}s; review focused on the strongest visual peak at {second:.1f}s."
        )
    else:
        summary = (
            f"Scoreboard changed {before_score[0]}-{before_score[1]} → {after_score[0]}-{after_score[1]} "
            f"between {start:.1f}s and {end:.1f}s. Exact scoring instant is not localized."
        )
    return AutoCandidate(
        second,
        event_type,
        conf,
        confidence_label(conf),
        summary,
        {
            "before": before_score,
            "after": after_score,
            "delta": delta,
            "side": side,
            "signal": "scoreboard_ocr+visual_focus" if focus else "scoreboard_ocr",
            "bracket_start_second": round(start, 2),
            "bracket_end_second": round(end, 2),
            "visual_focus_second": round(second, 2) if focus else None,
            "visual_activity_score": round(visual_score, 3) if focus else None,
            "time_precision": "visual_focus_within_score_bracket" if focus else "score_bracket_only",
        },
    )


def infer_candidates(observations: list[dict], interesting_moments: list[dict]) -> list[AutoCandidate]:
    candidates: list[AutoCandidate] = []
    stable = _stable_score(observations)
    prev = None
    for row in stable:
        if prev is not None:
            dh = row["home_score"] - prev["home_score"]
            da = row["away_score"] - prev["away_score"]
            if dh in (1, 2) and da == 0:
                candidates.append(_score_change_candidate(prev, row, "home", dh, interesting_moments))
            elif da in (1, 2) and dh == 0:
                candidates.append(_score_change_candidate(prev, row, "away", da, interesting_moments))
            if row.get("period") and prev.get("period") and int(row["period"]) != int(prev["period"]):
                conf = min(float(row.get("ocr_confidence", 0.5)), float(prev.get("ocr_confidence", 0.5))) * 0.85
                candidates.append(AutoCandidate(
                    float(row["second"]), "period_change_candidate", conf, confidence_label(conf),
                    f"Scoreboard period changed Q{prev['period']} → Q{row['period']}.",
                    {
                        "before_period": prev["period"], "after_period": row["period"],
                        "signal": "scoreboard_ocr", "bracket_start_second": float(prev.get("second", 0)),
                        "bracket_end_second": float(row.get("second", 0)),
                    },
                ))
        prev = row

    # Vision-only peaks stay generic. They are review targets, not sporting truth.
    for item in interesting_moments[:16]:
        sec = float(item.get("second", 0))
        score = float(item.get("score", 0))
        if any(abs(sec - c.second) < 4 for c in candidates):
            continue
        conf = min(0.55, max(0.2, score * 0.55))
        candidates.append(AutoCandidate(
            sec, "unclassified_action_candidate", conf, "LOW",
            "High visual activity detected; action type requires ball/player/audio models.",
            {"visual_activity_score": round(score, 3), "signal": "visual_baseline"},
        ))
    return sorted(candidates, key=lambda x: x.second)


def build_auto_summary(observations: list[dict], periods: list[dict], candidates: list[AutoCandidate]) -> dict:
    goals = [c for c in candidates if c.event_type.startswith("goal_candidate")]
    score_windows = [c for c in candidates if c.event_type.startswith("score_change_window")]
    focused = [c for c in goals + score_windows if c.evidence.get("visual_focus_second") is not None]
    return {
        "scoreboard_observations": len(observations),
        "periods_observed": len(periods),
        "goal_candidates": len(goals),
        "multi_goal_score_windows": len(score_windows),
        "score_changes_with_visual_focus": len(focused),
        "action_candidates": len(candidates),
        "autonomy_level": "L1.5 — scoreboard + visual focus + optional audio",
        "next_required_models": ["player/team detection", "ball tracking", "possession/event classifier"],
        "scientific_honesty": "Score changes are bracketed by OCR; visual peaks only refine the review timestamp and do not prove the exact scoring instant.",
    }
