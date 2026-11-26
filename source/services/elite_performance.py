"""Evidence-based water polo performance, versioned for senior rules 2026.

This is an annotation reducer, NOT a computer vision detector or referee.
Every count describes the reviewed sample. A possession ends only when explicitly
recorded; a shot recovered by the attack is not a new team possession.
"""
from collections import Counter, defaultdict
from math import isfinite
import re

RULES = {"version": "World Aquatics 2026-02 / FFN senior 2026-27",
         "quarters": 4, "quarter_seconds": 480, "shot_clock_seconds": 28,
         "reset_seconds": 18, "exclusion_seconds": 18,
         "source": "https://www.worldaquatics.com/rules/competition-regulations",
         "ffn": "https://www.ffnatation.fr/reglements-du-water-polo"}

def shot_clock_reset(reason, remaining=None, rules=None):
    """Only ordinary reset cases; the referee's observed decision takes precedence."""
    r = rules or RULES
    if reason in {"new_possession", "goal"}:
        return r["shot_clock_seconds"]
    if reason in {"offensive_rebound", "corner"}:
        return r["reset_seconds"]
    if reason == "exclusion" and remaining is not None:
        return max(remaining, r["reset_seconds"])
    return None

SHOTS = {"goal", "shot_on_target", "shot_off_target", "shot_blocked"}
END_LABELS = {
    "goal": "But", "save": "Arrêt gardienne", "off_target": "Tir non cadré",
    "post": "Poteau / barre", "blocked": "Tir contré",
    "bad_pass": "Mauvaise passe", "steal": "Interception adverse",
    "offensive_foul": "Faute offensive", "shot_clock": "Fin du chrono",
    "handling": "Erreur technique", "period_end": "Fin de période",
    "other": "Autre", "unknown": "Non classée",
}
PHASES = {"even_attack": "6 contre 6", "power_play": "6 contre 5",
          "penalty": "Penalty 5 m", "counterattack": "Contre-attaque",
          "centre_play": "Jeu en pointe", "penalty_kill": "5 contre 6",
          "auto": "Non déterminée"}
TAG = re.compile(r"(?:^|[\s;|])([a-z][a-z0-9_]{1,31})\s*=\s*([^\s;|]+)", re.I)

def tags(e):
    return {m.group(1).lower(): m.group(2).lower() for m in TAG.finditer(e.get("note") or "")}

def number(value, maximum):
    try:
        n = float(value)
        return n if isfinite(n) and 0 <= n <= maximum else None
    except (ValueError, TypeError):
        return None

def pct(n, d):
    return round(100*n/d, 1) if d else None

def clock(e):
    t = tags(e)
    p = number(t.get("period"), 4)
    c = number(t.get("game_clock_s"), 480)
    if p is None or p < 1 or p != int(p) or c is None:
        return None
    return int(p), c

def exposure(rows):
    """Pair explicit entry/exit in the same quarter using the playing clock.
    No elapsed-video substitution. Missing entries/exits make the total partial.
    """
    groups = defaultdict(list)
    invalid = 0
    for e in rows:
        if e.get("event_type") not in {"player_in", "player_out"}:
            continue
        tc = clock(e)
        if tc is None:
            invalid += 1
            continue
        groups[tc[0]].append((tc[1], e.get("event_type"), e.get("id") or 0))
    duration = 0.0
    pairs = 0
    for entries in groups.values():
        start = None
        for c, typ, _ in sorted(entries, key=lambda x: (-x[0], x[2])):
            if typ == "player_in":
                if start is not None:
                    invalid += 1
                start = c
            elif start is None:
                invalid += 1
            else:
                duration += start-c
                pairs += 1
                start = None
        if start is not None:
            invalid += 1
    return {"playing_seconds": round(duration, 1) if pairs else None,
            "playing_intervals": pairs, "unpaired_markers": invalid}

