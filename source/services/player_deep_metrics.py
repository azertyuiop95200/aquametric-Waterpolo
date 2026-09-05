from __future__ import annotations

from collections import Counter
import re
from statistics import mean

SHOT_EVENTS = {"goal", "shot_on_target", "shot_off_target", "shot_blocked"}
BALL_EVENTS = {
    "touch", "centre_touch", "pass_complete", "assist", "key_pass", "action_created",
    "goal", "shot_on_target", "shot_off_target", "shot_blocked", "bad_pass", "turnover",
    "exclusion_earned", "penalty_earned",
}
LOSS_LABELS = {
    "bad_pass": "Passe ratée", "centre_entry": "Entrée centre perdue", "counterattack": "Perte en contre-attaque",
    "offensive_foul": "Faute offensive", "shot_clock": "Fin de possession / 30 s", "steal": "Ballon volé",
    "handling": "Contrôle / ballon lâché", "other": "Autre perte",
}


def _pct(n, d):
    return round(100.0 * float(n) / float(d), 1) if d else None


def _note_number(note: str, key: str):
    pattern = re.compile(rf"(?:^|[; ,]){re.escape(key)}\s*[=:]\s*(-?\d+(?:\.\d+)?)", re.I)
    match = pattern.search(note or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _values(events, keys):
    rows = []
    for event in events:
        note = getattr(event, "note", "") or ""
        for key in keys:
            value = _note_number(note, key)
            if value is not None:
                rows.append(value)
                break
    return rows


def _explicit_playing_time(events):
    seconds = _values(events, ("playing_time_s", "time_played_s", "minutes_played_s", "match_playing_time_s"))
    minutes = _values(events, ("minutes_played", "playing_time_min", "time_played_min"))
    values = [v for v in seconds if v >= 0] + [v * 60.0 for v in minutes if v >= 0]
    if not values:
        return None, 0
    return round(max(values), 1), len(values)


def _distance(events):
    totals = _values(events, ("distance_total_m", "swim_distance_total_m", "match_distance_m", "distance_calibrated_m"))
    totals = [v for v in totals if v >= 0]
    if totals:
        return round(max(totals), 1), len(totals), "total_tag"
    segments = _values(events, ("distance_m", "swim_distance_m"))
    segments = [v for v in segments if v >= 0]
    if not segments:
        return None, 0, ""
    return round(sum(segments), 1), len(segments), "segment_sum"


def _physical(events, playing_time_s):
    distance_m, distance_samples, distance_method = _distance(events)
    sprint5 = _values(events, ("sprint_5m_s",))
    sprint10 = _values(events, ("sprint_10m_s",))
    swim_speed = _values(events, ("max_swim_speed_mps",))
    shot_speed = _values(events, ("shot_speed_kmh",))
    release = _values(events, ("release_time_s",))
    shot_distance = _values(events, ("shot_distance_m", "distance_shot_m"))

    def avg(values):
        return round(mean(values), 2) if values else None

    return {
        "distance_m": distance_m,
        "distance_samples": distance_samples,
        "distance_method": distance_method,
        "avg_speed_mps": round(distance_m / playing_time_s, 2) if distance_m is not None and playing_time_s else None,
        "sprint_5m_s_best": round(min(sprint5), 2) if sprint5 else None,
        "sprint_5m_samples": len(sprint5),
        "sprint_10m_s_best": round(min(sprint10), 2) if sprint10 else None,
        "sprint_10m_samples": len(sprint10),
        "max_swim_speed_mps": round(max(swim_speed), 2) if swim_speed else None,
        "swim_speed_samples": len(swim_speed),
        "shot_speed_kmh_avg": avg(shot_speed),
        "shot_speed_kmh_max": round(max(shot_speed), 2) if shot_speed else None,
        "shot_speed_samples": len(shot_speed),
        "release_time_s_avg": avg(release),
        "release_samples": len(release),
        "shot_distance_m_avg": avg(shot_distance),
        "shot_distance_samples": len(shot_distance),
        "policy": "Valeurs physiques affichées uniquement lorsqu'une mesure/calibration explicite est taguée.",
    }


def _meta(event):
    meta = getattr(event, "context_meta", None)
    return {
        "phase": getattr(meta, "phase_tag", "auto") if meta else "auto",
        "quality": getattr(meta, "quality_tag", "") if meta else "",
    }


def _loss_reason(event):
    note = (getattr(event, "note", "") or "").lower()
    quality = (_meta(event).get("quality") or "").lower()
    text = f"{note} {quality}"
    if getattr(event, "event_type", "") == "bad_pass":
        if any(k in text for k in ("centre", "center", "2m", "entry")):
            return "centre_entry"
        return "bad_pass"
    if any(k in text for k in ("counter", "transition", "fast break", "contre")):
        return "counterattack"
    if any(k in text for k in ("offensive foul", "faute offensive", "push off")):
        return "offensive_foul"
    if any(k in text for k in ("shot clock", "30s", "30 s")):
        return "shot_clock"
    if any(k in text for k in ("steal", "stolen", "ballon vol")):
        return "steal"
    if any(k in text for k in ("handling", "drop ball", "control", "contrôle", "lâché", "lache")):
        return "handling"
    return "other"


def _loss_breakdown(events):
    losses = [e for e in events if getattr(e, "event_type", "") in {"turnover", "bad_pass"}]
    counts = Counter(_loss_reason(e) for e in losses)
    total = len(losses)
    return [
        {"key": key, "label": LOSS_LABELS.get(key, key), "count": value, "share_pct": _pct(value, total)}
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def player_deep_metrics(player, events):
    events = sorted(list(events or []), key=lambda e: float(getattr(e, "second", 0) or 0))
    c = Counter(getattr(e, "event_type", "") for e in events)
    phases = Counter()
    for event in events:
        phase = _meta(event)["phase"]
        if phase and phase != "auto":
            phases[phase] += 1
    shots = sum(c[x] for x in SHOT_EVENTS)
    shots_on_target = c["goal"] + c["shot_on_target"]
    passes_completed = c["pass_complete"] + c["assist"]
    passes_failed = c["bad_pass"]
    pass_attempts = passes_completed + passes_failed
    losses = c["turnover"] + c["bad_pass"]
    duels = c["duel_won"] + c["duel_lost"]
    touches = c["touch"] + c["centre_touch"]
    playing_time_s, playing_time_samples = _explicit_playing_time(events)
    physical = _physical(events, playing_time_s)
    ball_actions = sum(c[x] for x in BALL_EVENTS)

    measured_groups = {
        "touches": touches > 0,
        "passes": pass_attempts > 0,
        "shots": shots > 0,
        "duels": duels > 0,
        "turnovers": losses > 0,
        "playing_time": playing_time_s is not None,
        "distance": physical["distance_m"] is not None,
        "speed": physical["max_swim_speed_mps"] is not None or physical["shot_speed_kmh_max"] is not None,
    }
    coverage_score = round(100.0 * sum(measured_groups.values()) / len(measured_groups), 1)

    return {
        "id": getattr(player, "id", None),
        "name": getattr(player, "name", ""),
        "cap": getattr(player, "cap_number", None),
        "role": getattr(player, "primary_role", "") or "À confirmer",
        "event_count": len(events),
        "coverage_score": coverage_score,
        "coverage_groups": measured_groups,
        "touches": touches,
        "centre_touches": c["centre_touch"],
        "ball_actions_tagged": ball_actions,
        "passes_completed": passes_completed,
        "passes_failed": passes_failed,
        "pass_attempts": pass_attempts,
        "pass_completion_pct": _pct(passes_completed, pass_attempts),
        "key_passes": c["key_pass"],
        "assists": c["assist"],
        "actions_created": c["action_created"],
        "shots": shots,
        "goals": c["goal"],
        "shots_on_target": shots_on_target,
        "shots_off_target": c["shot_off_target"],
        "shots_blocked": c["shot_blocked"],
        "shot_accuracy_pct": _pct(shots_on_target, shots),
        "scoring_efficiency_pct": _pct(c["goal"], shots),
        "turnovers": losses,
        "bad_passes": c["bad_pass"],
        "loss_breakdown": _loss_breakdown(events),
        "duels": duels,
        "duels_won": c["duel_won"],
        "duels_lost": c["duel_lost"],
        "duel_success_pct": _pct(c["duel_won"], duels),
        "interceptions": c["interception"],
        "recoveries": c["recovery"],
        "blocks": c["block"],
        "saves": c["save"],
        "fouls": c["foul"],
        "exclusions_earned": c["exclusion_earned"],
        "exclusions_committed": c["exclusion_committed"],
        "penalties_earned": c["penalty_earned"],
        "penalties_committed": c["penalty_committed"],
        "counterattack_starts": c["counterattack_start"],
        "fast_recoveries": c["fast_recovery"],
        "late_recoveries": c["late_recovery"],
        "phases": dict(phases),
        "playing_time_s": playing_time_s,
        "playing_time_min": round(playing_time_s / 60.0, 1) if playing_time_s is not None else None,
        "playing_time_samples": playing_time_samples,
        "touches_per_min": round(touches * 60.0 / playing_time_s, 2) if touches and playing_time_s else None,
        "ball_actions_per_min": round(ball_actions * 60.0 / playing_time_s, 2) if ball_actions and playing_time_s else None,
        "physical": physical,
        "first_event_s": round(float(events[0].second or 0), 1) if events else None,
        "last_event_s": round(float(events[-1].second or 0), 1) if events else None,
    }


def team_player_totals(players):
    keys = (
        "touches", "centre_touches", "ball_actions_tagged", "passes_completed", "passes_failed",
        "pass_attempts", "key_passes", "assists", "actions_created", "shots", "goals",
        "shots_on_target", "shots_off_target", "shots_blocked", "turnovers", "duels",
        "duels_won", "duels_lost", "interceptions", "recoveries", "blocks", "saves", "fouls",
        "exclusions_earned", "exclusions_committed", "penalties_earned", "penalties_committed",
        "counterattack_starts", "fast_recoveries", "late_recoveries",
    )
    totals = {key: sum(int(p.get(key) or 0) for p in players) for key in keys}
    totals["pass_completion_pct"] = _pct(totals["passes_completed"], totals["pass_attempts"])
    totals["shot_accuracy_pct"] = _pct(totals["shots_on_target"], totals["shots"])
    totals["scoring_efficiency_pct"] = _pct(totals["goals"], totals["shots"])
    totals["duel_success_pct"] = _pct(totals["duels_won"], totals["duels"])
    totals["players_with_playing_time"] = sum(1 for p in players if p.get("playing_time_s") is not None)
    totals["players_with_distance"] = sum(1 for p in players if p.get("physical", {}).get("distance_m") is not None)
    totals["players_with_touches"] = sum(1 for p in players if p.get("touches"))
    return totals
