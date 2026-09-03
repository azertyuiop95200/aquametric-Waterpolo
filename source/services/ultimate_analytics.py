from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
import re

SHOT_EVENTS = {"goal", "shot_on_target", "shot_off_target", "shot_blocked"}
PASS_SUCCESS = {"pass_complete", "assist", "key_pass"}
PASS_FAILURE = {"bad_pass"}
LOSS_EVENTS = {"turnover", "bad_pass"}
DEFENSIVE_WINS = {"interception", "recovery", "block", "duel_won", "save"}
TERMINAL_EVENTS = SHOT_EVENTS | LOSS_EVENTS | {"exclusion_earned", "penalty_earned"}

TAG_RE = re.compile(r"(?:^|[\s;|])([a-z][a-z0-9_]{1,31})\s*=\s*([^\s;|]+)", re.I)
NUMERIC_TAGS = {"distance_m", "shot_speed_kmh", "release_time_s", "sprint_5m_s", "sprint_10m_s", "max_swim_speed_mps"}

LOSS_LABELS = {
    "bad_pass": "Passe ratée",
    "centre_entry": "Entrée centre",
    "counterattack": "Contre-attaque",
    "offensive_foul": "Faute offensive",
    "shot_clock": "Fin de possession",
    "steal": "Ballon volé",
    "handling": "Contrôle ballon",
    "decision": "Décision",
    "technical": "Technique",
    "pressure": "Pression adverse",
    "other": "Autre",
}

ZONE_LABELS = {
    "wing_left": "Aile gauche",
    "flat_left": "Flat gauche",
    "point": "Pointe",
    "flat_right": "Flat droite",
    "wing_right": "Aile droite",
    "centre": "Centre / 2 m",
    "post_left": "Poteau gauche",
    "post_right": "Poteau droit",
    "penalty": "Penalty",
    "transition": "Transition",
    "unknown": "Zone non renseignée",
}

PHASE_LABELS = {
    "even_attack": "6v6 attaque",
    "even_defence": "6v6 défense",
    "power_play": "6v5",
    "penalty_kill": "5v6",
    "counterattack": "Contre-attaque",
    "defensive_recovery": "Repli",
    "centre_play": "Jeu centre",
    "restart": "Remise en jeu",
    "auto": "Phase non renseignée",
}


def _pct(n: float, d: float):
    return round(100.0 * n / d, 1) if d else None


def _avg(values):
    values = [float(v) for v in values if v is not None]
    return round(mean(values), 2) if values else None


def _meta(event):
    meta = getattr(event, "context_meta", None)
    return {
        "perspective": getattr(meta, "perspective", "for") if meta else "for",
        "phase": getattr(meta, "phase_tag", "auto") if meta else "auto",
        "quality": getattr(meta, "quality_tag", "") if meta else "",
    }


def note_tags(event) -> dict:
    text = getattr(event, "note", "") or ""
    tags = {m.group(1).lower(): m.group(2).strip().lower() for m in TAG_RE.finditer(text)}
    for key in NUMERIC_TAGS:
        if key in tags:
            try:
                tags[key] = float(tags[key].replace(",", "."))
            except (TypeError, ValueError):
                tags.pop(key, None)
    return tags


def _events_for(events, perspective="for"):
    if perspective == "for":
        return [e for e in events if _meta(e)["perspective"] != "against"]
    if perspective == "against":
        return [e for e in events if _meta(e)["perspective"] == "against"]
    return list(events)


def _basic(events):
    c = Counter(getattr(e, "event_type", "") for e in events)
    shots = sum(c[k] for k in SHOT_EVENTS)
    on_target = c["goal"] + c["shot_on_target"]
    passes_ok = sum(c[k] for k in PASS_SUCCESS)
    passes_bad = sum(c[k] for k in PASS_FAILURE)
    pass_attempts = passes_ok + passes_bad
    losses = sum(c[k] for k in LOSS_EVENTS)
    return {
        "events": len(events),
        "goals": c["goal"],
        "shots": shots,
        "shots_on_target": on_target,
        "shots_off_target": c["shot_off_target"],
        "shots_blocked": c["shot_blocked"],
        "shot_accuracy_pct": _pct(on_target, shots),
        "scoring_efficiency_pct": _pct(c["goal"], shots),
        "passes_completed": passes_ok,
        "passes_failed": passes_bad,
        "pass_attempts": pass_attempts,
        "pass_completion_pct": _pct(passes_ok, pass_attempts),
        "turnovers": losses,
        "ball_wins": sum(c[k] for k in DEFENSIVE_WINS),
        "exclusions_earned": c["exclusion_earned"],
        "exclusions_committed": c["exclusion_committed"],
        "key_passes": c["key_pass"],
        "actions_created": c["action_created"],
        "duels_won": c["duel_won"],
        "duels_lost": c["duel_lost"],
        "saves": c["save"],
    }


