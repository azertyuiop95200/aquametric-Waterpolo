from collections import Counter

# AquaMetric rating-v2 is deliberately evidence-bound. It scores only dimensions
# supported by tagged match actions. Physical output stays unavailable until a
# calibrated tracking layer measures speed/distance/repeated effort.
DIMENSION_DELTAS = {
    "goal": {"attack": 7, "decision": 2, "technique": 4, "impact": 7},
    "assist": {"attack": 5, "decision": 5, "tactics": 2, "technique": 2, "impact": 4},
    "key_pass": {"attack": 4, "decision": 4, "tactics": 2, "technique": 2, "impact": 2},
    "action_created": {"attack": 4, "decision": 3, "tactics": 3, "impact": 2},
    "touch": {"technique": 0.3},
    "centre_touch": {"attack": 1.5, "tactics": 1.5, "technique": 1},
    "duel_won": {"defence": 3, "technique": 2, "impact": 2},
    "duel_lost": {"defence": -2, "technique": -1.5},
    "pass_complete": {"decision": 0.5, "technique": 0.5},
    "shot_on_target": {"attack": 1.5, "technique": 1},
    "shot_off_target": {"attack": -1, "decision": -1, "technique": -1},
    "shot_blocked": {"attack": -0.5, "decision": -0.5},
    "block": {"defence": 5, "tactics": 2, "impact": 4},
    "interception": {"defence": 5, "decision": 2, "transition": 4, "impact": 4},
    "recovery": {"defence": 3, "transition": 2, "impact": 2},
    "save": {"defence": 4, "decision": 1.5, "technique": 3, "impact": 4},
    "bad_pass": {"attack": -1, "decision": -3, "technique": -2, "impact": -1},
    "turnover": {"attack": -2, "decision": -4, "transition": -2, "impact": -2},
    "foul": {"defence": -0.5, "discipline": -2},
    "exclusion": {"defence": -1, "discipline": -4, "impact": -1},
    "exclusion_earned": {"attack": 3, "tactics": 2, "impact": 3},
    "exclusion_committed": {"defence": -1.5, "discipline": -5, "impact": -2},
    "penalty_earned": {"attack": 4, "decision": 2, "impact": 4},
    "penalty_committed": {"defence": -2, "discipline": -6, "impact": -3},
    "power_play_start": {"tactics": 0.5},
    "penalty_kill_start": {"tactics": 0.5, "defence": 0.5},
    "counterattack_start": {"transition": 0.5, "tactics": 0.5},
    "defensive_recovery_start": {"transition": 0.5, "tactics": 0.5},
    "fast_recovery": {"defence": 2, "transition": 4, "decision": 1.5, "impact": 2},
    "late_recovery": {"defence": -2, "transition": -4, "decision": -1.5, "impact": -1},
}

NEGATIVE_EVENTS = {"bad_pass", "turnover", "foul", "exclusion", "exclusion_committed", "penalty_committed", "duel_lost", "late_recovery", "shot_off_target"}
DIMENSIONS = ("attack", "defence", "decision", "tactics", "transition", "discipline", "technique", "impact")


def _clamp(value, low=25.0, high=95.0):
    return round(max(low, min(high, value)), 1)


def _role_weights(role: str):
    r = (role or "").lower()
    if "goal" in r or "keeper" in r or "gard" in r:
        return {"attack": .03, "defence": .24, "decision": .16, "tactics": .15, "transition": .08, "discipline": .08, "technique": .16, "impact": .10}
    if "centre" in r or "center" in r:
        return {"attack": .17, "defence": .15, "decision": .12, "tactics": .15, "transition": .08, "discipline": .08, "technique": .13, "impact": .12}
    return {"attack": .16, "defence": .15, "decision": .15, "tactics": .14, "transition": .11, "discipline": .08, "technique": .11, "impact": .10}


def build_detailed_evaluation(events, role: str = "") -> dict:
    events = list(events or [])
    counts = Counter(e.event_type for e in events)
    raw = {d: 0.0 for d in DIMENSIONS}
    context_tags = Counter()
    for event in events:
        for dimension, delta in DIMENSION_DELTAS.get(event.event_type, {}).items():
            raw[dimension] += delta
        meta = getattr(event, "context_meta", None)
        phase = getattr(meta, "phase_tag", "") if meta else ""
        if phase and phase != "auto":
            context_tags[phase] += 1
            raw["tactics"] += 0.25

    # Diminish very large counting-volume effects while retaining action direction.
    scores = {}
    for d in DIMENSIONS:
        delta = raw[d]
        adjusted = (abs(delta) ** 0.82) * (1 if delta >= 0 else -1)
        scores[d] = _clamp(50 + adjusted * 2.15)

    n = len(events)
    distinct = len(counts)
    confidence_score = round(min(1.0, (n / 18) * .72 + (distinct / 9) * .28), 2) if n else 0.0
    if n == 0:
        confidence_label = "INSUFFICIENT DATA"
    elif confidence_score < .35:
        confidence_label = "LOW SAMPLE"
    elif confidence_score < .68:
        confidence_label = "MODERATE"
    else:
        confidence_label = "HIGH"

    weights = _role_weights(role)
    overall = round(sum(scores[d] * weights[d] for d in DIMENSIONS), 1) if n else None

    ranked = sorted(DIMENSIONS, key=lambda d: scores[d], reverse=True)
    strengths = []
    for d in ranked:
        if scores[d] >= 54 and raw[d] > 0:
            strengths.append(f"{d.replace('_', ' ').title()} supported by tagged actions ({scores[d]}/100).")
        if len(strengths) == 3:
            break

    negatives = sum(counts[x] for x in NEGATIVE_EVENTS)
    improvements = []
    for d in sorted(DIMENSIONS, key=lambda x: scores[x]):
        if scores[d] <= 47 and raw[d] < 0:
            improvements.append(f"Review {d.replace('_', ' ')} decisions around negative tagged events ({scores[d]}/100).")
        if len(improvements) == 3:
            break
    if negatives and not improvements:
        improvements.append(f"Review {negatives} negative tagged action(s) before prescribing a technical correction.")

    if not n:
        summary = "No verified player actions in this match yet; AquaMetric does not invent a performance score."
    else:
        summary = f"Evidence-based evaluation from {n} verified/tagged actions across {distinct} action types."
        if confidence_label in {"LOW SAMPLE", "MODERATE"}:
            summary += " Treat the score as provisional until more of the match is tagged or automatically attributed."

    return {
        "rated": bool(n),
        "overall": overall,
        "dimensions": scores,
        "physical": None,
        "physical_note": "Not rated: calibrated player tracking is required for swim speed, distance, repeated effort and fatigue.",
        "confidence_score": confidence_score,
        "confidence_label": confidence_label,
        "sample_size": n,
        "distinct_event_types": distinct,
        "event_counts": dict(counts),
        "phase_counts": dict(context_tags),
        "strengths": strengths,
        "improvements": improvements,
        "summary": summary,
        "engine_version": "rating-v2",
    }


def calculate_player_rating(events, role: str = ""):
    """Backward-compatible tuple used by existing routes, with rating-v2 detail in evidence.

    The first three return values keep V11 templates/tests compatible. New templates
    read ``evidence['__evaluation__']`` for the multi-dimensional breakdown.
    """
    evaluation = build_detailed_evaluation(events, role=role)
    evidence = dict(evaluation["event_counts"])
    evidence["__evaluation__"] = evaluation
    rating = evaluation["overall"] if evaluation["overall"] is not None else 50.0
    return rating, evaluation["confidence_label"], evidence
