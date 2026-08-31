"""Match-level statistics for AquaMetric.

The module exposes the complete metric catalogue discussed for scouting/match analysis,
but it never turns missing evidence into invented numbers. Verified/tagged Event rows
feed the counters. Metrics without enough evidence remain ``None`` with an explicit
coverage reason so the UI can show the schema for every match without pretending that
computer vision already produced facts it cannot support.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

SHOT_EVENTS = {"goal", "shot_on_target", "shot_off_target", "shot_blocked"}

METRIC_CATALOG = (
    ("attack", "Attaque", (
        ("goals", "Buts"), ("shots", "Tirs"), ("shot_efficiency", "Efficacité tir"),
        ("shots_on_target", "Tirs cadrés"), ("shot_on_target_rate", "% cadrés"),
        ("assists", "Passes décisives"), ("key_passes", "Passes clés"),
        ("actions_created", "Actions créées"), ("passes_complete", "Passes réussies"),
        ("touches", "Ballons touchés"), ("centre_touches", "Ballons touchés en pointe"),
        ("exclusions_earned", "Exclusions provoquées"), ("penalties_earned", "Penalties provoqués"),
    )),
    ("centre_duels", "Pointe & duels", (
        ("centre_touches", "Touches pointe"), ("duels_won", "Duels gagnés"),
        ("duels_lost", "Duels perdus"), ("duel_win_rate", "% duels gagnés"),
        ("turnovers_under_pressure", "Pertes sous pression"),
    )),
    ("defence", "Défense", (
        ("steals", "Interceptions / steals"), ("blocks", "Contres"),
        ("recoveries", "Récupérations"), ("fouls", "Fautes"),
        ("exclusions_committed", "Exclusions concédées"), ("shot_contests", "Tirs contestés"),
    )),
    ("transition", "Transition", (
        ("counterattacks", "Contre-attaques"), ("defensive_recoveries", "Replis"),
        ("fast_recovery", "Replis rapides"), ("late_recovery", "Replis tardifs"),
        ("transition_involvement", "Implication transition"),
    )),
    ("special", "Supériorité / infériorité", (
        ("power_play_starts", "Supériorités"), ("penalty_kill_starts", "Infériorités"),
        ("penalties_earned", "Penalties provoqués"), ("penalties_committed", "Penalties concédés"),
    )),
    ("goalkeeper", "Gardienne", (
        ("saves", "Arrêts"), ("shots_on_goal_received", "Tirs cadrés reçus"),
        ("save_efficiency", "% arrêts"), ("distribution_complete", "Relances réussies"),
        ("distribution_lost", "Relances perdues"), ("restart_time", "Temps de relance"),
    )),
)

EVENT_TO_METRIC = {
    "goal": "goals", "assist": "assists", "key_pass": "key_passes",
    "action_created": "actions_created", "pass_complete": "passes_complete",
    "touch": "touches", "centre_touch": "centre_touches", "duel_won": "duels_won",
    "duel_lost": "duels_lost", "shot_on_target": "shots_on_target",
    "shot_blocked": "blocked_shots", "block": "blocks", "interception": "steals",
    "recovery": "recoveries", "save": "saves", "bad_pass": "bad_passes",
    "turnover": "turnovers", "foul": "fouls", "exclusion_earned": "exclusions_earned",
    "exclusion_committed": "exclusions_committed", "penalty_earned": "penalties_earned",
    "penalty_committed": "penalties_committed", "power_play_start": "power_play_starts",
    "penalty_kill_start": "penalty_kill_starts", "counterattack_start": "counterattacks",
    "defensive_recovery_start": "defensive_recoveries", "fast_recovery": "fast_recovery",
    "late_recovery": "late_recovery",
}


def _event_context(event) -> tuple[str, str]:
    ctx = getattr(event, "context_meta", None)
    perspective = (getattr(ctx, "perspective", "") or "for").strip().lower()
    phase = (getattr(ctx, "phase_tag", "") or "auto").strip().lower()
    return perspective, phase


def _ratio(num: int | None, den: int | None) -> float | None:
    if num is None or den in (None, 0):
        return None
    return round(num / den * 100.0, 1)


def _derive(counter: Counter, evidence_events: int) -> dict[str, Any]:
    if evidence_events <= 0:
        return {}
    out: dict[str, Any] = dict(counter)
    out["shots"] = sum(counter.get(EVENT_TO_METRIC.get(e, ""), 0) for e in SHOT_EVENTS)
    out["shots_on_target"] = counter.get("shots_on_target", 0) + counter.get("goals", 0)
    out["shot_efficiency"] = _ratio(counter.get("goals", 0), out["shots"])
    out["shot_on_target_rate"] = _ratio(out["shots_on_target"], out["shots"])
    duels = counter.get("duels_won", 0) + counter.get("duels_lost", 0)
    out["duel_win_rate"] = _ratio(counter.get("duels_won", 0), duels)
    out["transition_involvement"] = (
        counter.get("counterattacks", 0) + counter.get("defensive_recoveries", 0)
        + counter.get("fast_recovery", 0) + counter.get("late_recovery", 0)
    )
    if counter.get("saves", 0) or counter.get("goals_against", 0):
        received = counter.get("saves", 0) + counter.get("goals_against", 0)
        out["shots_on_goal_received"] = received
        out["save_efficiency"] = _ratio(counter.get("saves", 0), received)
    return out


def _counter_for(events) -> Counter:
    c = Counter()
    for event in events:
        metric = EVENT_TO_METRIC.get(getattr(event, "event_type", ""))
        if metric:
            c[metric] += 1
        if getattr(event, "event_type", "") == "turnover":
            note = (getattr(event, "note", "") or "").lower()
            if "pressure" in note:
                c["turnovers_under_pressure"] += 1
    return c


def build_match_statistics(match) -> dict[str, Any]:
    """Return a complete evidence-aware match statistics payload."""
    events = list(getattr(match, "events", []) or [])
    confirmed = [
        e for e in events
        if (getattr(e, "confidence", "") or "").upper() in {"CONFIRMED", "HIGH", "VERIFIED", "OFFICIAL"}
        or (getattr(e, "source", "") or "").lower() == "manual"
    ]
    trusted = confirmed or events

    perspectives: dict[str, list] = defaultdict(list)
    phases = Counter()
    sources = Counter()
    for event in trusted:
        perspective, phase = _event_context(event)
        perspectives[perspective].append(event)
        phases[phase] += 1
        sources[(getattr(event, "source", "") or "unknown").lower()] += 1

    own_events = perspectives.get("for", [])
    against_events = perspectives.get("against", [])
    own_values = _derive(_counter_for(own_events), len(own_events))
    against_values = _derive(_counter_for(against_events), len(against_events))

    player_rows = []
    for player in list(getattr(getattr(match, "team", None), "players", []) or []):
        pevents = [e for e in own_events if getattr(e, "player_id", None) == player.id]
        values = _derive(_counter_for(pevents), len(pevents))
        player_rows.append({
            "id": player.id, "name": player.name, "cap_number": player.cap_number,
            "role": player.primary_role, "events": len(pevents), "values": values,
            "coverage": "tagged" if pevents else "missing",
        })
    player_rows.sort(key=lambda r: (-r["events"], r["name"]))

    automatic = [e for e in events if (getattr(e, "source", "") or "").lower() not in {"manual", "official"}]
    coverage = {
        "event_rows": len(events), "trusted_event_rows": len(trusted), "confirmed_rows": len(confirmed),
        "automatic_rows": len(automatic),
        "player_rows_with_evidence": sum(bool(r["events"]) for r in player_rows),
        "player_rows_total": len(player_rows),
        "level": "complete_tagging" if events and len(confirmed) == len(events) else ("partial_tagging" if events else "no_event_evidence"),
        "note": (
            "Les statistiques chiffrées proviennent uniquement des événements enregistrés/validés. "
            "Une case vide signifie que la donnée n'est pas encore prouvée, pas qu'elle vaut zéro."
        ),
    }

    return {
        "catalog": METRIC_CATALOG, "for": own_values, "against": against_values,
        "players": player_rows, "phases": dict(phases), "sources": dict(sources), "coverage": coverage,
    }


def reference_player_stat_payload(row) -> dict[str, Any]:
    """Normalize every currently supported official-library player field."""
    shots = getattr(row, "shots", None)
    goals = getattr(row, "goals", None)
    return {
        "goals": goals, "shots": shots, "shot_efficiency": _ratio(goals, shots),
        "assists": getattr(row, "assists", None), "steals": getattr(row, "steals", None),
        "exclusions": getattr(row, "exclusions", None), "saves": getattr(row, "saves", None),
        "source_quality": getattr(row, "source_quality", "") or "unknown",
        "note": getattr(row, "note", "") or "",
    }
