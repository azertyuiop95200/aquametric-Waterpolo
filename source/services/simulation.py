import math
import random

# Internal priors. These are deliberately NOT official rankings.
# Current-season rosters may be provisional; when so, coverage widens uncertainty rather than inventing precision.
SIM_TEAMS = {
    "Granville Water Polo": {
        "scope": "club", "competition_class": "France · Elite club", "level": 2,
        "strength": 56, "attack": 55, "defence": 54, "goalkeeper": 55, "extra_player": 52,
        "penalty_kill": 52, "transition": 55, "centre": 54, "depth": 51, "experience": 50,
        "cohesion": 61, "discipline": 55, "coverage": 0.48, "pace": 51,
        "history_score": 61, "home_history": 63, "away_history": 56, "recruitment_delta": 0.0, "roster_continuity": 57,
        "recruitment_note": "2026-27 recruitment impact not yet quantified; confirmed additions/departures will update this prior.",
        "roster_status": "PROVISIONAL", "note": "Promoted/current Elite context. The 2025-26 10–2 N1 season informs the historical prior, but is discounted for the move to Elite; 2026-27 roster evidence remains incomplete."
    },
    "Lille UC Métropole Water-Polo": {
        "scope": "club", "competition_class": "France · Elite club", "level": 2,
        "strength": 63, "attack": 64, "defence": 61, "goalkeeper": 62, "extra_player": 63,
        "penalty_kill": 60, "transition": 63, "centre": 60, "depth": 63, "experience": 64,
        "cohesion": 62, "discipline": 58, "coverage": 0.42, "pace": 53,
        "history_score": 68, "home_history": 70, "away_history": 65, "recruitment_delta": 0.0, "roster_continuity": 62,
        "recruitment_note": "Current-season recruitment impact remains provisional until confirmed roster sheets and player-strength links are complete.",
        "roster_status": "PROVISIONAL", "note": "Elite-club prior informed by recent seasons. Current-season roster is incomplete and will be refreshed from official sheets/announcements."
    },
    "Union St-Bruno Bordeaux": {
        "scope": "club", "competition_class": "France · Elite club", "level": 2,
        "strength": 60, "attack": 61, "defence": 58, "goalkeeper": 59, "extra_player": 60,
        "penalty_kill": 57, "transition": 60, "centre": 59, "depth": 59, "experience": 61,
        "cohesion": 60, "discipline": 58, "coverage": 0.38, "pace": 52,
        "history_score": 64, "home_history": 66, "away_history": 61, "recruitment_delta": 0.0, "roster_continuity": 60,
        "recruitment_note": "Recruitment impact is neutral until confirmed signings/departures can be linked to player ratings and roles.",
        "roster_status": "PROVISIONAL", "note": "Elite-club prior informed by recent seasons; current roster and 2026-27 competitive sample still incomplete."
    },
    "France — Women Senior": {
        "scope": "national", "competition_class": "Senior international", "level": 5,
        "strength": 86, "attack": 83, "defence": 85, "goalkeeper": 86, "extra_player": 81,
        "penalty_kill": 82, "transition": 84, "centre": 82, "depth": 88, "experience": 86,
        "cohesion": 82, "discipline": 79, "coverage": 0.74, "pace": 56,
        "history_score": 78, "home_history": 77, "away_history": 76, "recruitment_delta": 0.0, "roster_continuity": 80, "recruitment_note": "National teams use selection changes rather than club recruitment; impact is handled through availability and roster quality.",
        "roster_status": "PARTIAL_CURRENT", "note": "Senior-international prior informed by 2022-26 national-team data; exact match roster remains scenario-dependent."
    },
    "Spain — Women Senior": {
        "scope": "national", "competition_class": "Senior international · world elite", "level": 6,
        "strength": 94, "attack": 94, "defence": 92, "goalkeeper": 91, "extra_player": 94,
        "penalty_kill": 91, "transition": 93, "centre": 92, "depth": 95, "experience": 95,
        "cohesion": 94, "discipline": 88, "coverage": 0.82, "pace": 58,
        "history_score": 94, "home_history": 94, "away_history": 93, "recruitment_delta": 0.0, "roster_continuity": 90, "recruitment_note": "Selection changes are evaluated through roster strength/availability rather than transfer-market impact.",
        "roster_status": "PARTIAL_CURRENT", "note": "World-elite senior international prior; exact event roster and form should replace broad values when available."
    },
    "United States — Women Senior": {
        "scope": "national", "competition_class": "Senior international · world elite", "level": 6,
        "strength": 93, "attack": 93, "defence": 92, "goalkeeper": 94, "extra_player": 93,
        "penalty_kill": 92, "transition": 95, "centre": 90, "depth": 96, "experience": 94,
        "cohesion": 91, "discipline": 87, "coverage": 0.82, "pace": 59,
        "history_score": 93, "home_history": 93, "away_history": 92, "recruitment_delta": 0.0, "roster_continuity": 88, "recruitment_note": "Selection changes are evaluated through roster strength/availability rather than transfer-market impact.",
        "roster_status": "PARTIAL_CURRENT", "note": "World-elite senior international prior; current event roster and recent matches should refine it."
    },
    "France — Women U20": {
        "scope": "national", "competition_class": "U20 international", "level": 4,
        "strength": 74, "attack": 73, "defence": 73, "goalkeeper": 74, "extra_player": 72,
        "penalty_kill": 72, "transition": 76, "centre": 72, "depth": 75, "experience": 67,
        "cohesion": 73, "discipline": 72, "coverage": 0.45, "pace": 56,
        "history_score": 70, "home_history": 70, "away_history": 69, "recruitment_delta": 0.0, "roster_continuity": 65, "recruitment_note": "Youth selections use generation/selection changes instead of recruitment; roster turnover increases uncertainty.",
        "roster_status": "PROVISIONAL", "note": "U20 international prior; upcoming roster is provisional until official selection is published."
    },
    "Spain — Women U20": {
        "scope": "national", "competition_class": "U20 international · elite", "level": 4,
        "strength": 87, "attack": 88, "defence": 85, "goalkeeper": 84, "extra_player": 87,
        "penalty_kill": 85, "transition": 88, "centre": 86, "depth": 88, "experience": 80,
        "cohesion": 86, "discipline": 80, "coverage": 0.68, "pace": 58,
        "history_score": 88, "home_history": 88, "away_history": 87, "recruitment_delta": 0.0, "roster_continuity": 70, "recruitment_note": "Youth roster changes are handled through generation continuity and confirmed selections.",
        "roster_status": "PROVISIONAL", "note": "Elite U20 prior based on recent international benchmarks; next roster remains provisional until confirmed."
    },
    "Hungary — Women U20": {
        "scope": "national", "competition_class": "U20 international · elite", "level": 4,
        "strength": 84, "attack": 84, "defence": 84, "goalkeeper": 83, "extra_player": 85,
        "penalty_kill": 84, "transition": 85, "centre": 84, "depth": 85, "experience": 80,
        "cohesion": 84, "discipline": 80, "coverage": 0.62, "pace": 57,
        "history_score": 85, "home_history": 85, "away_history": 84, "recruitment_delta": 0.0, "roster_continuity": 70, "recruitment_note": "Youth roster changes are handled through generation continuity and confirmed selections.",
        "roster_status": "PROVISIONAL", "note": "Elite U20 prior; roster and tournament-specific form to be refreshed when official data is available."
    },
}

