from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict

from services.research_knowledge import TACTICAL_LIBRARY

PHASE_START_EVENTS = {
    "power_play_start": "power_play",
    "penalty_kill_start": "penalty_kill",
    "counterattack_start": "counterattack",
    "defensive_recovery_start": "defensive_recovery",
}

SHOT_EVENTS = {"goal", "shot_on_target", "shot_off_target", "shot_blocked", "block"}
LOSS_EVENTS = {"turnover", "bad_pass"}
PASS_EVENTS = {"pass_complete", "assist"}


def _meta(event):
    meta = getattr(event, "context_meta", None)
    return {
        "perspective": getattr(meta, "perspective", "for") if meta else "for",
        "phase_tag": getattr(meta, "phase_tag", "auto") if meta else "auto",
    }


def _confidence(event_count: int, explicit_phase_count: int, tracking_ready: bool = False) -> str:
    if tracking_ready and event_count >= 20:
        return "HIGH CONFIDENCE"
    if explicit_phase_count >= 2 and event_count >= 8:
        return "MODERATE"
    if event_count >= 4:
        return "PRELIMINARY"
    return "INSUFFICIENT DATA"


def _pct(n, d):
    return round(100 * n / d, 1) if d else None


def analyze_match_tactics(match) -> dict:
    events = sorted(match.events, key=lambda e: e.second)
    tagged = [(e, _meta(e)) for e in events]
    counts_for = Counter(e.event_type for e, m in tagged if m["perspective"] == "for")
    counts_against = Counter(e.event_type for e, m in tagged if m["perspective"] == "against")
    explicit_phases = sum(1 for e, m in tagged if e.event_type in PHASE_START_EVENTS or m["phase_tag"] not in {"", "auto"})

    attack_shots = sum(counts_for[x] for x in SHOT_EVENTS)
    attack_goals = counts_for["goal"]
    opp_shots = sum(counts_against[x] for x in SHOT_EVENTS)
    opp_goals = counts_against["goal"]
    attack_losses = sum(counts_for[x] for x in LOSS_EVENTS)
    recoveries = counts_for["recovery"] + counts_for["interception"]

    headline = []
    if attack_shots:
        eff = _pct(attack_goals, attack_shots)
        headline.append({"label": "Tagged shot conversion", "value": f"{eff}%", "detail": f"{attack_goals} goals from {attack_shots} tagged shot outcomes"})
    if attack_losses:
        headline.append({"label": "Ball-security alerts", "value": str(attack_losses), "detail": "turnovers + bad passes in verified tags"})
    if recoveries:
        headline.append({"label": "Ball wins", "value": str(recoveries), "detail": "recoveries + interceptions"})
    if opp_shots:
        headline.append({"label": "Opponent tagged conversion", "value": f"{_pct(opp_goals, opp_shots)}%", "detail": "requires opponent-perspective tagging"})

    remarks = []
    if attack_shots >= 5:
        eff = attack_goals / attack_shots
        if eff >= .45:
            remarks.append({"tone": "positive", "title": "Finishing efficiency is a current strength", "text": "Tagged shot outcomes show strong conversion. Preserve the shot-quality process; do not assume the result came only from shooting skill.", "evidence": f"{attack_goals}/{attack_shots} tagged outcomes ended in goals."})
        elif eff <= .25:
            remarks.append({"tone": "warning", "title": "Review shot selection before blaming execution", "text": "Low conversion can come from shot location, defensive block, goalkeeper positioning or rushed timing. Use clips to classify the cause before prescribing shooting work.", "evidence": f"{attack_goals}/{attack_shots} tagged outcomes ended in goals."})
    if attack_losses >= 4:
        remarks.append({"tone": "warning", "title": "Possession security deserves review", "text": "Repeated turnovers/bad passes can damage both attack quality and defensive transition. Classify whether losses occurred under pressure, in transition, at centre entry or during power play.", "evidence": f"{attack_losses} verified ball-security events."})
    if counts_for["fast_recovery"] + counts_for["late_recovery"] >= 4:
        fr, lr = counts_for["fast_recovery"], counts_for["late_recovery"]
        remarks.append({"tone": "positive" if fr > lr else "warning", "title": "Defensive transition has enough evidence to review", "text": "Compare reaction time after loss, central-lane protection and restoration of matchups. Tracking will later replace subjective labels with measured seconds and distance.", "evidence": f"{fr} fast vs {lr} late recovery tags."})

    sequences = build_phase_sequences(events)
    power = [x for x in sequences if x["phase"] == "power_play"]
    penalty_kill = [x for x in sequences if x["phase"] == "penalty_kill"]
    counter = [x for x in sequences if x["phase"] == "counterattack"]

    # Contextual phase KPIs. These are descriptive of the tagged sample, not
    # universal performance standards. Research uses similar dimensions (action
    # duration, passes, exclusions, shot origin/outcome) but competition context matters.
    if len(power) >= 3:
        pp_shots = sum(1 for x in power if x["shots_for"] > 0)
        pp_goals = sum(x["goals_for"] for x in power)
        pp_passes = sum(x["passes"] for x in power)
        pp_times = [x["time_to_first_shot"] for x in power if x["time_to_first_shot"] is not None]
        headline.append({
            "label": "Tagged Zone+ conversion",
            "value": f"{_pct(pp_goals, len(power))}%",
            "detail": f"{pp_goals}/{len(power)} sequences · {_pct(pp_shots, len(power))}% created a tagged shot"
        })
        if pp_times:
            avg_pp_time = sum(pp_times) / len(pp_times)
            avg_pp_passes = pp_passes / len(power)
            remarks.append({
                "tone": "neutral",
                "title": "Zone+ tempo can be reviewed sequence by sequence",
                "text": "Use the average only as a starting point. Compare quick-shot sequences with longer circulation, shot quality and defensive displacement before deciding whether tempo was good or bad.",
                "evidence": f"{len(power)} tagged Zone+ sequences · {avg_pp_time:.1f}s mean to first tagged shot · {avg_pp_passes:.1f} tagged passes per sequence."
            })

    if len(penalty_kill) >= 2:
        conceded = sum(x["goals_against"] for x in penalty_kill)
        headline.append({
            "label": "Tagged 5-on-6 stop rate",
            "value": f"{_pct(len(penalty_kill)-conceded, len(penalty_kill))}%",
            "detail": f"{conceded} goals conceded in {len(penalty_kill)} tagged penalty-kill sequences"
        })

    if len(counter) >= 3:
        c_goals = sum(x["goals_for"] for x in counter)
        c_losses = sum(x["losses_for"] for x in counter)
        c_shots = sum(x["shots_for"] for x in counter)
        remarks.append({
            "tone": "positive" if c_goals and c_losses == 0 else "warning" if c_losses > c_goals else "neutral",
            "title": "Counterattack outcome has enough tagged volume to compare",
            "text": "Separate the quality of the first transition reaction from the final shot. A failed counter can originate from lane occupation, outlet timing, pass choice, finish quality or recovery by the opponent.",
            "evidence": f"{len(counter)} tagged counters · {c_shots} shot outcomes · {c_goals} goals · {c_losses} losses."
        })

    # Research shows close and unbalanced games can have different discriminating
    # indicators. Only use this lens if enough tagged goals exist to characterize margin.
    tagged_for_goals = counts_for["goal"]
    tagged_against_goals = counts_against["goal"]
    tagged_goal_total = tagged_for_goals + tagged_against_goals
    match_context = "unknown"
    if tagged_goal_total >= 8:
        margin = abs(tagged_for_goals - tagged_against_goals)
        match_context = "close" if margin <= 2 else "unbalanced" if margin >= 5 else "intermediate"
        remarks.append({
            "tone": "neutral",
            "title": f"Interpretation lens: {match_context} tagged-score context",
            "text": "Do not apply the same tactical benchmark to every score state. Close and unbalanced international matches can emphasize different indicators, so AquaMetric keeps score margin as context rather than a player-quality shortcut.",
            "evidence": f"Current tagged goals: {tagged_for_goals}-{tagged_against_goals}; margin {margin}."
        })
    if power:
        with_shot = sum(1 for x in power if x["shots_for"] > 0)
        goals = sum(x["goals_for"] for x in power)
        losses = sum(x["losses_for"] for x in power)
        tone = "warning" if with_shot < len(power) or losses else "neutral"
        remarks.append({
            "tone": tone, "title": "Zone+ / power-play process is now measurable",
            "text": "Review whether each advantage creates a clean shot before judging the final conversion. Formation labels and lane quality still require tracking evidence.",
            "evidence": f"{with_shot}/{len(power)} tagged power plays produced a shot; {goals} goals; {losses} tagged losses."
        })
    kill = penalty_kill
    if kill and any(x["opponent_events"] for x in kill):
        conceded = sum(x["goals_against"] for x in kill)
        remarks.append({
            "tone": "warning" if conceded else "positive", "title": "5-on-6 defence has opponent-context evidence",
            "text": "Evaluate rotation, shot lane conceded, block geometry and goalkeeper sightline around these sequences. Avoid crediting a stop to structure alone until tracking confirms the defensive shape.",
            "evidence": f"{len(kill)} tagged penalty-kill sequences; {conceded} opponent goals in tagged context."
        })
    if not remarks:
        remarks.append({"tone": "neutral", "title": "Not enough verified tactical evidence yet", "text": "Add phase-start tags, team/opponent perspective and key outcomes. AquaMetric intentionally avoids inventing formation or decision-quality conclusions from sparse data.", "evidence": f"{len(events)} verified events available."})

    phase_cards = []
    for key in ["power_play", "penalty_kill", "counterattack", "defensive_recovery", "even_attack", "even_defence"]:
        seqs = [s for s in sequences if s["phase"] == key]
        lib = TACTICAL_LIBRARY.get(key, {})
        phase_cards.append({
            "key": key,
            "label": key.replace("_", " ").title(),
            "sequences": len(seqs),
            "principles": lib.get("principles", []),
            "patterns": lib.get("patterns", []),
            "requires_tracking_for": lib.get("requires_tracking_for", []),
            "summary": summarize_phase(key, seqs),
        })

    limitations = [
        "Formation labels such as 4-2, 3-3, press, M-zone or 2-4 drop are not asserted without player/ball tracking or explicit analyst tagging.",
        "Current tactical conclusions are based on verified event tags; they are not a substitute for computer-vision positioning data.",
        "Match context (score margin, opponent level, timeout, quarter, exclusion timing) must be added before benchmark comparisons become strong.",
    ]

    return {
        "confidence": _confidence(len(events), explicit_phases),
        "event_count": len(events),
        "explicit_phase_count": explicit_phases,
        "headline": headline,
        "remarks": remarks,
        "phases": phase_cards,
        "sequences": sequences,
        "match_context": match_context,
        "research_lens": [
            "Notational analyses support separating Even, Counterattack and Power Play by duration, passes, exclusions/penalties, shot origin and outcome.",
            "International women's studies identify power-play goals, counterattack outcomes, steals/blocks and goalkeeper saves as useful discriminating indicators, but not universal causal rules.",
            "Close versus unbalanced matches should be interpreted differently; score context is retained before benchmarking."
        ],
        "limitations": limitations,
    }