def _loss_reason(event, tags=None):
    tags = tags or note_tags(event)
    if tags.get("cause") in LOSS_LABELS:
        return tags["cause"]
    text = f"{getattr(event, 'note', '') or ''} {_meta(event)['quality']}".lower()
    if getattr(event, "event_type", "") == "bad_pass":
        if any(k in text for k in ("centre", "center", "2m", "entry")):
            return "centre_entry"
        return "bad_pass"
    rules = [
        ("counterattack", ("counter", "transition", "contre")),
        ("offensive_foul", ("offensive foul", "faute offensive", "push off")),
        ("shot_clock", ("shot clock", "30s", "30 s")),
        ("steal", ("steal", "stolen", "ballon vol")),
        ("handling", ("handling", "drop ball", "contrôle", "control")),
    ]
    for key, words in rules:
        if any(word in text for word in words):
            return key
    return "other"


def loss_context_report(events):
    losses = [e for e in events if getattr(e, "event_type", "") in LOSS_EVENTS]
    reasons = Counter()
    zones = Counter()
    phases = Counter()
    pressures = Counter()
    decisions = Counter()
    rows = []
    for event in losses:
        tags = note_tags(event)
        reason = _loss_reason(event, tags)
        reasons[reason] += 1
        zones[tags.get("zone", "unknown")] += 1
        phases[_meta(event)["phase"] or "auto"] += 1
        pressures[tags.get("pressure", "unknown")] += 1
        decisions[tags.get("decision", "unknown")] += 1
    total = len(losses)
    for key, count in reasons.most_common():
        rows.append({"key": key, "label": LOSS_LABELS.get(key, key), "count": count, "share": _pct(count, total)})
    return {
        "total": total,
        "classified": sum(v for k, v in reasons.items() if k != "other"),
        "classified_pct": _pct(sum(v for k, v in reasons.items() if k != "other"), total),
        "reasons": rows,
        "zones": _counter_rows(zones, ZONE_LABELS, total),
        "phases": _counter_rows(phases, PHASE_LABELS, total),
        "pressures": _counter_rows(pressures, {}, total),
        "decisions": _counter_rows(decisions, {}, total),
    }


def _counter_rows(counter, labels, denominator=None):
    denominator = denominator if denominator is not None else sum(counter.values())
    return [
        {"key": key, "label": labels.get(key, key.replace("_", " ").title()), "count": count, "share": _pct(count, denominator)}
        for key, count in counter.most_common()
    ]


def shot_profile(events):
    shots = [e for e in events if getattr(e, "event_type", "") in SHOT_EVENTS]
    by_zone = defaultdict(list)
    by_type = defaultdict(list)
    by_hand = defaultdict(list)
    distance = []
    speeds = []
    releases = []
    for e in shots:
        tags = note_tags(e)
        by_zone[tags.get("zone", "unknown")].append(e)
        by_type[tags.get("shot_type", "unknown")].append(e)
        by_hand[tags.get("hand", "unknown")].append(e)
        if "distance_m" in tags:
            distance.append(tags["distance_m"])
        if "shot_speed_kmh" in tags:
            speeds.append(tags["shot_speed_kmh"])
        if "release_time_s" in tags:
            releases.append(tags["release_time_s"])

    def rows(groups, labels=None):
        labels = labels or {}
        out = []
        for key, seq in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            basic = _basic(seq)
            out.append({
                "key": key,
                "label": labels.get(key, key.replace("_", " ").title()),
                "shots": basic["shots"],
                "goals": basic["goals"],
                "on_target": basic["shots_on_target"],
                "accuracy_pct": basic["shot_accuracy_pct"],
                "efficiency_pct": basic["scoring_efficiency_pct"],
            })
        return out

    return {
        "total": len(shots),
        "located": sum(len(v) for k, v in by_zone.items() if k != "unknown"),
        "located_pct": _pct(sum(len(v) for k, v in by_zone.items() if k != "unknown"), len(shots)),
        "zones": rows(by_zone, ZONE_LABELS),
        "types": rows(by_type),
        "hands": rows(by_hand),
        "distance_m_avg": _avg(distance),
        "shot_speed_kmh_avg": _avg(speeds),
        "shot_speed_kmh_max": round(max(speeds), 1) if speeds else None,
        "release_time_s_avg": _avg(releases),
        "calibrated_speed_samples": len(speeds),
        "release_samples": len(releases),
    }


