from __future__ import annotations

from collections import Counter, defaultdict
import re
from statistics import mean

from services.tactical_engine import build_phase_sequences

SHOT_EVENTS = {"goal", "shot_on_target", "shot_off_target", "shot_blocked"}
NEGATIVE_BALL = {"turnover", "bad_pass"}
PASS_EVENTS = {"pass_complete", "bad_pass"}

LOSS_REASON_LABELS = {
    "bad_pass": "Passe ratée",
    "centre_entry": "Entrée centre perdue",
    "counterattack": "Perte en contre-attaque",
    "offensive_foul": "Faute offensive",
    "shot_clock": "Fin de possession / 30 s",
    "steal": "Ballon volé",
    "handling": "Contrôle / ballon lâché",
    "other": "Autre perte",
}

POSITION_STANDARDS = {
    "goalkeeper": [
        "Position initiale par rapport à la balle et aux poteaux",
        "Lecture du bras tireur et déplacement avant le lâcher",
        "Organisation du bloc et communication centre-back",
        "Contrôle du rebond / deuxième ballon",
        "Temps arrêt ou récupération → première passe de transition",
    ],
    "centre": [
        "Premier contact, ligne d'eau intérieure et contrôle des hanches",
        "Seal / re-seal avant l'arrivée de la passe",
        "Qualité de séparation à T−1 puis disponibilité à T0",
        "Fautes/exclusions provoquées sans perdre la possession",
        "Repli immédiat après tir ou perte",
    ],
    "centre-back": [
        "Behind / 3/4 / front choisi selon position du ballon",
        "Contrôle du deuxième contact et capacité à re-front",
        "Timing de l'aide sans ouvrir l'aile haute",
        "Exclusions concédées et fautes utiles/inutiles",
        "Première accélération vers l'avant après récupération",
    ],
    "wing": [
        "Hauteur réelle en attaque, largeur et angle de tir court",
        "Scan centre → gardienne → aide avant réception",
        "Fixation avant one-more ou renversement",
        "Départ contre-attaque et occupation du couloir extérieur",
        "Retour sécurité côté faible après perte",
    ],
    "flat": [
        "Orientation du corps avant réception et vitesse de décision",
        "Qualité d'entrée au centre et refus du tir faible",
        "Drive utile / faux drive pour déplacer le drop",
        "Renversement après fixation",
        "Bascule attaque → sécurité au changement de possession",
    ],
    "point": [
        "Double scan avant réception et lecture de la gardienne",
        "Rythme imposé à la circulation de balle",
        "Fixation axiale avant transfert",
        "Gestion de fin de possession et qualité du tir lointain",
        "Responsabilité de safety sur transition négative",
    ],
    "field": [
        "Lecture avant réception",
        "Qualité technique sous pression",
        "Décision après fixation",
        "Transition positive et négative",
        "Discipline et conservation du ballon",
    ],
}


def _meta(event):
    meta = getattr(event, "context_meta", None)
    return {
        "perspective": getattr(meta, "perspective", "for") if meta else "for",
        "phase_tag": getattr(meta, "phase_tag", "auto") if meta else "auto",
        "quality_tag": getattr(meta, "quality_tag", "") if meta else "",
    }


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def _score(base, positive=0.0, negative=0.0):
    return round(max(25.0, min(95.0, base + positive - negative)), 1)


def _dimension(label, score, evidence, available=True):
    return {"label": label, "score": score if available else None, "evidence": evidence, "available": bool(available)}


def _role_family(role: str) -> str:
    text = (role or "").lower()
    if "goal" in text or "gard" in text:
        return "goalkeeper"
    if "centre back" in text or "center back" in text or "centre-back" in text:
        return "centre-back"
    if "centre" in text or "center" in text or "2m" in text:
        return "centre"
    if "wing" in text or "aile" in text:
        return "wing"
    if "point" in text or "pointe" in text or "top" in text:
        return "point"
    if "flat" in text or "driver" in text:
        return "flat"
    return "field"


def _loss_reason(event) -> str:
    note = (getattr(event, "note", "") or "").lower()
    quality = (_meta(event).get("quality_tag") or "").lower()
    text = f"{note} {quality}"
    if getattr(event, "event_type", "") == "bad_pass":
        if any(k in text for k in ("centre", "center", "2m", "entry")):
            return "centre_entry"
        return "bad_pass"
    if any(k in text for k in ("counter", "transition", "fast break", "contre")):
        return "counterattack"
    if any(k in text for k in ("offensive foul", "faute offensive", "push off")):
        return "offensive_foul"
    if any(k in text for k in ("shot clock", "30s", "30 s", "possession clock")):
        return "shot_clock"
    if any(k in text for k in ("steal", "stolen", "interception adverse", "ballon vol")):
        return "steal"
    if any(k in text for k in ("handling", "drop ball", "control", "contrôle", "lâché", "lache")):
        return "handling"
    return "other"


