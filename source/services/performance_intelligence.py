from __future__ import annotations

from collections import Counter

from services.tactical_engine import build_phase_sequences

SHOT_EVENTS = {"goal", "shot_on_target", "shot_off_target", "shot_blocked"}
NEGATIVE_BALL = {"turnover", "bad_pass"}


def _meta(event):
    meta = getattr(event, "context_meta", None)
    return {
        "perspective": getattr(meta, "perspective", "for") if meta else "for",
        "phase_tag": getattr(meta, "phase_tag", "auto") if meta else "auto",
    }


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def _score(base, positive=0.0, negative=0.0):
    return round(max(25.0, min(95.0, base + positive - negative)), 1)


def _dimension(label, score, evidence, available=True):
    return {"label": label, "score": score if available else None, "evidence": evidence, "available": bool(available)}


def team_performance_report(match) -> dict:
    events = sorted(list(match.events or []), key=lambda e: e.second)
    tagged = [(e, _meta(e)) for e in events]
    own = Counter(e.event_type for e, m in tagged if m["perspective"] != "against")
    opp = Counter(e.event_type for e, m in tagged if m["perspective"] == "against")
    sequences = build_phase_sequences(events)

    own_shots = sum(own[x] for x in SHOT_EVENTS)
    opp_shots = sum(opp[x] for x in SHOT_EVENTS)
    own_goals = own["goal"]
    opp_goals = opp["goal"]
    losses = sum(own[x] for x in NEGATIVE_BALL)
    passes = own["pass_complete"] + own["assist"]
    creation = own["assist"] + own["key_pass"] + own["action_created"] + own["exclusion_earned"]
    ball_wins = own["interception"] + own["recovery"]
    blocks = own["block"] + own["shot_blocked"]
    discipline_neg = own["foul"] + 2 * own["exclusion_committed"] + 3 * own["penalty_committed"]
    fast = own["fast_recovery"]
    late = own["late_recovery"]

    power = [s for s in sequences if s["phase"] == "power_play"]
    kill = [s for s in sequences if s["phase"] == "penalty_kill"]
    counter = [s for s in sequences if s["phase"] == "counterattack"]

    dims = []
    if own_shots >= 3 or creation >= 3:
        conv = own_goals / max(1, own_shots)
        dims.append(_dimension(
            "Attack",
            _score(50, conv * 35 + min(12, creation * 1.6), min(16, losses * 2.0)),
            f"{own_goals}/{own_shots} tagged shot outcomes · {creation} creation actions · {losses} ball losses",
        ))
    else:
        dims.append(_dimension("Attack", None, "Need at least 3 tagged shots or creation actions.", False))

    technique_volume = passes + own_shots + losses
    if technique_volume >= 5:
        target = own["goal"] + own["shot_on_target"]
        accuracy = target / max(1, own_shots)
        security = passes / max(1, passes + losses)
        dims.append(_dimension(
            "Technical execution",
            _score(50, accuracy * 18 + security * 18, min(14, losses * 1.6)),
            f"{passes} completed/assist pass tags · {_pct(target, own_shots) or 0}% target/goal share · {losses} losses",
        ))
    else:
        dims.append(_dimension("Technical execution", None, "Insufficient pass/shot execution tags.", False))

    defensive_volume = ball_wins + blocks + opp_shots + own["duel_won"] + own["duel_lost"]
    if defensive_volume >= 4:
        stop_signal = ball_wins * 3 + blocks * 2 + own["duel_won"] * 2
        conceded_penalty = opp_goals * 3 + own["duel_lost"] * 1.5
        dims.append(_dimension(
            "Defence",
            _score(50, min(25, stop_signal), min(25, conceded_penalty)),
            f"{ball_wins} ball wins · {blocks} blocks · {own['duel_won']} duels won · {opp_goals} opponent goals tagged",
        ))
    else:
        dims.append(_dimension("Defence", None, "Insufficient defensive/opponent-context tags.", False))

    explicit_context = sum(1 for _, m in tagged if m["phase_tag"] not in {"", "auto"}) + len(power) + len(kill) + len(counter)
    if explicit_context >= 3:
        productive = sum(1 for s in sequences if s["shots_for"] or s["goals_for"] or s["blocks_for"])
        failed = sum(1 for s in sequences if s["losses_for"] or s["goals_against"])
        dims.append(_dimension(
            "Tactical execution",
            _score(50, min(24, productive * 2.8), min(20, failed * 3.0)),
            f"{len(sequences)} explicit phase sequences · {productive} productive · {failed} with loss/concession",
        ))
    else:
        dims.append(_dimension("Tactical execution", None, "Need more explicit phase tagging/tracking.", False))

    transition_volume = len(counter) + fast + late
    if transition_volume >= 3:
        dims.append(_dimension(
            "Transition",
            _score(50, min(24, len(counter) * 2 + fast * 4), min(24, late * 4 + sum(s["losses_for"] for s in counter) * 2)),
            f"{len(counter)} counterattack sequences · {fast} fast recoveries · {late} late recoveries",
        ))
    else:
        dims.append(_dimension("Transition", None, "Insufficient transition/recovery tags.", False))

    if power:
        pp_goals = sum(s["goals_for"] for s in power)
        pp_shots = sum(1 for s in power if s["shots_for"] > 0)
        pp_losses = sum(s["losses_for"] for s in power)
        dims.append(_dimension(
            "Zone+",
            _score(50, min(28, pp_goals * 7 + pp_shots * 2), min(20, pp_losses * 5)),
            f"{len(power)} sequences · {pp_goals} goals · {pp_shots} created a shot · {pp_losses} losses",
        ))
    else:
        dims.append(_dimension("Zone+", None, "No explicit Zone+ sequence tagged.", False))

    if kill:
        conceded = sum(s["goals_against"] for s in kill)
        stops = max(0, len(kill) - conceded)
        dims.append(_dimension(
            "Zone−",
            _score(50, min(28, stops * 5), min(28, conceded * 7)),
            f"{len(kill)} sequences · {stops} non-goal outcomes · {conceded} goals conceded",
        ))
    else:
        dims.append(_dimension("Zone−", None, "No explicit 5-on-6 sequence tagged.", False))

    discipline_volume = discipline_neg + own["exclusion_earned"] + own["penalty_earned"]
    if discipline_volume >= 2:
        positive = own["exclusion_earned"] * 2 + own["penalty_earned"] * 3
        dims.append(_dimension(
            "Discipline / pressure",
            _score(55, min(15, positive), min(28, discipline_neg * 2.2)),
            f"{own['exclusion_earned']} exclusions earned · {own['exclusion_committed']} exclusions committed · {own['penalty_committed']} penalties committed",
        ))
    else:
        dims.append(_dimension("Discipline / pressure", None, "Insufficient exclusion/foul evidence.", False))

    if opp_shots >= 3 and own["save"]:
        saves = own["save"]
        dims.append(_dimension(
            "Goalkeeper / block unit",
            _score(45, min(38, 38 * saves / max(1, opp_shots)), min(15, opp_goals * 1.5)),
            f"{saves} saves · {blocks} blocks · {opp_shots} opponent shot outcomes",
        ))
    else:
        dims.append(_dimension("Goalkeeper / block unit", None, "Need goalkeeper saves plus opponent shot context.", False))

    available = [d for d in dims if d["available"]]
    overall = round(sum(d["score"] for d in available) / len(available), 1) if available else None
    confidence = min(1.0, len(events) / 45 * 0.55 + len(available) / len(dims) * 0.30 + min(1.0, explicit_context / 10) * 0.15)
    confidence = round(confidence, 2)
    confidence_label = "HIGH" if confidence >= .80 else "STRONG" if confidence >= .62 else "MODERATE" if confidence >= .38 else "PRELIMINARY"

    strengths = [d for d in sorted(available, key=lambda x: x["score"], reverse=True) if d["score"] >= 58][:3]
    reviews = [d for d in sorted(available, key=lambda x: x["score"]) if d["score"] <= 47][:3]

    return {
        "overall": overall,
        "confidence": confidence,
        "confidence_label": confidence_label,
        "event_count": len(events),
        "dimensions": dims,
        "strengths": strengths,
        "reviews": reviews,
        "raw": {
            "own": dict(own), "opponent": dict(opp), "sequences": len(sequences),
            "shots_for": own_shots, "shots_against": opp_shots,
        },
    }