def pass_profile(events):
    passes = [e for e in events if getattr(e, "event_type", "") in PASS_SUCCESS | PASS_FAILURE]
    grouped = defaultdict(list)
    zones = defaultdict(list)
    pressures = defaultdict(list)
    decisions = defaultdict(list)
    for e in passes:
        tags = note_tags(e)
        grouped[tags.get("pass_type", "unknown")].append(e)
        zones[tags.get("zone", "unknown")].append(e)
        pressures[tags.get("pressure", "unknown")].append(e)
        decisions[tags.get("decision", "unknown")].append(e)

    def rows(groups, labels=None):
        labels = labels or {}
        out = []
        for key, seq in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            basic = _basic(seq)
            out.append({
                "key": key,
                "label": labels.get(key, key.replace("_", " ").title()),
                "attempts": basic["pass_attempts"],
                "completed": basic["passes_completed"],
                "failed": basic["passes_failed"],
                "completion_pct": basic["pass_completion_pct"],
            })
        return out

    return {
        "total": len(passes),
        "types": rows(grouped),
        "zones": rows(zones, ZONE_LABELS),
        "pressures": rows(pressures),
        "decisions": rows(decisions),
        "typed": sum(len(v) for k, v in grouped.items() if k != "unknown"),
        "typed_pct": _pct(sum(len(v) for k, v in grouped.items() if k != "unknown"), len(passes)),
    }


def decision_report(events):
    tagged = []
    for e in events:
        decision = note_tags(e).get("decision")
        if decision:
            tagged.append((decision, e))
    c = Counter(k for k, _ in tagged)
    total = len(tagged)
    success = Counter()
    for key, e in tagged:
        if e.event_type in {"goal", "shot_on_target", "pass_complete", "assist", "key_pass", "action_created", "exclusion_earned", "interception", "recovery", "block", "duel_won", "save"}:
            success[key] += 1
    return {
        "total": total,
        "good": c["good"],
        "neutral": c["neutral"],
        "poor": c["poor"],
        "good_pct": _pct(c["good"], total),
        "poor_pct": _pct(c["poor"], total),
        "rows": [
            {"key": key, "count": c[key], "share": _pct(c[key], total), "positive_outcome_pct": _pct(success[key], c[key])}
            for key in ("good", "neutral", "poor") if c[key]
        ],
    }


def pressure_report(events):
    grouped = defaultdict(list)
    for e in events:
        pressure = note_tags(e).get("pressure")
        if pressure:
            grouped[pressure].append(e)
    rows = []
    for key in ("low", "medium", "high"):
        seq = grouped.get(key, [])
        if not seq:
            continue
        b = _basic(seq)
        rows.append({
            "key": key,
            "events": len(seq),
            "pass_completion_pct": b["pass_completion_pct"],
            "shot_efficiency_pct": b["scoring_efficiency_pct"],
            "turnovers": b["turnovers"],
            "turnover_event_pct": _pct(b["turnovers"], len(seq)),
        })
    return {"rows": rows, "tagged": sum(len(v) for v in grouped.values())}


def phase_report(events):
    groups = defaultdict(list)
    for e in events:
        groups[_meta(e)["phase"] or "auto"].append(e)
    rows = []
    for key, seq in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        b = _basic(seq)
        rows.append({"key": key, "label": PHASE_LABELS.get(key, key.replace("_", " ").title()), **b})
    return rows