def build_phase_sequences(events):
    events = sorted(events, key=lambda e: e.second)
    starts = []
    current_phase = None
    last_second = None
    for i, e in enumerate(events):
        meta = _meta(e)
        explicit_start = PHASE_START_EVENTS.get(e.event_type)
        tagged_phase = meta["phase_tag"] if meta["phase_tag"] not in {"", "auto"} else None
        phase = explicit_start or tagged_phase
        # A phase tag describes the current sequence; it should not create a new
        # sequence on every event. Start only on an explicit start marker, a
        # phase change, or after a long gap.
        gap_reset = last_second is not None and e.second - last_second > 35
        if explicit_start or (phase and (phase != current_phase or gap_reset)):
            starts.append((i, e.second, phase))
            current_phase = phase
        elif phase:
            current_phase = phase
        if gap_reset and not phase:
            current_phase = None
        last_second = e.second
    sequences = []
    for n, (idx, second, phase) in enumerate(starts):
        next_second = starts[n + 1][1] if n + 1 < len(starts) else second + 35
        end_second = min(second + 35, next_second)
        seq_events = [e for e in events if second <= e.second < end_second]
        counts = Counter(e.event_type for e in seq_events)
        for_counts = Counter(e.event_type for e in seq_events if _meta(e)["perspective"] == "for")
        against_counts = Counter(e.event_type for e in seq_events if _meta(e)["perspective"] == "against")
        first_shot = next((e for e in seq_events if _meta(e)["perspective"] == "for" and e.event_type in SHOT_EVENTS), None)
        sequences.append({
            "phase": phase,
            "start": second,
            "end": end_second,
            "duration": round(end_second - second, 1),
            "events": len(seq_events),
            "opponent_events": sum(against_counts.values()),
            "passes": sum(for_counts[x] for x in PASS_EVENTS),
            "shots": sum(for_counts[x] for x in SHOT_EVENTS),
            "goals": for_counts["goal"],
            "losses": sum(for_counts[x] for x in LOSS_EVENTS),
            "shots_for": sum(for_counts[x] for x in SHOT_EVENTS),
            "shots_against": sum(against_counts[x] for x in SHOT_EVENTS),
            "goals_for": for_counts["goal"],
            "goals_against": against_counts["goal"],
            "losses_for": sum(for_counts[x] for x in LOSS_EVENTS),
            "blocks_for": for_counts["block"] + for_counts["shot_blocked"],
            "fast_recovery": for_counts["fast_recovery"],
            "late_recovery": for_counts["late_recovery"],
            "time_to_first_shot": round(first_shot.second - second, 1) if first_shot else None,
        })
    return sequences