def reduce_side(rows):
    c = Counter(e.get("event_type") for e in rows)
    shots = sum(c[k] for k in SHOTS)
    on = c["goal"] + c["shot_on_target"]
    ends = Counter()
    for e in rows:
        if e.get("event_type") == "possession_end":
            outcome = tags(e).get("outcome", "unknown")
            ends[outcome if outcome in END_LABELS else "unknown"] += 1
    classified = sum(ends.values()) - ends["unknown"]
    penalties = [e for e in rows if e.get("phase") == "penalty" and e.get("event_type") in SHOTS]
    pp = Counter(tags(e).get("outcome") for e in rows if e.get("event_type") == "power_play_end")
    pk = Counter(tags(e).get("outcome") for e in rows if e.get("event_type") == "penalty_kill_end")
    pp_total = pp["goal"] + pp["no_goal"]
    pk_total = pk["goal"] + pk["no_goal"]
    distances = [number(tags(e).get("distance_m"), 10000) for e in rows
                 if e.get("event_type") == "distance_sample"]
    distances = [d for d in distances if d is not None]
    return {
        "events": len(rows), "goals": c["goal"], "shots": shots, "on_target": on,
        "off_target": c["shot_off_target"], "blocked_shots": c["shot_blocked"],
        "shot_conversion": pct(c["goal"], shots), "shot_accuracy": pct(on, shots),
        "assists": c["assist"], "points": c["goal"]+c["assist"],
        "key_passes": c["key_pass"], "passes": c["pass_complete"],
        "bad_passes": c["bad_pass"], "pass_accuracy": pct(c["pass_complete"], c["pass_complete"]+c["bad_pass"]),
        "turnovers": c["turnover"], "unforced_errors": c["unforced_error"],
        "steals": c["interception"], "recoveries": c["recovery"], "blocks": c["block"],
        "fouls_committed": c["foul"], "fouls_earned": c["foul_earned"],
        "offensive_fouls": c["offensive_foul"],
        "exclusions_committed": c["exclusion_committed"]+c["exclusion"],
        "exclusions_earned": c["exclusion_earned"],
        "penalties_committed": c["penalty_committed"], "penalties_earned": c["penalty_earned"],
        "personal_fouls": c["exclusion_committed"]+c["exclusion"]+c["penalty_committed"],
        "penalty_shots": len(penalties), "penalty_goals": sum(e.get("event_type")=="goal" for e in penalties),
        "penalty_conversion": pct(sum(e.get("event_type")=="goal" for e in penalties), len(penalties)),
        "saves": c["save"], "goals_against": c["goal_against"],
        "save_pct": pct(c["save"], c["save"]+c["goal_against"]),
        "possession_ends": sum(ends.values()), "classified_ends": classified,
        "attack_conversion": pct(ends["goal"], classified),
        "outcomes": [{"label": END_LABELS[k], "count": v, "share": pct(v,sum(ends.values()))}
                     for k,v in ends.items() if v],
        "power_play_completed": pp_total, "power_play_conversion": pct(pp["goal"],pp_total),
        "penalty_kill_completed": pk_total, "penalty_kill_success": pct(pk["no_goal"],pk_total),
        "counterattacks": c["counterattack_start"],
        "swimoffs_won": c["swim_off_won"], "swimoffs_lost": c["swim_off_lost"],
        "timeouts": c["timeout_start"], "clock_expiries": c["shot_clock_expired"],
        "sprints": c["sprint"],
        "distance_m": round(sum(distances),1) if distances else None,
        "distance_samples": len(distances), **exposure(rows),
    }