def period_report(events):
    groups = defaultdict(list)
    untagged = 0
    for e in events:
        period = note_tags(e).get("period")
        if period:
            groups[str(period).upper()].append(e)
        else:
            untagged += 1
    order = {"1": 1, "Q1": 1, "2": 2, "Q2": 2, "3": 3, "Q3": 3, "4": 4, "Q4": 4, "OT": 5, "SO": 6}
    rows = []
    for key, seq in sorted(groups.items(), key=lambda kv: (order.get(kv[0], 99), kv[0])):
        rows.append({"period": key, **_basic(seq)})
    return {"rows": rows, "tagged": sum(len(v) for v in groups.values()), "untagged": untagged, "coverage_pct": _pct(sum(len(v) for v in groups.values()), len(events))}


def possession_report(events):
    groups = defaultdict(list)
    candidates = [e for e in events if getattr(e, "event_type", "") in (SHOT_EVENTS | PASS_SUCCESS | PASS_FAILURE | LOSS_EVENTS | {"action_created", "exclusion_earned", "penalty_earned", "centre_touch"})]
    for e in candidates:
        pid = note_tags(e).get("possession") or note_tags(e).get("possession_id")
        if pid:
            groups[str(pid)].append(e)
    tagged_events = sum(len(v) for v in groups.values())
    if not groups:
        terminal = Counter(e.event_type for e in candidates if e.event_type in TERMINAL_EVENTS)
        return {
            "available": False,
            "mode": "terminal-action proxy",
            "possessions": None,
            "coverage_pct": 0.0,
            "terminal_actions": dict(terminal),
            "note": "Le nombre de possessions n'est pas inventé. Taguer possession=ID sur les événements pour obtenir les taux par possession.",
        }
    outcomes = Counter()
    durations = []
    pass_counts = []
    for _, seq in groups.items():
        seq = sorted(seq, key=lambda e: float(getattr(e, "second", 0) or 0))
        c = Counter(e.event_type for e in seq)
        if c["goal"]:
            outcome = "goal"
        elif sum(c[x] for x in {"shot_on_target", "shot_off_target", "shot_blocked"}):
            outcome = "shot_no_goal"
        elif sum(c[x] for x in LOSS_EVENTS):
            outcome = "turnover"
        elif c["exclusion_earned"] or c["penalty_earned"]:
            outcome = "advantage_earned"
        else:
            outcome = "open"
        outcomes[outcome] += 1
        if len(seq) >= 2:
            durations.append(float(seq[-1].second or 0) - float(seq[0].second or 0))
        pass_counts.append(sum(c[x] for x in PASS_SUCCESS | PASS_FAILURE))
    total = len(groups)
    return {
        "available": True,
        "mode": "explicit possession ids",
        "possessions": total,
        "coverage_pct": _pct(tagged_events, len(candidates)),
        "goals_per_possession_pct": _pct(outcomes["goal"], total),
        "shot_possessions_pct": _pct(outcomes["goal"] + outcomes["shot_no_goal"], total),
        "turnover_possessions_pct": _pct(outcomes["turnover"], total),
        "advantage_earned_pct": _pct(outcomes["advantage_earned"], total),
        "avg_observed_duration_s": _avg(durations),
        "avg_tagged_passes": _avg(pass_counts),
        "outcomes": _counter_rows(outcomes, {
            "goal": "But", "shot_no_goal": "Tir sans but", "turnover": "Perte", "advantage_earned": "Exclusion/penalty provoqué", "open": "Issue non taguée"
        }, total),
    }