def _loss_breakdown(events) -> dict:
    losses = [e for e in events if getattr(e, "event_type", "") in NEGATIVE_BALL]
    c = Counter(_loss_reason(e) for e in losses)
    total = len(losses)
    rows = []
    for key, count in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
        rows.append({
            "key": key,
            "label": LOSS_REASON_LABELS.get(key, key),
            "count": count,
            "share": _pct(count, total),
        })
    return {"total": total, "rows": rows}


def _numeric_note_values(events, key: str) -> list[float]:
    values = []
    pattern = re.compile(rf"(?:^|[; ,]){re.escape(key)}\s*[=:]\s*(\d+(?:\.\d+)?)", re.I)
    for e in events:
        m = pattern.search(getattr(e, "note", "") or "")
        if m:
            try:
                values.append(float(m.group(1)))
            except ValueError:
                pass
    return values


def _timed_after(events, start_type: str, target_types: set[str], max_window: float = 20.0) -> list[float]:
    ordered = sorted(events, key=lambda e: float(getattr(e, "second", 0) or 0))
    out = []
    for idx, e in enumerate(ordered):
        if e.event_type != start_type:
            continue
        start = float(e.second or 0)
        perspective = _meta(e)["perspective"]
        for candidate in ordered[idx + 1:]:
            delta = float(candidate.second or 0) - start
            if delta < 0:
                continue
            if delta > max_window:
                break
            if _meta(candidate)["perspective"] == perspective and candidate.event_type in target_types:
                out.append(round(delta, 2))
                break
    return out


def _transition_timing(events) -> dict:
    d2o_first_pass = _timed_after(events, "counterattack_start", {"pass_complete", "assist", "key_pass"}, 12)
    d2o_shot = _timed_after(events, "counterattack_start", SHOT_EVENTS, 20)
    o2d_shape = _timed_after(events, "defensive_recovery_start", {"fast_recovery", "late_recovery", "recovery", "interception", "block"}, 15)
    measured = {
        "sprint_5m_s": _numeric_note_values(events, "sprint_5m_s"),
        "sprint_10m_s": _numeric_note_values(events, "sprint_10m_s"),
        "max_swim_speed_mps": _numeric_note_values(events, "max_swim_speed_mps"),
        "shot_speed_kmh": _numeric_note_values(events, "shot_speed_kmh"),
        "release_time_s": _numeric_note_values(events, "release_time_s"),
    }
    def avg(xs):
        return round(mean(xs), 2) if xs else None
    return {
        "defence_to_attack_first_pass_s": avg(d2o_first_pass),
        "defence_to_attack_shot_s": avg(d2o_shot),
        "attack_to_defence_shape_s": avg(o2d_shape),
        "samples": {
            "d2o_first_pass": len(d2o_first_pass),
            "d2o_shot": len(d2o_shot),
            "o2d_shape": len(o2d_shape),
        },
        "measured": {key: {"avg": avg(vals), "max": round(max(vals), 2) if vals else None, "samples": len(vals)} for key, vals in measured.items()},
        "policy": "Les vitesses absolues ne sont affichées que si une valeur mesurée est explicitement taguée dans la note de l'événement.",
    }


def _statboard(events) -> dict:
    c = Counter(e.event_type for e in events)
    shots = sum(c[x] for x in SHOT_EVENTS)
    on_frame = c["goal"] + c["shot_on_target"]
    passes_ok = c["pass_complete"] + c["assist"]
    passes_failed = c["bad_pass"]
    pass_attempts = passes_ok + passes_failed
    losses = c["turnover"] + c["bad_pass"]
    return {
        "shots": shots,
        "goals": c["goal"],
        "shots_on_target": on_frame,
        "shots_off_target": c["shot_off_target"],
        "shots_blocked": c["shot_blocked"],
        "shot_accuracy_pct": _pct(on_frame, shots),
        "scoring_efficiency_pct": _pct(c["goal"], shots),
        "passes_completed": passes_ok,
        "passes_failed": passes_failed,
        "pass_attempts_tagged": pass_attempts,
        "pass_completion_pct": _pct(passes_ok, pass_attempts),
        "turnovers": losses,
        "turnovers_per_100_tagged_passes": round(losses * 100 / pass_attempts, 1) if pass_attempts else None,
        "assists": c["assist"],
        "key_passes": c["key_pass"],
        "actions_created": c["action_created"],
        "exclusions_earned": c["exclusion_earned"],
        "exclusions_committed": c["exclusion_committed"],
        "interceptions": c["interception"],
        "recoveries": c["recovery"],
        "blocks": c["block"],
        "saves": c["save"],
        "duels_won": c["duel_won"],
        "duels_lost": c["duel_lost"],
    }


