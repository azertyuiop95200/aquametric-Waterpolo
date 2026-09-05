from __future__ import annotations

import re
from collections import Counter
from statistics import mean

from services.performance_intelligence import player_match_breakdown


_NUMERIC = re.compile(r"(?:^|[; ,])(?P<key>[a-zA-Z0-9_]+)\s*[=:]\s*(?P<value>\d+(?:\.\d+)?)", re.I)


def _note_metrics(events) -> dict[str, list[float]]:
    values: dict[str, list[float]] = {}
    for event in events:
        note = getattr(event, "note", "") or ""
        for match in _NUMERIC.finditer(note):
            key = match.group("key").strip().lower()
            try:
                value = float(match.group("value"))
            except ValueError:
                continue
            values.setdefault(key, []).append(value)
    return values


def _first(values: dict[str, list[float]], *keys: str):
    for key in keys:
        rows = values.get(key.lower()) or []
        if rows:
            return rows[-1]
    return None


def _max(values: dict[str, list[float]], *keys: str):
    rows = []
    for key in keys:
        rows.extend(values.get(key.lower()) or [])
    return max(rows) if rows else None


def _avg(values: dict[str, list[float]], *keys: str):
    rows = []
    for key in keys:
        rows.extend(values.get(key.lower()) or [])
    return round(mean(rows), 2) if rows else None


def _fmt_seconds(value):
    if value is None:
        return None
    seconds = max(0, int(round(float(value))))
    return {"seconds": seconds, "text": f"{seconds // 60}:{seconds % 60:02d}"}


def build_player_premium_metrics(events, *, role: str = "") -> dict:
    """Return the complete V12.2 player surface without inventing unavailable data.

    Event counts come from validated/tagged events. Absolute physical metrics are
    exposed only when an explicit numeric measurement is present in an event note.
    Supported total tags include playing_time_s/minutes_played, distance_m/km,
    sprint_5m_s, sprint_10m_s, max_swim_speed_mps, shot_speed_kmh and release_time_s.
    """
    events = sorted(list(events or []), key=lambda e: float(getattr(e, "second", 0) or 0))
    breakdown = player_match_breakdown(events, {"rated": False, "dimensions": {}}, role=role)
    board = dict(breakdown.get("statboard", {}) or {})
    counts = Counter(getattr(e, "event_type", "") for e in events)
    metrics = _note_metrics(events)

    # Technical event surface.
    generic_touches = int(counts.get("touch", 0) or 0)
    centre_touches = int(counts.get("centre_touch", 0) or 0)
    board.update({
        "ball_touches": generic_touches + centre_touches,
        "generic_touches": generic_touches,
        "centre_touches": centre_touches,
        "duels_total": int(counts.get("duel_won", 0) or 0) + int(counts.get("duel_lost", 0) or 0),
        "fouls": int(counts.get("foul", 0) or 0),
        "penalties_earned": int(counts.get("penalty_earned", 0) or 0),
        "penalties_committed": int(counts.get("penalty_committed", 0) or 0),
        "power_play_starts": int(counts.get("power_play_start", 0) or 0),
        "penalty_kill_starts": int(counts.get("penalty_kill_start", 0) or 0),
        "counterattack_starts": int(counts.get("counterattack_start", 0) or 0),
        "fast_recoveries": int(counts.get("fast_recovery", 0) or 0),
        "late_recoveries": int(counts.get("late_recovery", 0) or 0),
    })

    # Playing time: never infer from first/last action because that overstates real minutes.
    playing_time_s = _max(metrics, "playing_time_s", "time_played_s", "match_playing_time_s")
    if playing_time_s is None:
        minutes = _max(metrics, "minutes_played", "playing_time_min", "time_played_min")
        playing_time_s = float(minutes) * 60.0 if minutes is not None else None

    # Distance: require an explicit calibrated/measurement tag. We accept common
    # names but do not derive metres from video pixels.
    distance_m = _max(metrics, "distance_m", "match_distance_m", "distance_calibrated_m")
    if distance_m is None:
        distance_km = _max(metrics, "distance_km", "match_distance_km")
        distance_m = float(distance_km) * 1000.0 if distance_km is not None else None

    physical = {
        "playing_time": _fmt_seconds(playing_time_s),
        "distance_m": round(distance_m, 1) if distance_m is not None else None,
        "sprint_5m_s": _avg(metrics, "sprint_5m_s"),
        "sprint_10m_s": _avg(metrics, "sprint_10m_s"),
        "max_swim_speed_mps": _max(metrics, "max_swim_speed_mps"),
        "shot_speed_kmh": _max(metrics, "shot_speed_kmh"),
        "release_time_s": _avg(metrics, "release_time_s"),
        "calibrated": bool(distance_m is not None or _max(metrics, "max_swim_speed_mps", "shot_speed_kmh") is not None),
        "policy": "Temps de jeu et métriques physiques absolues uniquement si explicitement mesurés/tagués ; aucune conversion pixels→mètres sans calibration.",
    }

    observed_span = None
    if len(events) >= 2:
        start = float(getattr(events[0], "second", 0) or 0)
        end = float(getattr(events[-1], "second", 0) or 0)
        if end >= start:
            observed_span = _fmt_seconds(end - start)

    return {
        **breakdown,
        "statboard": board,
        "physical": physical,
        "observed_action_span": observed_span,
        "measurement_tags": sorted(metrics.keys()),
        "measurement_contract": {
            "event_counts": "TAGUÉ / VÉRIFIÉ",
            "playing_time": "MESURÉ" if physical["playing_time"] else "NON MESURÉ",
            "distance": "CALIBRÉ" if physical["distance_m"] is not None else "NON MESURÉ",
            "absolute_speed": "CALIBRÉ" if physical["calibrated"] else "NON MESURÉ",
        },
    }