WEIGHTS = {
    "attack": .13, "defence": .13, "goalkeeper": .10, "extra_player": .08,
    "penalty_kill": .08, "transition": .08, "centre": .07, "depth": .08,
    "experience": .07, "cohesion": .07, "discipline": .04,
}

TACTICS = {
    "balanced": {"attack": 0.0, "defence": 0.0, "pace": 0.0},
    "transition": {"attack": 0.35, "defence": -0.12, "pace": 0.7},
    "centre_pressure": {"attack": 0.28, "defence": -0.05, "pace": -0.1},
    "zone_plus_focus": {"attack": 0.24, "defence": -0.04, "pace": 0.0},
    "defence_first": {"attack": -0.18, "defence": 0.32, "pace": -0.8},
}


def _poisson(lam, rng):
    # Knuth is adequate for water-polo score lambdas in this prototype.
    L = math.exp(-max(0.05, lam))
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


def _metric_strength(team):
    return sum(team[k] * w for k, w in WEIGHTS.items()) / sum(WEIGHTS.values())


def _effective_strength(team, availability=100, form=50, rest=3, home=False, away=False):
    # Competition/team prior dominates. Historical results, roster continuity and confirmed recruitment refine it.
    metric = _metric_strength(team)
    history = team.get("history_score", team["strength"])
    continuity = team.get("roster_continuity", 60)
    recruitment = max(-3.0, min(3.0, float(team.get("recruitment_delta", 0.0))))
    s = team["strength"] * 0.56 + metric * 0.30 + history * 0.10 + continuity * 0.04
    s += recruitment
    s += (max(50, min(100, availability)) - 100) * 0.11
    s += (max(30, min(70, form)) - 50) * 0.085
    if rest <= 0:
        s -= 1.5
    elif rest == 1:
        s -= 0.8
    elif rest >= 5:
        s += 0.15
    # Home/away is learned as a team-specific historical tendency rather than a universal fixed bonus.
    if home:
        s += (team.get("home_history", 55) - 50) * 0.045
    elif away:
        s += (team.get("away_history", 50) - 50) * 0.035
    return s


