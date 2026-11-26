"""Per-family coverage, confirmed and automatic evidence kept separate."""
from collections import Counter,defaultdict
from services.elite_performance import METRICS,reduce_side

FAMILIES={
"tirs":("goal","shot_on_target","shot_off_target","shot_blocked","shot_unknown"),
"passes":("assist","key_pass","pass_complete","bad_pass"),
"duels":("duel_won","duel_lost"),
"touches":("touch","centre_touch"),
"pertes":("turnover","bad_pass","unforced_error"),
"defense":("interception","recovery","block","save","goal_against"),
"arbitrage":("foul","foul_earned","offensive_foul","exclusion","exclusion_committed","exclusion_earned","penalty_committed","penalty_earned"),
"possessions":("possession_end","possession_start"),
"numerique":("power_play_end","penalty_kill_end","power_play_start","penalty_kill_start"),
"transition":("counterattack_start","fast_recovery","late_recovery"),
"chronometres":("timeout_start","swim_off_won","swim_off_lost","shot_clock_expired"),
"physique":("player_in","player_out","distance_sample","sprint"),
}
def metric_table(rows):
    stats=reduce_side(rows)
    counts=Counter(e.get("event_type") for e in rows)
    families=[{"family":k,"events":sum(counts[t] for t in types)} for k,types in FAMILIES.items()]
    # A positive count is a documented sample. An implementation zero is
    # not a proven sporting zero without complete observation.
    values={k:(v if v!=0 or k in ("events",) else None) for k,v in stats.items()}
    # Ratio zero is meaningful only where denominator actually exists.
    for k in ("shot_conversion","shot_accuracy","pass_accuracy","duel_pct","save_pct","attack_conversion","penalty_conversion","power_play_conversion","penalty_kill_success"):
        values[k]=stats.get(k)
    return {"metrics":values,"families":families,"event_count":len(rows),"scope":"partial_sample"}

def report_coverage(confirmed,automatic,roster):
    verified=[e for e in confirmed if str(e.get("confidence") or "").upper() in {"CONFIRMED","VERIFIED"}]
    tentative=[]
    for e in automatic.get("events",[]):
        if e.get("counted") is not True or e.get("conflict") or e.get("is_replay"):continue
        # Keep the model's possession outcome, do not manufacture one.
        outcome=e.get("possession_outcome","unknown")
        if outcome not in ("goal","save","off_target","post","blocked","bad_pass","steal","offensive_foul","shot_clock","handling","period_end","unknown"):outcome="unknown"
        tentative.append(dict(e,perspective=e.get("side"),note="outcome="+outcome if e.get("event_type")=="possession_end" else ""))
    teams={}
    for side in ("for","against"):
        teams[side]={"confirmed":metric_table([e for e in verified if e.get("perspective")==side]),"candidate":metric_table([e for e in tentative if e.get("perspective")==side])}
    players=[]
    groups=defaultdict(list)
    for e in tentative:
        cap=e.get("cap_number")
        if e.get("perspective") in ("for","against") and type(cap) is int and 1<=cap<=30:groups[(e["perspective"],cap)].append(e)
    for (s,n),rr in sorted(groups.items()):
        players.append({"side":s,"cap":n,**metric_table(rr)})
    return {"teams":teams,"candidate_players":players,"roster":[{"id":r["id"],"name":r["name"],"cap":r.get("cap_number")} for r in roster],
            "labels":METRICS,"video_coverage_percent":automatic.get("coverage_percent") if automatic.get("duration_seconds") else None,
            "duration_seconds":automatic.get("duration_seconds"),"processed_seconds":automatic.get("processed_seconds"),
            "confirmed_unassigned":sum(e.get("perspective") not in ("for","against") for e in verified),
            "candidate_unassigned":sum(e.get("perspective") not in ("for","against") for e in tentative),
            "scope":"no_full_match_claim"}
