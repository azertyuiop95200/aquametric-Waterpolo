"""Autonomous evidence interpreter.

This layer converts low-level visual/OCR observations into candidates. It never
fabricates player/ball events. A goal candidate can only come from a stable
scoreboard increment; visual activity alone can never create or duplicate a goal.
Replay/break/final observations and period resets are excluded from goal counting.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import re


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


def _valid_score_rows(obs: list[dict]) -> list[dict]:
    rows = []
    for raw in sorted(obs, key=lambda x: float(x.get("second", 0))):
        h, a = raw.get("home_score"), raw.get("away_score")
        if h is None or a is None:
            continue
        try:
            current = (int(h), int(a))
        except (TypeError, ValueError):
            continue
        if not (0 <= current[0] <= 40 and 0 <= current[1] <= 40):
            continue
        row = dict(raw)
        row["home_score"], row["away_score"] = current
        rows.append(row)
    return rows


def _same_period(a: dict, b: dict) -> bool:
    pa, pb = a.get("period"), b.get("period")
    return pa is None or pb is None or int(pa) == int(pb)


def _status_kind(row: dict) -> str:
    if row.get("is_replay"):
        return "replay"
    if row.get("is_break"):
        return "break"
    if row.get("is_final"):
        return "final"
    text = " ".join(str(row.get("normalized_text") or row.get("raw_text") or "").upper().split())
    if re.search(r"\b(?:REPLAY|RALENTI|SLOW\s*MOTION|SLOWMO)\b", text):
        return "replay"
    if re.search(r"\b(?:FINAL|FULL\s*TIME|FIN\s+DU\s+MATCH|MATCH\s+TERMINE|FT)\b", text):
        return "final"
    if re.search(r"\b(?:BREAK|PAUSE|INTERVAL|HALF\s*TIME|HALFTIME|END\s+OF\s+(?:Q|QUARTER|PERIOD)|QUARTER\s+BREAK)\b", text):
        return "break"
    return "live_or_unknown"


def _status_blocked(row: dict) -> bool:
    return _status_kind(row) in {"replay", "break", "final"}


def _score_state_confirmed(rows: list[dict], index: int, horizon: int = 3) -> bool:
    """Require nearby scoreboard support before treating an increment as a goal.

    This rejects single OCR spikes. A later equal score or a later monotonic score
    that necessarily contains the candidate state counts as confirmation.
    """
    row = rows[index]
    h, a = int(row["home_score"]), int(row["away_score"])
    period = row.get("period")
    for later in rows[index + 1:index + 1 + max(1, horizon)]:
        if _status_blocked(later):
            continue
        lp = later.get("period")
        if period is not None and lp is not None and int(lp) != int(period):
            break
        lh, la = int(later["home_score"]), int(later["away_score"])
        if (lh, la) == (h, a):
            return True
        if lh >= h and la >= a and (lh - h) + (la - a) <= 2:
            return True
        if lh < h or la < a:
            continue
    return False


def _stable_score(obs: list[dict]) -> list[dict]:
    rows = _valid_score_rows(obs)
    result: list[dict] = []
    last: tuple[int, int] | None = None
    for idx, row in enumerate(rows):
        current = (int(row["home_score"]), int(row["away_score"]))
        row["score_state_confirmed"] = _score_state_confirmed(rows, idx) or idx == 0
        if last is not None:
            if current[0] < last[0] or current[1] < last[1]:
                continue
            if current[0] - last[0] > 2 or current[1] - last[1] > 2:
                continue
        result.append(row)
        if not _status_blocked(row) and (
            last is None or current == last or bool(row.get("score_state_confirmed"))
        ):
            # A one-frame upward OCR spike is kept as a review window but never
            # becomes the live baseline that would invalidate later real readings.
            last = current
    return result


def infer_periods(observations: list[dict], duration: float) -> list[dict]:
    by_period: dict[int, list[dict]] = {}
    for row in observations:
        if _status_kind(row) == "replay":
            continue
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
    inside = [item for item in interesting_moments if start <= float(item.get("second", -1)) <= end]
    if not inside:
        return None
    return max(inside, key=lambda item: float(item.get("score", 0) or 0))


def _clock_state(prev: dict, row: dict) -> str:
    if not _same_period(prev, row):
        return "period_reset"
    pc, rc = prev.get("clock_seconds"), row.get("clock_seconds")
    if pc is None or rc is None:
        return "unknown"
    try:
        pc, rc = int(pc), int(rc)
    except (TypeError, ValueError):
        return "unknown"
    if rc > pc + 3:
        return "clock_reset_or_inconsistent"
    if rc < pc:
        return "live_clock_progress"
    return "clock_stopped"


def _score_change_candidate(
    prev: dict,
    row: dict,
    side: str,
    delta: int,
    interesting_moments: list[dict],
    *,
    strict_goal: bool,
) -> AutoCandidate:
    start = float(prev.get("second", 0) or 0)
    end = float(row.get("second", start) or start)
    clock_state = _clock_state(prev, row)
    focus = _best_visual_focus(interesting_moments, start, end)
    ocr_conf = min(float(row.get("ocr_confidence", 0.5)), float(prev.get("ocr_confidence", 0.5)))
    before_score = [prev["home_score"], prev["away_score"]]
    after_score = [row["home_score"], row["away_score"]]
    team_label = "home" if side == "home" else "away"
    visual_score = float(focus.get("score", 0) or 0) if focus else 0.0
    second = end
    if strict_goal:
        base = ocr_conf * 0.94
        if clock_state == "live_clock_progress":
            base += 0.03
        conf = min(0.94, base)
        event_type = f"goal_candidate_{team_label}"
        summary = (
            f"Bandeau confirmé {before_score[0]}-{before_score[1]} → {after_score[0]}-{after_score[1]} "
            f"entre {start:.1f}s et {end:.1f}s. Le but est compté depuis le changement du bandeau, "
            "jamais depuis une image de ralenti/replay; l'instant exact reste dans cette fenêtre."
        )
    else:
        conf = min(0.72, ocr_conf * 0.78)
        event_type = f"score_change_window_{team_label}"
        summary = (
            f"Variation de bandeau {before_score[0]}-{before_score[1]} → {after_score[0]}-{after_score[1]} "
            f"entre {start:.1f}s et {end:.1f}s, conservée comme fenêtre à vérifier et non comme but validé."
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
            "signal": "stable_scoreboard_ocr",
            "bracket_start_second": round(start, 2),
            "bracket_end_second": round(end, 2),
            "visual_focus_second": round(float(focus["second"]), 2) if focus else None,
            "visual_activity_score": round(visual_score, 3) if focus else None,
            "time_precision": "score_bracket_only",
            "play_state": clock_state,
            "score_state_confirmed": bool(row.get("score_state_confirmed")),
            "replay_guard": "visual peaks never create/count goals; replay/break/final rows are excluded",
            "counting_rule": "one-team +1 scoreboard increment only" if strict_goal else "not counted as a confirmed goal",
        },
    )


def infer_candidates(observations: list[dict], interesting_moments: list[dict]) -> list[AutoCandidate]:
    candidates: list[AutoCandidate] = []
    stable = _stable_score(observations)
    prev = None
    for row in stable:
        if prev is not None:
            period_changed = (
                row.get("period") is not None
                and prev.get("period") is not None
                and int(row["period"]) != int(prev["period"])
            )
            if period_changed:
                conf = min(float(row.get("ocr_confidence", 0.5)), float(prev.get("ocr_confidence", 0.5))) * 0.85
                candidates.append(AutoCandidate(
                    float(row["second"]), "period_change_candidate", conf, confidence_label(conf),
                    f"Scoreboard period changed Q{prev['period']} → Q{row['period']}.",
                    {
                        "before_period": prev["period"], "after_period": row["period"],
                        "signal": "scoreboard_ocr", "bracket_start_second": float(prev.get("second", 0)),
                        "bracket_end_second": float(row.get("second", 0)),
                        "play_state": "quarter_break_or_period_transition",
                    },
                ))
                prev = row
                continue

            if _status_blocked(prev) or _status_blocked(row):
                prev = row
                continue

            dh = row["home_score"] - prev["home_score"]
            da = row["away_score"] - prev["away_score"]
            clock_state = _clock_state(prev, row)
            reset_like = clock_state in {"period_reset", "clock_reset_or_inconsistent"}
            if not reset_like and dh == 1 and da == 0:
                strict = bool(row.get("score_state_confirmed"))
                candidates.append(_score_change_candidate(prev, row, "home", 1, interesting_moments, strict_goal=strict))
            elif not reset_like and da == 1 and dh == 0:
                strict = bool(row.get("score_state_confirmed"))
                candidates.append(_score_change_candidate(prev, row, "away", 1, interesting_moments, strict_goal=strict))
            elif not reset_like and ((dh in (1, 2) and da == 0) or (da in (1, 2) and dh == 0)):
                side, delta = ("home", dh) if dh else ("away", da)
                candidates.append(_score_change_candidate(prev, row, side, delta, interesting_moments, strict_goal=False))
        prev = row

    for item in interesting_moments[:16]:
        sec = float(item.get("second", 0))
        score = float(item.get("score", 0))
        if any(abs(sec - c.second) < 4 for c in candidates):
            continue
        conf = min(0.55, max(0.2, score * 0.55))
        candidates.append(AutoCandidate(
            sec, "unclassified_action_candidate", conf, "LOW",
            "High visual activity detected; action type requires ball/player/audio models and is never counted as a goal by itself.",
            {"visual_activity_score": round(score, 3), "signal": "visual_baseline", "counting_rule": "never a goal without scoreboard transition"},
        ))
    return sorted(candidates, key=lambda x: x.second)


def build_auto_summary(observations: list[dict], periods: list[dict], candidates: list[AutoCandidate]) -> dict:
    goals = [c for c in candidates if c.event_type.startswith("goal_candidate")]
    score_windows = [c for c in candidates if c.event_type.startswith("score_change_window")]
    replay_rows = [row for row in observations if _status_kind(row) == "replay"]
    break_rows = [row for row in observations if _status_kind(row) == "break"]
    final_rows = [row for row in observations if _status_kind(row) == "final"]
    return {
        "scoreboard_observations": len(observations),
        "periods_observed": len(periods),
        "goal_candidates": len(goals),
        "multi_goal_score_windows": len(score_windows),
        "score_changes_with_visual_focus": len([c for c in goals + score_windows if c.evidence.get("visual_focus_second") is not None]),
        "action_candidates": len(candidates),
        "replay_observations_ignored_for_goals": len(replay_rows),
        "break_observations_ignored_for_goals": len(break_rows),
        "final_observations_ignored_for_goals": len(final_rows),
        "autonomy_level": "L1.7 — stable scoreboard truth gate + replay/break guard + visual review",
        "next_required_models": ["dense scoreboard refinement", "player/team detection", "ball tracking", "possession/event classifier"],
        "scientific_honesty": (
            "Goals can only originate from a stable +1 scoreboard transition on one side. "
            "Replays, quarter breaks, final screens, period resets and visual peaks cannot create a goal. "
            "Visual activity may suggest where to review, but never proves the live scoring instant."
        ),
    }
