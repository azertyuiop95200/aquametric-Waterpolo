"""Autonomous evidence interpreter v0.1.

This layer converts low-level visual/OCR observations into *candidates*. It does
not fabricate player/ball events. Score changes and period changes can be inferred
from scoreboard evidence; generic visual peaks remain explicitly unclassified.
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
    """Drop impossible/isolated score OCR jumps while preserving evidence."""
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
            # Water-polo score cannot decrease; huge jumps are OCR noise.
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
    # If no OCR period exists, do not invent quarter boundaries.
    return periods


def infer_candidates(observations: list[dict], interesting_moments: list[dict]) -> list[AutoCandidate]:
    candidates: list[AutoCandidate] = []
    stable = _stable_score(observations)
    prev = None
    for row in stable:
        if prev is not None:
            dh = row["home_score"] - prev["home_score"]
            da = row["away_score"] - prev["away_score"]
            if dh == 1 and da == 0:
                conf = min(float(row.get("ocr_confidence", 0.5)), float(prev.get("ocr_confidence", 0.5))) * 0.92
                candidates.append(AutoCandidate(float(row["second"]), "goal_candidate_home", conf, confidence_label(conf),
                    f"Scoreboard increased from {prev['home_score']}-{prev['away_score']} to {row['home_score']}-{row['away_score']}.",
                    {"before": [prev['home_score'], prev['away_score']], "after": [row['home_score'], row['away_score']], "signal": "scoreboard_ocr"}))
            elif da == 1 and dh == 0:
                conf = min(float(row.get("ocr_confidence", 0.5)), float(prev.get("ocr_confidence", 0.5))) * 0.92
                candidates.append(AutoCandidate(float(row["second"]), "goal_candidate_away", conf, confidence_label(conf),
                    f"Scoreboard increased from {prev['home_score']}-{prev['away_score']} to {row['home_score']}-{row['away_score']}.",
                    {"before": [prev['home_score'], prev['away_score']], "after": [row['home_score'], row['away_score']], "signal": "scoreboard_ocr"}))
            if row.get("period") and prev.get("period") and int(row["period"]) != int(prev["period"]):
                conf = min(float(row.get("ocr_confidence", 0.5)), float(prev.get("ocr_confidence", 0.5))) * 0.85
                candidates.append(AutoCandidate(float(row["second"]), "period_change_candidate", conf, confidence_label(conf),
                    f"Scoreboard period changed Q{prev['period']} → Q{row['period']}.",
                    {"before_period": prev["period"], "after_period": row["period"], "signal": "scoreboard_ocr"}))
        prev = row

    # Vision-only peaks stay generic. They are useful for clip selection, not truth.
    for item in interesting_moments[:12]:
        sec = float(item.get("second", 0))
        score = float(item.get("score", 0))
        if any(abs(sec - c.second) < 5 for c in candidates):
            continue
        conf = min(0.55, max(0.2, score * 0.55))
        candidates.append(AutoCandidate(sec, "unclassified_action_candidate", conf, "LOW",
            "High visual activity detected; action type requires ball/player/audio models.",
            {"visual_activity_score": round(score, 3), "signal": "visual_baseline"}))
    return sorted(candidates, key=lambda x: x.second)


def build_auto_summary(observations: list[dict], periods: list[dict], candidates: list[AutoCandidate]) -> dict:
    goals = [c for c in candidates if c.event_type.startswith("goal_candidate")]
    return {
        "scoreboard_observations": len(observations),
        "periods_observed": len(periods),
        "goal_candidates": len(goals),
        "action_candidates": len(candidates),
        "autonomy_level": "L1 — scoreboard + visual evidence",
        "next_required_models": ["player/team detection", "ball tracking", "whistle/audio", "possession/event classifier"],
        "scientific_honesty": "Only scoreboard-supported score changes are promoted to goal candidates. Visual peaks remain unclassified.",
    }
