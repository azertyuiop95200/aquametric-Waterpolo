"""Evidence-bounded possession review (Q1 stages 2.3 v1/v2).
Generalized to any match, source and period; no Q1 evidence is injected into other matches.
Reviewed endpoint intervals are not automatically complete possessions or turnovers.
"""
from collections import Counter, defaultdict
from math import isfinite
from services.elite_performance import tags

CAUSE_GROUPS = {
    "shot": "goal shot_saved shot_blocked shot_post shot_crossbar shot_wide shot_unknown shot_non_goal",
    "penalty": "penalty_goal penalty_saved penalty_missed penalty_post penalty_violation",
    "officiating": "offensive_foul ball_under_water two_hands illegal_entry offside_goal_area impeding illegal_restart shot_clock_expired defensive_ordinary_foul defensive_exclusion penalty_awarded simultaneous_foul timeout_illegal misconduct other_foul",
    "technical": "pass_intercepted pass_inaccurate pass_into_water pass_dropped pass_deflected ball_stolen ball_lost_under_pressure unforced_loss bad_control ball_out dribble_lost ball_disputed",
    "unknown": "unknown",
    "restart": "corner goal_throw neutral_throw timeout period_start period_end post_goal_restart free_throw rebound keeper_recovery referee_correction",
}
CAUSES = {cause: family for family, items in CAUSE_GROUPS.items() for cause in items.split()}
ARBITRAL = {c for c, f in CAUSES.items() if f == "officiating"} | {"penalty_violation"}
TURNOVER = {"offensive_foul", "ball_under_water", "two_hands", "offside_goal_area", "illegal_restart", "shot_clock_expired", "penalty_violation", "pass_intercepted", "pass_inaccurate", "pass_dropped", "ball_stolen", "ball_lost_under_pressure", "unforced_loss", "bad_control", "ball_out", "dribble_lost"}
SIDES = {"for", "against"}

def validate(start, end, before, after, before_state, after_state, cause, cause_verified, decision_verified, exact, prior_shot, evidence, restart_award='unknown', restart_verified=False):
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and isfinite(v) for v in (start,end)) or not 0 <= start < end <= 43200:
        raise ValueError("Intervalle vidéo invalide.")
    for side, state in ((before,before_state),(after,after_state)):
        if side not in SIDES | {"unknown"} or state not in {"observed","apparent","unknown"} or (side=="unknown") != (state=="unknown"):
            raise ValueError("Équipe et niveau de preuve incompatibles.")
    if not evidence or not evidence.strip():
        raise ValueError("Décrire les preuves visibles.")
    if cause not in CAUSES or (cause_verified and cause=="unknown"):
        raise ValueError("Cause invalide.")
    if cause_verified and cause in ARBITRAL and not decision_verified:
        raise ValueError("Une cause arbitrale nécessite une décision identifiée.")
    if restart_award not in SIDES | {"unknown", "neutral"} or (restart_verified and (restart_award=="unknown" or not decision_verified)):
        raise ValueError("Reprise vérifiée : bénéficiaire et décision identifiés nécessaires.")
    if exact and not (before_state==after_state=="observed" and before!=after):
        raise ValueError("Transition unique : deux contrôles opposés observés sont nécessaires.")
    status = "unresolved"
    if before_state==after_state=="observed":
        status = "opposite_endpoints" if before!=after else "same_team_endpoints"
    elif before in SIDES and after in SIDES and before!=after:
        status = "probable_opposite_endpoints"
    credited = bool(exact and cause_verified)
    turnover = None
    if credited:
        if cause in TURNOVER: turnover=True
        elif CAUSES[cause] in {"shot","penalty"} and cause!="penalty_violation": turnover=False
    return dict(status=status, minimum_changes=1 if status=="opposite_endpoints" else None,
                exact_count=1 if exact else None, attributed_cause=cause if credited else None,
                turnover=turnover, prior_shot=prior_shot, video_duration_s=round(end-start,3),
                complete_possession=False, game_duration_s=None,
                restart_award=restart_award, restart_verified=bool(restart_verified))

