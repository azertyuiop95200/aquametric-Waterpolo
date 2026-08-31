"""Match-level statistics for AquaMetric.

This module exposes the complete match/scouting metric catalogue while preserving an
evidence-first rule: a missing measurement is never converted to zero. Verified/tagged
Event rows feed counters and derived rates. Metrics that require richer tracking remain
visible in the UI as unavailable until evidence exists.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

SHOT_EVENTS = {"goal", "shot_on_target", "shot_off_target", "shot_blocked"}

METRIC_CATALOG = (
    ("attack", "Attaque & finition", (
        ("goals", "Buts"), ("shots", "Tirs"), ("shot_efficiency", "Efficacité tir"),
        ("shots_on_target", "Tirs cadrés"), ("shots_off_target", "Tirs non cadrés"),
        ("blocked_shots", "Tirs bloqués"), ("shot_on_target_rate", "% cadrés"),
        ("assists", "Passes décisives"), ("key_passes", "Passes clés"),
        ("actions_created", "Actions créées"), ("exclusions_earned", "Exclusions provoquées"),
        ("penalties_earned", "Penalties provoqués"), ("penalties_scored", "Penalties marqués"),
    )),
    ("possession", "Possession & décision", (
        ("possessions", "Possessions"), ("passes_attempted", "Passes tentées"),
        ("passes_complete", "Passes réussies"), ("pass_completion_rate", "% passes réussies"),
        ("bad_passes", "Mauvaises passes"), ("turnovers", "Pertes de balle"),
        ("turnovers_under_pressure", "Pertes sous pression"), ("touches", "Ballons touchés"),
        ("centre_entries", "Entrées de balle en pointe"), ("centre_touches", "Ballons touchés en pointe"),
        ("decision_errors", "Erreurs de décision"),
    )),
    ("centre_duels", "Pointe & duels", (
        ("centre_touches", "Touches pointe"), ("centre_shots", "Tirs depuis la pointe"),
        ("duels_won", "Duels gagnés"), ("duels_lost", "Duels perdus"),
        ("duel_win_rate", "% duels gagnés"), ("position_wins", "Positions gagnées"),
        ("position_losses", "Positions perdues"),
    )),
    ("defence", "Défense", (
        ("steals", "Interceptions / steals"), ("blocks", "Contres"),
        ("recoveries", "Récupérations"), ("shot_contests", "Tirs contestés"),
        ("help_rotations", "Aides / rotations"), ("fouls", "Fautes"),
        ("exclusions_committed", "Exclusions concédées"),
    )),
    ("transition", "Transition", (
        ("counterattacks", "Contre-attaques"), ("counterattack_shots", "Tirs en contre-attaque"),
        ("counterattack_goals", "Buts en contre-attaque"), ("defensive_recoveries", "Replis"),
        ("fast_recovery", "Replis rapides"), ("late_recovery", "Replis tardifs"),
        ("transition_involvement", "Implication transition"),
    )),
    ("special", "Supériorité / infériorité", (
        ("power_play_starts", "Supériorités"), ("power_play_shots", "Tirs en supériorité"),
        ("power_play_goals", "Buts en supériorité"), ("power_play_conversion", "% supériorité"),
        ("penalty_kill_starts", "Infériorités"), ("penalty_kill_stops", "Infériorités défendues"),
        ("penalty_kill_stop_rate", "% stops 5v6"), ("penalties_earned", "Penalties provoqués"),
        ("penalties_committed", "Penalties concédés"),
    )),
    ("goalkeeper", "Gardienne", (
        ("saves", "Arrêts"), ("shots_on_goal_received", "Tirs cadrés reçus"),
        ("goals_against", "Buts encaissés"), ("save_efficiency", "% arrêts"),
        ("distribution_attempted", "Relances tentées"), ("distribution_complete", "Relances réussies"),
        ("distribution_lost", "Relances perdues"), ("distribution_rate", "% relances réussies"),
        ("restart_time", "Temps moyen de relance"),
    )),
    ("physical", "Physique & nage", (
        ("sprints", "Sprints"), ("distance_m", "Distance nagée (m)"),
        ("avg_swim_speed", "Vitesse moyenne"), ("max_swim_speed", "Vitesse max"),
        ("high_intensity_distance_m", "Distance haute intensité"), ("work_rate", "Work rate"),
    )),
    ("shot_location", "Carte de tirs & préférences", (
        ("shot_pool_zones", "Zones de tir bassin"), ("shot_goal_zones", "Zones cage 3×3"),
        ("preferred_side", "Côté préféré"), ("best_shot_zone", "Zone la plus efficace"),
        ("weak_shot_zone", "Zone la moins efficace"), ("shot_map_sample", "Échantillon carte de tirs"),
    )),
)

EVENT_TO_METRIC = {
    "goal": "goals", "assist": "assists", "key_pass": "key_passes",
    "action_created": "actions_created", "pass_attempt": "passes_attempted",
    "pass_complete": "passes_complete", "bad_pass": "bad_passes", "turnover": "turnovers",
    "touch": "touches", "centre_entry": "centre_entries", "centre_touch": "centre_touches",
    "centre_shot": "centre_shots", "duel_won": "duels_won", "duel_lost": "duels_lost",
    "position_won": "position_wins", "position_lost": "position_losses",
    "shot_on_target": "shots_on_target", "shot_off_target": "shots_off_target",
    "shot_blocked": "blocked_shots", "shot_contest": "shot_contests",
    "block": "blocks", "interception": "steals", "recovery": "recoveries",
    "help_rotation": "help_rotations", "save": "saves", "goal_against": "goals_against",
    "foul": "fouls", "decision_error": "decision_errors",
    "exclusion_earned": "exclusions_earned", "exclusion_committed": "exclusions_committed",
    "penalty_earned": "penalties_earned", "penalty_committed": "penalties_committed",
    "penalty_scored": "penalties_scored", "power_play_start": "power_play_starts",
    "power_play_shot": "power_play_shots", "power_play_goal": "power_play_goals",
    "penalty_kill_start": "penalty_kill_starts", "penalty_kill_stop": "penalty_kill_stops",
    "counterattack_start": "counterattacks", "counterattack_shot": "counterattack_shots",
    "counterattack_goal": "counterattack_goals", "defensive_recovery_start": "defensive_recoveries",
    "fast_recovery": "fast_recovery", "late_recovery": "late_recovery",
    "possession": "possessions", "sprint": "sprints", "distribution_attempt": "distribution_attempted",
    "distribution_complete": "distribution_complete", "distribution_lost": "distribution_lost",
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
    out["shots"] = sum(counter.get(EVENT_TO_METRIC.get(event_type, ""), 0) for event_type in SHOT_EVENTS)
    out["shots_on_target"] = counter.get("shots_on_target", 0) + counter.get("goals", 0)
    out["shot_efficiency"] = _ratio(counter.get("goals", 0), out["shots"])
    out["shot_on_target_rate"] = _ratio(out["shots_on_target"], out["shots"])

    attempted = counter.get("passes_attempted", 0)
    complete = counter.get("passes_complete", 0)
    if attempted or complete:
        # Some legacy tagging records only completed/bad passes. Use an explicit
        # attempted count when it exists; otherwise do not invent the denominator.
        out["pass_completion_rate"] = _ratio(complete, attempted) if attempted else None

    duels = counter.get("duels_won", 0) + counter.get("duels_lost", 0)
    if duels:
        out["duel_win_rate"] = _ratio(counter.get("duels_won", 0), duels)

    out["transition_involvement"] = (
        counter.get("counterattacks", 0) + counter.get("defensive_recoveries", 0)
        + counter.get("fast_recovery", 0) + counter.get("late_recovery", 0)
    )

    pp = counter.get("power_play_starts", 0)
    if pp:
        out["power_play_conversion"] = _ratio(counter.get("power_play_goals", 0), pp)
    pk = counter.get("penalty_kill_starts", 0)
    if pk:
        out["penalty_kill_stop_rate"] = _ratio(counter.get("penalty_kill_stops", 0), pk)

    saves = counter.get("saves", 0)
    goals_against = counter.get("goals_against", 0)
    if saves or goals_against:
        received = saves + goals_against
        out["shots_on_goal_received"] = received
        out["save_efficiency"] = _ratio(saves, received)
    dist_attempted = counter.get("distribution_attempted", 0)
    if dist_attempted:
        out["distribution_rate"] = _ratio(counter.get("distribution_complete", 0), dist_attempted)
    return out


def _counter_for(events) -> Counter:
    counter = Counter()
    for event in events:
        event_type = getattr(event, "event_type", "")
        metric = EVENT_TO_METRIC.get(event_type)
        if metric:
            counter[metric] += 1
        if event_type == "turnover":
            note = (getattr(event, "note", "") or "").lower()
            if "pressure" in note:
                counter["turnovers_under_pressure"] += 1
    return counter


def build_match_statistics(match) -> dict[str, Any]:
    """Return a complete evidence-aware match statistics payload."""
    events = list(getattr(match, "events", []) or [])
    confirmed = [
        event for event in events
        if (getattr(event, "confidence", "") or "").upper() in {"CONFIRMED", "HIGH", "VERIFIED", "OFFICIAL"}
        or (getattr(event, "source", "") or "").lower() == "manual"
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
        player_events = [event for event in own_events if getattr(event, "player_id", None) == player.id]
        values = _derive(_counter_for(player_events), len(player_events))
        player_rows.append({
            "id": player.id,
            "name": player.name,
            "cap_number": player.cap_number,
            "role": player.primary_role,
            "events": len(player_events),
            "values": values,
            "coverage": "tagged" if player_events else "missing",
        })
    player_rows.sort(key=lambda row: (-row["events"], row["name"]))

    automatic = [event for event in events if (getattr(event, "source", "") or "").lower() not in {"manual", "official"}]
    coverage = {
        "event_rows": len(events),
        "trusted_event_rows": len(trusted),
        "confirmed_rows": len(confirmed),
        "automatic_rows": len(automatic),
        "player_rows_with_evidence": sum(bool(row["events"]) for row in player_rows),
        "player_rows_total": len(player_rows),
        "level": "complete_tagging" if events and len(confirmed) == len(events) else ("partial_tagging" if events else "no_event_evidence"),
        "note": (
            "Les statistiques chiffrées proviennent uniquement des événements enregistrés/validés. "
            "Une case vide signifie que la donnée n'est pas encore prouvée, pas qu'elle vaut zéro."
        ),
    }

    return {
        "catalog": METRIC_CATALOG,
        "for": own_values,
        "against": against_values,
        "players": player_rows,
        "phases": dict(phases),
        "sources": dict(sources),
        "coverage": coverage,
    }


def reference_player_stat_payload(row) -> dict[str, Any]:
    """Normalize every currently supported official-library player field."""
    shots = getattr(row, "shots", None)
    goals = getattr(row, "goals", None)
    return {
        "goals": goals,
        "shots": shots,
        "shot_efficiency": _ratio(goals, shots),
        "assists": getattr(row, "assists", None),
        "steals": getattr(row, "steals", None),
        "exclusions": getattr(row, "exclusions", None),
        "saves": getattr(row, "saves", None),
        "source_quality": getattr(row, "source_quality", "") or "unknown",
        "note": getattr(row, "note", "") or "",
    }