def coverage_report(events):
    events = list(events)
    relevant = [e for e in events if getattr(e, "event_type", "") not in {"whistle", "power_play_start", "penalty_kill_start", "counterattack_start", "defensive_recovery_start"}]
    shots = [e for e in relevant if e.event_type in SHOT_EVENTS]
    passes = [e for e in relevant if e.event_type in PASS_SUCCESS | PASS_FAILURE]
    losses = [e for e in relevant if e.event_type in LOSS_EVENTS]

    def tag_cov(seq, key, allowed=None):
        if not seq:
            return None
        n = 0
        for e in seq:
            value = note_tags(e).get(key)
            if value and (allowed is None or value in allowed):
                n += 1
        return _pct(n, len(seq))

    components = {
        "player_attribution_pct": _pct(sum(1 for e in relevant if getattr(e, "player_id", None)), len(relevant)),
        "period_pct": tag_cov(relevant, "period"),
        "phase_pct": _pct(sum(1 for e in relevant if _meta(e)["phase"] not in {"", "auto"}), len(relevant)),
        "shot_zone_pct": tag_cov(shots, "zone"),
        "shot_type_pct": tag_cov(shots, "shot_type"),
        "pass_type_pct": tag_cov(passes, "pass_type"),
        "loss_cause_pct": tag_cov(losses, "cause"),
        "pressure_pct": tag_cov(relevant, "pressure"),
        "decision_pct": tag_cov(relevant, "decision"),
        "possession_pct": tag_cov(relevant, "possession") if relevant else None,
    }
    weights = {
        "player_attribution_pct": 1.2, "period_pct": 1.0, "phase_pct": 1.0,
        "shot_zone_pct": 1.2, "shot_type_pct": .7, "pass_type_pct": .8,
        "loss_cause_pct": 1.2, "pressure_pct": .8, "decision_pct": .9, "possession_pct": 1.2,
    }
    weighted = [(components[k], weights[k]) for k in components if components[k] is not None]
    score = round(sum(v * w for v, w in weighted) / sum(w for _, w in weighted), 1) if weighted else 0.0
    readiness = "ELITE READY" if score >= 85 else "STRONG" if score >= 70 else "USABLE" if score >= 50 else "BUILDING" if score >= 25 else "SPARSE"
    missing = sorted(
        ({"key": k, "coverage": v} for k, v in components.items() if v is not None and v < 70),
        key=lambda x: x["coverage"],
    )
    return {"score": score, "readiness": readiness, "components": components, "priority_gaps": missing[:5], "event_count": len(events)}


def qualitative_findings(events):
    b = _basic(events)
    losses = loss_context_report(events)
    shots = shot_profile(events)
    passes = pass_profile(events)
    pressure = pressure_report(events)
    decisions = decision_report(events)
    findings = []

    def add(tone, title, text, evidence):
        findings.append({"tone": tone, "title": title, "text": text, "evidence": evidence})

    if b["pass_attempts"] >= 10 and b["pass_completion_pct"] is not None:
        if b["pass_completion_pct"] < 78:
            add("warning", "Sécurité de passe prioritaire", "Revoir timing, distance et orientation avant d'attribuer toutes les pertes à l'exécution technique.", f"{b['passes_completed']}/{b['pass_attempts']} passes taguées réussies · {b['pass_completion_pct']}%")
        elif b["pass_completion_pct"] >= 90:
            add("positive", "Circulation sécurisée", "La conservation est forte dans l'échantillon ; vérifier maintenant si cette sécurité crée réellement du déplacement défensif et des tirs de qualité.", f"{b['pass_completion_pct']}% sur {b['pass_attempts']} passes taguées")

    if b["shots"] >= 8:
        if b["shot_accuracy_pct"] is not None and b["shot_accuracy_pct"] < 55:
            add("warning", "Sélection / cadrage du tir à revoir", "Comparer zone, pression, bras fort et position gardienne avant de prescrire uniquement du travail de finition.", f"{b['shots_on_target']}/{b['shots']} tirs cadrés ou buts · {b['shot_accuracy_pct']}%")
        if b["scoring_efficiency_pct"] is not None and b["scoring_efficiency_pct"] >= 45:
            add("positive", "Conversion offensive élevée", "Identifier les mécanismes qui créent ces tirs plutôt que de réduire la performance à l'adresse individuelle.", f"{b['goals']}/{b['shots']} · {b['scoring_efficiency_pct']}%")

    if losses["total"] >= 4:
        top = losses["reasons"][0] if losses["reasons"] else None
        if top and top["share"] is not None and top["share"] >= 35:
            add("warning", f"Cause dominante : {top['label']}", "Le plan de correction doit viser la cause dominante et son contexte, pas seulement le nombre brut de turnovers.", f"{top['count']}/{losses['total']} pertes · {top['share']}%")

    high = next((x for x in pressure["rows"] if x["key"] == "high"), None)
    low = next((x for x in pressure["rows"] if x["key"] == "low"), None)
    if high and low and high["events"] >= 4 and low["events"] >= 4 and high["pass_completion_pct"] is not None and low["pass_completion_pct"] is not None:
        gap = round(low["pass_completion_pct"] - high["pass_completion_pct"], 1)
        if gap >= 12:
            add("warning", "La pression dégrade la qualité de passe", "Travailler réception orientée, scan pré-réception et deuxième solution avant contact.", f"Écart faible→forte pression : {gap} points")

    if decisions["total"] >= 6 and decisions["poor_pct"] is not None and decisions["poor_pct"] >= 25:
        add("warning", "Décisions pauvres récurrentes", "Isoler les signaux disponibles à T−2/T−1 : aide, centre, gardienne, chrono et position de sécurité.", f"{decisions['poor']} décisions pauvres / {decisions['total']} taguées · {decisions['poor_pct']}%")

    known_zones = [x for x in shots["zones"] if x["key"] != "unknown" and x["shots"] >= 3]
    if known_zones:
        best = max(known_zones, key=lambda x: x["efficiency_pct"] if x["efficiency_pct"] is not None else -1)
        worst = min(known_zones, key=lambda x: x["efficiency_pct"] if x["efficiency_pct"] is not None else 999)
        if best["efficiency_pct"] is not None and worst["efficiency_pct"] is not None and best["efficiency_pct"] - worst["efficiency_pct"] >= 20:
            add("neutral", "Écart d'efficacité selon la zone", "Comparer création de l'avantage et qualité du tir, pas seulement la position finale du tireur.", f"{best['label']} {best['efficiency_pct']}% vs {worst['label']} {worst['efficiency_pct']}%")

    if not findings:
        add("neutral", "Échantillon encore à densifier", "Le moteur refuse de produire un diagnostic fort sans volume et contexte suffisants. Continuer le tagging structuré.", f"{len(events)} événements observés")
    return findings[:8]


