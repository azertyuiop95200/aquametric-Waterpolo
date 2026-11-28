"""Join candidate sporting events to observed game-clock lineups.
Not official plus/minus or match totals. Strictly interior clocks only: an event
at a substitution boundary cannot be attributed without finer evidence.
Rates describe detected events within observed lineup time, not true rates.
"""
from collections import Counter, defaultdict
from math import isfinite

SIDES=("for","against")
SHOTS={"goal","shot_on_target","shot_off_target","shot_blocked","shot_unknown"}
PASSES={"pass_complete","assist","key_pass","bad_pass","pass_unknown"}
METRICS={"goal":"goals","assist":"assists","interception":"interceptions","recovery":"recoveries",
         "turnover":"direct_turnovers","exclusion_earned":"exclusions_earned","exclusion_committed":"exclusions_committed",
         "save":"saves","block":"blocks","duel_won":"duels_won","duel_lost":"duels_lost"}

def _event_clock(e):
    p=e.get("period"); t=e.get("game_clock_seconds")
    if type(p) is not int or not 1<=p<=4 or type(t) not in (int,float) or not isfinite(t) or not 0<=t<=480 or not str(e.get("game_clock_evidence") or "").strip():return None
    return p,float(t)

def _rate(n,seconds):
    return round(60*n/seconds,3) if n and seconds>0 else None

def analyze_performance(events, lineups):
    by=defaultdict(list); players=defaultdict(Counter); comps=defaultdict(Counter)
    paired=defaultdict(Counter); states=defaultdict(Counter); ignored=Counter()
    for side in SIDES:
        for r in lineups.get("teams",{}).get(side,{}).get("intervals",[]):
            by[side,r["period"]].append(r)
            caps=tuple(r["in_play"]);dt=r["clock_start"]-r["clock_end"]
            comps[side,caps]["seconds"]+=dt
            for n in caps:players[side,n]["seconds"]+=dt
    def at(side,p,t):
        rr=[r for r in by[side,p] if r["clock_end"]<t<r["clock_start"]]
        if len(rr)==1:return tuple(rr[0]["in_play"])
        if rr:return None
        # The sweep may split a constant lineup at an overlap boundary.
        # An event on that boundary is valid only when both sides agree.
        before=[tuple(r["in_play"]) for r in by[side,p] if r["clock_start"]==t]
        after=[tuple(r["in_play"]) for r in by[side,p] if r["clock_end"]==t]
        return before[0] if len(before)==len(after)==1 and before[0]==after[0] else None
    # Matched exposure for comparing goal differential and numerical states.
    for p in range(1,5):
        a,b=by["for",p],by["against",p]
        a=sorted(a,key=lambda r:r["clock_end"]);b=sorted(b,key=lambda r:r["clock_end"]);i=j=0
        while i<len(a) and j<len(b):
            x,y=a[i],b[j];dt=min(x["clock_start"],y["clock_start"])-max(x["clock_end"],y["clock_end"])
            if dt>0:
                for side,r,other in (("for",x,y),("against",y,x)):
                    k=tuple(r["in_play"]);paired[side,k]["seconds"]+=dt
                    states[side,len(k),len(other["in_play"])]["seconds"]+=dt
                    for n in k:players[side,n]["paired_seconds"]+=dt
            if x["clock_start"]<=y["clock_start"]:i+=1
            if y["clock_start"]<=x["clock_start"]:j+=1
    seen=set()
    for e in events:
        kind=e.get("event_type")
        if kind not in SHOTS|PASSES|set(METRICS):continue
        if not e.get("counted") or e.get("conflict") or e.get("is_replay"):ignored["not_counted"]+=1;continue
        k=e.get("key")
        if not k or k in seen:ignored["missing_or_duplicate_key"]+=1;continue
        seen.add(k)
        tc=_event_clock(e);side=e.get("side")
        if tc is None or side not in SIDES or not e.get("team_evidence"):ignored["clock_or_team_missing"]+=1;continue
        p,t=tc;other=SIDES[1] if side==SIDES[0] else SIDES[0]
        caps=at(side,p,t);opp=at(other,p,t)
        if caps is None:ignored["lineup_gap_or_boundary"]+=1;continue
        n=e.get("cap_number");identified=type(n) is int and bool(e.get("identity_evidence"))
        if identified and n not in caps:ignored["actor_lineup_conflict"]+=1;continue
        names=[]
        if kind in SHOTS:names.append("shots")
        if kind=="shot_unknown":names.append("shots_unknown")
        if kind in PASSES:names.append("passes_attempted")
        if kind in {"pass_complete","assist","key_pass"}:names.append("passes_completed")
        if kind in METRICS:names.append(METRICS[kind])
        for name in names:
            comps[side,caps][name]+=1
            if identified:players[side,n][name]+=1
            if opp is not None:states[side,len(caps),len(opp)][name]+=1
        if kind in {"pass_complete","assist","key_pass"}:
            rec=e.get("receiver_cap_number")
            if type(rec) is int and rec in caps and rec!=n and e.get("receiver_evidence"):players[side,rec]["passes_received"]+=1
        if kind=="goal":
            if opp is None:ignored["goal_without_both_lineups"]+=1;continue
            for s,ks,label in ((side,caps,"goals_for"),(other,opp,"goals_against")):
                paired[s,ks][label]+=1
                for n in ks:players[s,n][label]+=1
    def view(c):
        return {k:c[k] for k in ("goals","shots","shots_unknown","passes_attempted","passes_completed","passes_received","assists","interceptions","recoveries","direct_turnovers","exclusions_earned","exclusions_committed","saves","blocks","duels_won","duels_lost")}
    def differential(c):
        return {"goals_for":c["goals_for"],"goals_against":c["goals_against"],"observed_goal_diff":c["goals_for"]-c["goals_against"] if c["goals_for"]+c["goals_against"] else None}
    out={}
    for side in SIDES:
        ps=[]; cs=[]; ns=[]
        for (s,n),c in sorted(players.items()):
            if s!=side:continue
            ps.append({"cap":n,"seconds":round(c["seconds"],3),"paired_seconds":round(c["paired_seconds"],3),**view(c),**differential(c),"goals_per_min":_rate(c["goals"],c["seconds"]),"shots_per_min":_rate(c["shots"],c["seconds"]),"passes_per_min":_rate(c["passes_attempted"],c["seconds"]),"receives_per_min":_rate(c["passes_received"],c["seconds"])})
        for (s,k),c in comps.items():
            if s!=side:continue
            d=paired[s,k]
            cs.append({"caps":list(k),"seconds":round(c["seconds"],3),"paired_seconds":round(d["seconds"],3),**view(c),**differential(d),"shots_per_min":_rate(c["shots"],c["seconds"])})
        for (s,a,b),c in sorted(states.items()):
            if s!=side:continue
            ns.append({"players":a,"opponents":b,"seconds":round(c["seconds"],3),**view(c),"goal_per_min":_rate(c["goals"],c["seconds"]),"goals_per_detected_shot_pct":round(100*c["goals"]/c["shots"],1) if c["shots"] and not c["shots_unknown"] else None})
        out[side]={"players":ps,"compositions":sorted(cs,key=lambda r:-r["seconds"]),"numerical":ns}
    return {"scope":"candidate_events_matched_to_partial_game_clock_exposure","teams":out,"excluded":dict(ignored),"note":"Detected-event rates, not validated match rates. Goal differential only on goals matched to both lineups. Numerical states include goalkeepers and are not possessions."}