def team_performance_report(match) -> dict:
    events = sorted(list(match.events or []), key=lambda e: e.second)
    tagged = [(e, _meta(e)) for e in events]
    own_events = [e for e, m in tagged if m["perspective"] != "against"]
    opp_events = [e for e, m in tagged if m["perspective"] == "against"]
    own = Counter(e.event_type for e in own_events)
    opp = Counter(e.event_type for e in opp_events)
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
        dims.append(_dimension("Attack", _score(50, conv * 35 + min(12, creation * 1.6), min(16, losses * 2.0)), f"{own_goals}/{own_shots} tirs tagués · {creation} créations · {losses} pertes"))
    else:
        dims.append(_dimension("Attack", None, "Need at least 3 tagged shots or creation actions.", False))

    technique_volume = passes + own_shots + losses
    if technique_volume >= 5:
        target = own["goal"] + own["shot_on_target"]
        accuracy = target / max(1, own_shots)
        security = passes / max(1, passes + losses)
        dims.append(_dimension("Technical execution", _score(50, accuracy * 18 + security * 18, min(14, losses * 1.6)), f"{passes} passes complètes/assists · {_pct(target, own_shots) or 0}% cadrés+but · {losses} pertes"))
    else:
        dims.append(_dimension("Technical execution", None, "Insufficient pass/shot execution tags.", False))

    defensive_volume = ball_wins + blocks + opp_shots + own["duel_won"] + own["duel_lost"]
    if defensive_volume >= 4:
        stop_signal = ball_wins * 3 + blocks * 2 + own["duel_won"] * 2
        conceded_penalty = opp_goals * 3 + own["duel_lost"] * 1.5
        dims.append(_dimension("Defence", _score(50, min(25, stop_signal), min(25, conceded_penalty)), f"{ball_wins} gains · {blocks} blocs · {own['duel_won']} duels gagnés · {opp_goals} buts adverses tagués"))
    else:
        dims.append(_dimension("Defence", None, "Insufficient defensive/opponent-context tags.", False))

    explicit_context = sum(1 for _, m in tagged if m["phase_tag"] not in {"", "auto"}) + len(power) + len(kill) + len(counter)
    if explicit_context >= 3:
        productive = sum(1 for s in sequences if s["shots_for"] or s["goals_for"] or s["blocks_for"])
        failed = sum(1 for s in sequences if s["losses_for"] or s["goals_against"])
        dims.append(_dimension("Tactical execution", _score(50, min(24, productive * 2.8), min(20, failed * 3.0)), f"{len(sequences)} séquences · {productive} productives · {failed} avec perte/encaissement"))
    else:
        dims.append(_dimension("Tactical execution", None, "Need more explicit phase tagging/tracking.", False))

    transition_volume = len(counter) + fast + late
    if transition_volume >= 3:
        dims.append(_dimension("Transition", _score(50, min(24, len(counter) * 2 + fast * 4), min(24, late * 4 + sum(s["losses_for"] for s in counter) * 2)), f"{len(counter)} contre-attaques · {fast} replis rapides · {late} replis tardifs"))
    else:
        dims.append(_dimension("Transition", None, "Insufficient transition/recovery tags.", False))

    if power:
        pp_goals = sum(s["goals_for"] for s in power)
        pp_shots = sum(1 for s in power if s["shots_for"] > 0)
        pp_losses = sum(s["losses_for"] for s in power)
        dims.append(_dimension("Zone+", _score(50, min(28, pp_goals * 7 + pp_shots * 2), min(20, pp_losses * 5)), f"{len(power)} séquences · {pp_goals} buts · {pp_shots} tirs créés · {pp_losses} pertes"))
    else:
        dims.append(_dimension("Zone+", None, "No explicit Zone+ sequence tagged.", False))

    if kill:
        conceded = sum(s["goals_against"] for s in kill)
        stops = max(0, len(kill) - conceded)
        dims.append(_dimension("Zone−", _score(50, min(28, stops * 5), min(28, conceded * 7)), f"{len(kill)} séquences · {stops} stops · {conceded} buts encaissés"))
    else:
        dims.append(_dimension("Zone−", None, "No explicit 5-on-6 sequence tagged.", False))

    discipline_volume = discipline_neg + own["exclusion_earned"] + own["penalty_earned"]
    if discipline_volume >= 2:
        positive = own["exclusion_earned"] * 2 + own["penalty_earned"] * 3
        dims.append(_dimension("Discipline / pressure", _score(55, min(15, positive), min(28, discipline_neg * 2.2)), f"{own['exclusion_earned']} exclusions provoquées · {own['exclusion_committed']} concédées · {own['penalty_committed']} penalties concédés"))
    else:
        dims.append(_dimension("Discipline / pressure", None, "Insufficient exclusion/foul evidence.", False))

    if opp_shots >= 3 and own["save"]:
        saves = own["save"]
        dims.append(_dimension("Goalkeeper / block unit", _score(45, min(38, 38 * saves / max(1, opp_shots)), min(15, opp_goals * 1.5)), f"{saves} arrêts · {blocks} blocs · {opp_shots} tirs adverses"))
    else:
        dims.append(_dimension("Goalkeeper / block unit", None, "Need goalkeeper saves plus opponent shot context.", False))

    available = [d for d in dims if d["available"]]
    overall = round(sum(d["score"] for d in available) / len(available), 1) if available else None
    confidence = min(1.0, len(events) / 45 * 0.55 + len(available) / len(dims) * 0.30 + min(1.0, explicit_context / 10) * 0.15)
    confidence = round(confidence, 2)
    confidence_label = "HIGH" if confidence >= .80 else "STRONG" if confidence >= .62 else "MODERATE" if confidence >= .38 else "PRELIMINARY"
    strengths = [d for d in sorted(available, key=lambda x: x["score"], reverse=True) if d["score"] >= 58][:3]
    reviews = [d for d in sorted(available, key=lambda x: x["score"]) if d["score"] <= 47][:3]

    own_board = _statboard(own_events)
    opp_board = _statboard(opp_events)
    return {
        "overall": overall,
        "confidence": confidence,
        "confidence_label": confidence_label,
        "event_count": len(events),
        "dimensions": dims,
        "strengths": strengths,
        "reviews": reviews,
        "statboard": own_board,
        "opponent_statboard": opp_board,
        "loss_breakdown": _loss_breakdown(own_events),
        "transition_timing": _transition_timing(own_events),
        "raw": {"own": dict(own), "opponent": dict(opp), "sequences": len(sequences), "shots_for": own_shots, "shots_against": opp_shots},
        "methodology": {
            "measured": "Comptages issus des événements validés et valeurs numériques explicitement taguées.",
            "derived": "Pourcentages calculés uniquement lorsque le dénominateur est disponible.",
            "qualitative": "Interprétation coach séparée des mesures brutes.",
        },
    }