METRICS = [
    ("goals","Buts"),("shots","Tirs"),("on_target","Cadrés (buts inclus)"),
    ("off_target","Non cadrés"),("blocked_shots","Tirs contrés"),
    ("shot_conversion","Conversion tir (%)"),("shot_accuracy","Précision (%)"),
    ("assists","Passes décisives"),("points","Buts + passes décisives"),
    ("key_passes","Passes clés"),("passes","Passes réussies"),("bad_passes","Mauvaises passes"),
    ("pass_accuracy","Passes réussies (%)"),("turnovers","Pertes directes"),
    ("unforced_errors","Erreurs non provoquées"),("steals","Interceptions"),
    ("recoveries","Récupérations"),("blocks","Contres"),
    ("fouls_committed","Fautes ordinaires commises"),("fouls_earned","Fautes ordinaires obtenues"),
    ("offensive_fouls","Fautes offensives"),("exclusions_committed","Exclusions commises"),
    ("exclusions_earned","Exclusions obtenues"),("penalties_committed","5 m concédés"),
    ("penalties_earned","5 m obtenus"),("personal_fouls","Fautes personnelles annotées"),
    ("penalty_shots","Tirs à 5 m"),("penalty_goals","Buts à 5 m"),("penalty_conversion","5 m (%)"),
    ("saves","Arrêts"),("goals_against","Buts encaissés attribués"),("save_pct","Arrêts (%)"),
    ("possession_ends","Fins de possession"),("classified_ends","Fins classées"),
    ("attack_conversion","Attaques réussies (%)"),("power_play_completed","6v5 terminés et classés"),
    ("power_play_conversion","6v5 réussis (%)"),("penalty_kill_completed","5v6 terminés et classés"),
    ("penalty_kill_success","5v6 défendus (%)"),("counterattacks","Contre-attaques lancées"),
    ("swimoffs_won","Engagements gagnés"),("swimoffs_lost","Engagements perdus"),
    ("timeouts","Temps morts"),("clock_expiries","Expirations du chrono"),
    ("sprints","Sprints annotés"),("playing_seconds","Temps de jeu relevé (s)"),
    ("distance_m","Distance relevée (m)"),("distance_samples","Segments de distance relevés"),
    ("playing_intervals","Intervalles de jeu appariés"),("unpaired_markers","Entrées/sorties à compléter"),
]
PLAYER_KEYS = ("playing_seconds","distance_m","goals","shots","shot_conversion","shot_accuracy","assists",
               "steals","blocks","recoveries","fouls_committed","fouls_earned","exclusions_committed",
               "exclusions_earned","penalties_committed","penalties_earned","personal_fouls",
               "turnovers","unforced_errors","saves","goals_against","save_pct","possession_ends",
               "playing_intervals","unpaired_markers")

def elite_report(events):
    confirmed = [e for e in events if str(e.get("confidence") or "").upper() in {"CONFIRMED","VERIFIED"}]
    sides = {s:[e for e in confirmed if e.get("perspective")==s] for s in ("for","against")}
    players = defaultdict(list)
    for e in sides["for"]:
        if e.get("player_id"):
            players[(e["player_id"],e.get("player") or "Joueuse")].append(e)
    phase_rows = []
    for phase,label in PHASES.items():
        values = {s:reduce_side([e for e in rows if e.get("phase")==phase]) for s,rows in sides.items()}
        phase_rows.append({"label":label, **values})
    periods = []
    for q in range(1,5):
        values = {s:reduce_side([e for e in rows if number(tags(e).get("period"),4)==q]) for s,rows in sides.items()}
        periods.append({"quarter":q, **values})
    return {"rules": RULES, "metrics": METRICS, "player_metrics":[(k,l) for k,l in METRICS if k in PLAYER_KEYS],
            "team": reduce_side(sides["for"]), "opponent":reduce_side(sides["against"]),
            "players":[{"id":pid,"name":name,**reduce_side(rows)} for (pid,name),rows in sorted(players.items(),key=lambda x:x[0][1])],
            "phases":phase_rows, "quarters":periods,
            "unassigned_period":sum(number(tags(e).get("period"),4) not in {1,2,3,4} for e in confirmed),
            "scope":"confirmed_sample"}
