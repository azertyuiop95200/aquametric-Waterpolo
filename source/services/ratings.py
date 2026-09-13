from collections import defaultdict

WEIGHTS = {
    "goal": 8, "assist": 5, "block": 4, "interception": 4, "recovery": 3,
    "save": 3, "shot_on_target": 1, "shot_off_target": 0, "shot_blocked": -0.5,
    "bad_pass": -2, "turnover": -4, "foul": -1,
    "exclusion": -3, "exclusion_earned": 3, "exclusion_committed": -3,
    "penalty_earned": 4, "penalty_committed": -4, "goal_conceded": -2,
    "fast_recovery": 3, "late_recovery": -2,
}

def calculate_player_rating(events):
    score = 50.0
    evidence = defaultdict(int)
    for event in events:
        score += WEIGHTS.get(event.event_type, 0)
        evidence[event.event_type] += 1
    score = max(0, min(100, round(score, 1)))
    confidence = "LOW SAMPLE" if len(events) < 5 else "MEDIUM" if len(events) < 15 else "HIGH"
    return score, confidence, dict(evidence)