def player_match_breakdown(events, evaluation: dict, role: str = "") -> dict:
    events = list(events or [])
    c = Counter(e.event_type for e in events)
    phase = Counter()
    for e in events:
        tag = _meta(e)["phase_tag"]
        if tag and tag != "auto":
            phase[tag] += 1

    shots = sum(c[x] for x in SHOT_EVENTS)
    target = c["goal"] + c["shot_on_target"]
    passes_ok = c["pass_complete"] + c["assist"]
    passes_failed = c["bad_pass"]
    pass_attempts = passes_ok + passes_failed
    losses = c["turnover"] + c["bad_pass"]
    positive_def = c["interception"] + c["recovery"] + c["block"] + c["duel_won"]
    creation = c["assist"] + c["key_pass"] + c["action_created"] + c["exclusion_earned"] + c["penalty_earned"]

    cards = [
        {"label": "Création", "value": creation, "detail": f"{c['assist']} assists · {c['key_pass']} passes clés · {c['exclusion_earned']} exclusions provoquées"},
        {"label": "Tir", "value": f"{c['goal']}/{shots}" if shots else "—", "detail": f"{_pct(target, shots) if shots else '—'}% cadrés+but · {_pct(c['goal'], shots) if shots else '—'}% efficacité"},
        {"label": "Passe", "value": f"{passes_ok}/{pass_attempts}" if pass_attempts else "—", "detail": f"{_pct(passes_ok, pass_attempts) if pass_attempts else '—'}% réussies · {passes_failed} ratées"},
        {"label": "Sécurité ballon", "value": losses, "detail": f"{c['turnover']} turnovers · {c['bad_pass']} mauvaises passes"},
        {"label": "Impact défensif", "value": positive_def, "detail": f"{c['interception']} interceptions · {c['block']} blocs · {c['duel_won']} duels gagnés"},
    ]
    family = _role_family(role)
    return {
        "cards": cards,
        "statboard": _statboard(events),
        "loss_breakdown": _loss_breakdown(events),
        "transition_timing": _transition_timing(events),
        "position_family": family,
        "qualitative_checklist": POSITION_STANDARDS[family],
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