def player_match_breakdown(events, evaluation: dict) -> dict:
    events = list(events or [])
    c = Counter(e.event_type for e in events)
    phase = Counter()
    for e in events:
        tag = _meta(e)["phase_tag"]
        if tag and tag != "auto":
            phase[tag] += 1

    shots = sum(c[x] for x in SHOT_EVENTS)
    target = c["goal"] + c["shot_on_target"]
    passes = c["pass_complete"] + c["assist"]
    losses = c["turnover"] + c["bad_pass"]
    positive_def = c["interception"] + c["recovery"] + c["block"] + c["duel_won"]
    creation = c["assist"] + c["key_pass"] + c["action_created"] + c["exclusion_earned"] + c["penalty_earned"]

    cards = [
        {"label": "Creation", "value": creation, "detail": f"{c['assist']} assists · {c['key_pass']} key passes · {c['exclusion_earned']} exclusions earned"},
        {"label": "Finishing", "value": f"{c['goal']}/{shots}" if shots else "—", "detail": f"{_pct(target, shots) if shots else '—'}% goal/on-target share"},
        {"label": "Ball security", "value": f"{passes}:{losses}", "detail": "completed/assist pass tags : bad pass/turnover tags"},
        {"label": "Defensive impact", "value": positive_def, "detail": f"{c['interception']} interceptions · {c['block']} blocks · {c['duel_won']} duels won"},
    ]
    return {
        "cards": cards,
        "phases": dict(phase),
        "event_counts": dict(c),
        "technical_score": evaluation.get("dimensions", {}).get("technique") if evaluation.get("rated") else None,
        "tactical_score": evaluation.get("dimensions", {}).get("tactics") if evaluation.get("rated") else None,
        "decision_score": evaluation.get("dimensions", {}).get("decision") if evaluation.get("rated") else None,
    }


def shot_preference_summary(shot_map: dict) -> dict:
    count = int(shot_map.get("count") or 0)
    if count < 3:
        return {"available": False, "count": count, "origin": "Not enough located shots", "target": "Not enough target-zone shots"}
    pool = shot_map.get("pool_bins") or []
    goal = shot_map.get("goal_bins") or []

    origin = "Mixed"
    if pool:
        cols = [sum(row[x] for row in pool) for x in range(len(pool[0]))]
        thirds = [sum(cols[:2]), sum(cols[2:4]), sum(cols[4:])]
        labels = ["Left-side origin", "Central origin", "Right-side origin"]
        if max(thirds) > 0:
            origin = labels[thirds.index(max(thirds))]

    target = "Target data incomplete"
    if goal and any(any(v for v in row) for row in goal):
        best = max(((v, y, x) for y, row in enumerate(goal) for x, v in enumerate(row)), key=lambda z: z[0])
        vertical = ["High", "Middle", "Low"][best[1]]
        horizontal = ["left", "centre", "right"][best[2]]
        target = f"{vertical} {horizontal} target"

    return {"available": True, "count": count, "origin": origin, "target": target, "confidence": shot_map.get("confidence", 0.0)}