def _plan_matchup_bonus(team, opponent, tactic):
    # Tactical scenario impact is intentionally capped: tactics can optimise a matchup, not turn a domestic club into a senior national side.
    base = TACTICS.get(tactic, TACTICS["balanced"])
    bonus = base["attack"] + base["defence"]
    if tactic == "transition":
        bonus += (team["transition"] - opponent["transition"]) / 100 * 0.55
    elif tactic == "centre_pressure":
        bonus += (team["centre"] - opponent["defence"]) / 100 * 0.55
    elif tactic == "zone_plus_focus":
        bonus += (team["extra_player"] - opponent["penalty_kill"]) / 100 * 0.55
    elif tactic == "defence_first":
        bonus += (team["defence"] + team["goalkeeper"] - opponent["attack"] * 2) / 200 * 0.50
    return max(-0.55, min(0.55, bonus))


def simulate_matchup(team_a, team_b, tactic_a="balanced", tactic_b="balanced", n=5000, seed=17,
                     availability_a=100, availability_b=100, form_a=50, form_b=50,
                     rest_a=3, rest_b=3, venue="neutral"):
    a = SIM_TEAMS[team_a]
    b = SIM_TEAMS[team_b]
    sa = _effective_strength(a, availability_a, form_a, rest_a, venue == "team_a_home", venue == "team_b_home")
    sb = _effective_strength(b, availability_b, form_b, rest_b, venue == "team_b_home", venue == "team_a_home")

    # A reality gate for cross-level comparisons. It is small for peers and strong only when competition classes are far apart.
    level_gap = a["level"] - b["level"]
    if abs(level_gap) >= 2:
        gate = math.copysign(1.25 * (abs(level_gap) ** 1.35), level_gap)
        sa += max(0.0, gate)
        sb += max(0.0, -gate)

    # Tactics affect goal expectation by less than one goal in normal cases.
    ta = _plan_matchup_bonus(a, b, tactic_a)
    tb = _plan_matchup_bonus(b, a, tactic_b)

    rating_diff = sa - sb
    # Saturating conversion from rating gap to expected goal margin.
    expected_margin = 11.8 * math.tanh(rating_diff / 25.5) + (ta - tb) * 0.85

    # Expected total stays in a realistic water-polo band and reflects pace + defensive plans.
    pace = (a["pace"] + b["pace"]) / 2
    total = 20.5 + (pace - 52) * 0.16 + (TACTICS[tactic_a]["pace"] + TACTICS[tactic_b]["pace"]) * 0.28
    total = max(15.5, min(25.5, total))
    lam_a = max(1.2, min(22.0, (total + expected_margin) / 2))
    lam_b = max(1.2, min(22.0, (total - expected_margin) / 2))

    coverage = min(a["coverage"], b["coverage"])
    # Lower coverage increases outcome dispersion, but never moves the mean toward nonsense.
    uncertainty = 0.07 + (1 - coverage) * 0.13
    rng = random.Random(seed)
    scores, aw, bw, draws = [], 0, 0, 0
    for _ in range(n):
        shared = max(0.72, min(1.30, rng.gauss(1.0, uncertainty * 0.55)))
        shock_a = max(0.72, min(1.30, rng.gauss(1.0, uncertainty)))
        shock_b = max(0.72, min(1.30, rng.gauss(1.0, uncertainty)))
        xa = _poisson(lam_a * shared * shock_a, rng)
        xb = _poisson(lam_b * shared * shock_b, rng)
        scores.append((xa, xb))
        if xa > xb:
            aw += 1
        elif xb > xa:
            bw += 1
        else:
            draws += 1

    avg_a = sum(x[0] for x in scores) / n
    avg_b = sum(x[1] for x in scores) / n
    diffs = sorted(x[0] - x[1] for x in scores)
    lo, hi = diffs[int(.10 * n)], diffs[int(.90 * n)]
    cross_level = abs(a["level"] - b["level"]) >= 2

    factor_rows = [
        ("Competition class", a["competition_class"], b["competition_class"], round(rating_diff, 1)),
        ("Historical results prior", a.get("history_score", "—"), b.get("history_score", "—"), round((a.get("history_score",50)-b.get("history_score",50))*.10,1)),
        ("Home/away history", a.get("home_history" if venue=="team_a_home" else "away_history", "—"), b.get("home_history" if venue=="team_b_home" else "away_history", "—"), 0.0),
        ("Recruitment / selection impact", a.get("recruitment_delta",0.0), b.get("recruitment_delta",0.0), round(a.get("recruitment_delta",0.0)-b.get("recruitment_delta",0.0),1)),
        ("Roster continuity", a.get("roster_continuity","—"), b.get("roster_continuity","—"), round((a.get("roster_continuity",60)-b.get("roster_continuity",60))*.04,1)),
        ("Roster availability", f"{availability_a}%", f"{availability_b}%", round((availability_a-availability_b)*.11,1)),
        ("Attack", a["attack"], b["attack"], round((a["attack"]-b["attack"])*.08,1)),
        ("Defence", a["defence"], b["defence"], round((a["defence"]-b["defence"])*.08,1)),
        ("Goalkeeper", a["goalkeeper"], b["goalkeeper"], round((a["goalkeeper"]-b["goalkeeper"])*.10,1)),
        ("Zone+", a["extra_player"], b["extra_player"], round((a["extra_player"]-b["extra_player"])*.08,1)),
        ("Zone−", a["penalty_kill"], b["penalty_kill"], round((a["penalty_kill"]-b["penalty_kill"])*.08,1)),
        ("Transition", a["transition"], b["transition"], round((a["transition"]-b["transition"])*.08,1)),
        ("Centre play", a["centre"], b["centre"], round((a["centre"]-b["centre"])*.07,1)),
        ("Depth", a["depth"], b["depth"], round((a["depth"]-b["depth"])*.08,1)),
        ("Experience", a["experience"], b["experience"], round((a["experience"]-b["experience"])*.07,1)),
        ("Cohesion", a["cohesion"], b["cohesion"], round((a["cohesion"]-b["cohesion"])*.07,1)),
        ("Recent form input", form_a, form_b, round((form_a-form_b)*.085,1)),
        ("Rest days", rest_a, rest_b, 0.0),
    ]

    return {
        "team_a": team_a, "team_b": team_b,
        "avg_a": round(avg_a, 1), "avg_b": round(avg_b, 1),
        "win_a": round(aw / n * 100, 2), "win_b": round(bw / n * 100, 2), "draw": round(draws / n * 100, 2),
        "diff_interval": [lo, hi], "coverage": round(coverage * 100), "n": n,
        "strength_a": round(sa, 1), "strength_b": round(sb, 1), "class_gap": abs(a["level"] - b["level"]),
        "cross_level": cross_level, "factor_rows": factor_rows,
        "tactic_a": tactic_a, "tactic_b": tactic_b,
        "roster_status_a": a["roster_status"], "roster_status_b": b["roster_status"],
        "recruitment_note_a": a.get("recruitment_note", "No recruitment context available."),
        "recruitment_note_b": b.get("recruitment_note", "No recruitment context available."),
        "disclaimer": "Exploratory scenario model, not a betting forecast. Historical results are time- and competition-weighted priors; confirmed recruitment/selection changes only alter the model when their role and player strength are sufficiently supported. Current-season results, confirmed rosters and video-derived metrics progressively replace provisional priors."
    }