def summarize_phase(key: str, seqs: list[dict]) -> str:
    if not seqs:
        return "No explicitly tagged sequences yet. Add phase-start tags or wait for the future tracking engine."
    shots = sum(s["shots_for"] for s in seqs)
    goals = sum(s["goals_for"] for s in seqs)
    losses = sum(s["losses_for"] for s in seqs)
    shot_times = [s["time_to_first_shot"] for s in seqs if s["time_to_first_shot"] is not None]
    if key == "power_play":
        with_shot = sum(1 for s in seqs if s["shots_for"] > 0)
        base = f"{len(seqs)} tagged sequences · {with_shot} produced a shot · {goals} goals · {losses} losses"
    elif key == "penalty_kill":
        conceded = sum(s["goals_against"] for s in seqs)
        opp_shots = sum(s["shots_against"] for s in seqs)
        base = f"{len(seqs)} tagged sequences · {opp_shots} opponent shot outcomes · {conceded} goals conceded in tagged context"
    elif key == "counterattack":
        base = f"{len(seqs)} tagged transitions · {shots} shot outcomes · {goals} goals · {losses} losses"
    elif key == "defensive_recovery":
        late = sum(s["late_recovery"] for s in seqs); fast = sum(s["fast_recovery"] for s in seqs)
        base = f"{len(seqs)} tagged recoveries · {fast} fast labels · {late} late labels · {sum(s['goals_against'] for s in seqs)} goals against in tagged context"
    else:
        base = f"{len(seqs)} tagged sequences · {shots} shot outcomes · {goals} goals · {losses} losses"
    if shot_times:
        base += f" · {sum(shot_times)/len(shot_times):.1f}s average to first tagged shot"
    return base