def build_note(start, end, before, after, before_state, after_state, cause, cause_verified, decision_verified, exact, prior_shot, evidence, period, segment, restart_award="unknown", restart_verified=False):
    validate(start,end,before,after,before_state,after_state,cause,cause_verified,decision_verified,exact,prior_shot,evidence,restart_award,restart_verified)
    # Free text cannot introduce overriding tags; machine tags are last.
    safe = evidence.replace("="," : ").replace("|"," ").replace(";"," ")[:180]
    return (safe+" | "+" ".join([f"period={period}",f"p_source={segment or 'match'}",f"p_start={start:g}",
        f"p_before={before}",f"p_after={after}",f"p_bs={before_state}",f"p_as={after_state}",f"p_cause={cause}",
        f"p_cv={int(cause_verified)}",f"p_dv={int(decision_verified)}",f"p_exact={int(exact)}",f"p_prior={int(prior_shot)}",f"p_ra={restart_award}",f"p_rv={int(restart_verified)}"]))

def report(events):
    rows=[]; rejected=[]; groups=defaultdict(list)
    for e in events:
        if e.get("event_type")!="possession_transition" or str(e.get("confidence","")).upper() not in {"CONFIRMED","VERIFIED"}: continue
        t=tags(e)
        try:
            a=float(t["p_start"]); b=float(e["second"]); q=int(t["period"]); src=t["p_source"]
            if not 1<=q<=8 or not (src=="match" or src.isdecimal()): raise ValueError("source")
            note=(e.get("note") or "").split(" | ",1)[0]
            vals=validate(a,b,t["p_before"],t["p_after"],t["p_bs"],t["p_as"],t["p_cause"],t["p_cv"]=="1",t["p_dv"]=="1",t["p_exact"]=="1",t["p_prior"]=="1",note,t.get("p_ra","unknown"),t.get("p_rv")=="1")
            r=dict(id=e.get("id"),period=q,source=src,start_s=a,end_s=b,before=t["p_before"],after=t["p_after"],cause=t["p_cause"],evidence=note,**vals)
            groups[(src,q,a,b)].append(r)
        except (ValueError,TypeError,KeyError) as err:
            rejected.append(dict(id=e.get("id"),reason=str(err)))
    # Repeated windows never add counts; conflicting duplicates are excluded.
    for key, rr in groups.items():
        comparable=lambda r: tuple(r[k] for k in ("before","after","cause","status","exact_count","attributed_cause","turnover","prior_shot","restart_award","restart_verified"))
        if any(comparable(r)!=comparable(rr[0]) for r in rr[1:]):
            rejected.extend(dict(id=r["id"],reason="Annotations contradictoires") for r in rr)
            continue
        rows.append(rr[0])
        rejected.extend(dict(id=r["id"],reason="Fenêtre dupliquée") for r in rr[1:])
    by_source=defaultdict(list)
    for r in rows: by_source[(r["source"],r["period"])].append(r)
    bounds=[]
    for (src,q), rr in sorted(by_source.items()):
        last=-1; chosen=[]
        for r in sorted(rr,key=lambda r:r["end_s"]):
            if r["status"]=="opposite_endpoints" and not r["prior_shot"] and r["start_s"]>=last:
                chosen.append(r);last=r["end_s"]
        bounds.append(dict(source=src,period=q,lower_bound=len(chosen),interval_ids=[r["id"] for r in chosen]))
    return dict(rows=sorted(rows,key=lambda r:(r["period"],r["source"],r["start_s"])),rejected=rejected,
                statuses=dict(Counter(r["status"] for r in rows)),bounds=bounds,causes=CAUSES,
                exact_total_changes=None,complete_possessions=None,turnover_rate=None,game_duration_s=None,
                note="Référence partielle. Bornes par source, non additionnables entre vidéos. Aucune attribution à partir d'une simple vue ultérieure.")