def differential(team, opponent):
    rows = []
    for key, label in (
        ("scoring_efficiency_pct", "Efficacité tir"),
        ("shot_accuracy_pct", "Tirs cadrés"),
        ("pass_completion_pct", "Passes réussies"),
        ("turnovers", "Pertes"),
        ("ball_wins", "Ballons gagnés"),
    ):
        a, b = team.get(key), opponent.get(key)
        delta = round(a - b, 1) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
        rows.append({"key": key, "label": label, "team": a, "opponent": b, "delta": delta})
    return rows


def ultimate_event_report(events, perspective="for"):
    selected = _events_for(list(events or []), perspective)
    basic = _basic(selected)
    return {
        "basic": basic,
        "coverage": coverage_report(selected),
        "losses": loss_context_report(selected),
        "shots": shot_profile(selected),
        "passes": pass_profile(selected),
        "decisions": decision_report(selected),
        "pressure": pressure_report(selected),
        "periods": period_report(selected),
        "phases": phase_report(selected),
        "possessions": possession_report(selected),
        "qualitative": qualitative_findings(selected),
    }


def ultimate_match_report(match):
    events = sorted(list(getattr(match, "events", []) or []), key=lambda e: float(getattr(e, "second", 0) or 0))
    team = ultimate_event_report(events, "for")
    opponent = ultimate_event_report(events, "against")
    return {
        "version": "ultimate-analyst-v2.0",
        "team": team,
        "opponent": opponent,
        "differentials": differential(team["basic"], opponent["basic"]),
        "evidence_contract": {
            "measured": "Événements confirmés + valeurs calibrées explicitement taguées.",
            "derived": "Pourcentages calculés uniquement avec dénominateur observé.",
            "estimated": "Aucune possession n'est estimée comme exacte : sans possession=ID, seul un proxy d'actions terminales est affiché.",
            "qualitative": "Les constats coach sont générés à partir de seuils transparents puis doivent être validés par la vidéo.",
        },
        "tagging_schema": {
            "period": "1|2|3|4|OT|SO",
            "possession": "identifiant libre de possession",
            "zone": "wing_left|flat_left|point|flat_right|wing_right|centre|post_left|post_right|penalty|transition",
            "pressure": "low|medium|high",
            "decision": "good|neutral|poor",
            "cause": "bad_pass|centre_entry|counterattack|offensive_foul|shot_clock|steal|handling|decision|technical|pressure|other",
            "pass_type": "perimeter|centre_entry|skip|one_more|outlet|transition|post|restart",
            "shot_type": "catch_shoot|fake_shoot|drive|centre|lob|skip|penalty|transition",
            "hand": "right|left",
            "distance_m": "nombre",
            "shot_speed_kmh": "mesure calibrée uniquement",
            "release_time_s": "mesure calibrée uniquement",
        },
    }
