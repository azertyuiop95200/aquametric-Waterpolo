"""Candidate game-clock exposure from observed continuous team lineups.

Intervals use descending regulation clock within one period, not video duration.
Complete lineup observations only. No interpolation across missing compositions;
an exclusion ends only when an observed state changes. No bench time inferred
from absence in a partial roster. Max period length is a validation bound.
"""
from collections import defaultdict, Counter
from math import isfinite

SIDES=("for","against")

def normalize_lineups(rows, segment, scene):
    if rows and scene not in {"water_polo","mixed"}:raise ValueError("Invalid scene")
    out=[]; start=float(segment["clip_start"]); end=float(segment["clip_end"])
    core_a=float(segment["start"]); core_b=float(segment["end"])
    if not start<=core_a<core_b<=end:raise ValueError("Invalid segment")
    for r in rows:
        if r.get("is_replay"):continue
        a,b=float(r["start_second"]),float(r["end_second"])
        if not (isfinite(a) and isfinite(b) and 0<=a<b<=end-start+1e-6):raise ValueError("Lineup outside clip")
        # A lineup may span a core boundary; keep its actual clock endpoints.
        # Never crop a clock interval by video interpolation. Clock union later.
        a,b=a+start,b+start
        if b<=core_a or a>=core_b:continue
        out.append({**r,"start_second":round(a,3),"end_second":round(b,3),"segment_index":segment["index"]})
    return out

def _caps(values, maximum):
    if not isinstance(values,list) or len(values)>maximum or any(type(x) is not int or not 1<=x<=30 for x in values) or len(set(values))!=len(values):raise ValueError("Invalid caps")
    return tuple(sorted(values))

def lineup_report(rows, *, max_period_seconds=480, periods=4, max_players=7):
    if not (isfinite(max_period_seconds) and 0<max_period_seconds<=480 and type(periods) is int and 1<=periods<=4 and type(max_players) is int and 1<=max_players<=7):raise ValueError("Invalid profile bounds")
    groups=defaultdict(list); rejected=0
    for r in rows:
        try:
            side=r["side"]; p=r["period"]; a,b,c,d,conf=map(float,(r["clock_start"],r["clock_end"],r["start_second"],r["end_second"],r["confidence"]))
            playing=_caps(r["in_play"],max_players); excluded=_caps(r.get("excluded",[]),30)
            if set(playing)&set(excluded):raise ValueError("Incompatible state")
            if side not in SIDES or type(p) is not int or not 1<=p<=periods or not all(isfinite(x) for x in (a,b,c,d,conf)) or not 0<=b<a<=max_period_seconds or not 0<=c<d or a-b>d-c+1. or not .65<=conf<=1 or r.get("is_replay") or r.get("conflict") or r.get("complete_lineup") is not True or not playing or not all(str(r.get(k) or "").strip() for k in ("clock_evidence","lineup_evidence","team_evidence")):raise ValueError("Unresolved lineup or clock")
            groups[(side,p)].append((b,a,playing,excluded))
        except (ValueError,TypeError,KeyError):rejected+=1
    teams={}; resolved={}
    for side in SIDES:
        play=Counter(); ex=Counter(); comps=Counter(); by_period=[]; total=conflict=player_seconds=0.; intervals=[]; per_player=defaultdict(Counter)
        for p in range(1,periods+1):
            rr=groups[side,p]; bounds=sorted({x for r in rr for x in r[:2]}); observed=bad=0.; pp=[]
            for lo,hi in zip(bounds,bounds[1:]):
                states={(r[2],r[3]) for r in rr if r[0]<=lo and r[1]>=hi}
                if not states:continue
                dt=hi-lo
                if len({s[0] for s in states})!=1:bad+=dt;continue
                caps=next(iter(states))[0]
                # Only explicitly supported exclusions on every overlapping row.
                excl=tuple(sorted(set.intersection(*(set(s[1]) for s in states))))
                observed+=dt;player_seconds+=dt*len(caps);comps[caps]+=dt
                for n in caps:play[n]+=dt;per_player[n][p]+=dt
                for n in excl:ex[n]+=dt
                item={"period":p,"clock_start":hi,"clock_end":lo,"in_play":list(caps),"excluded":list(excl),"seconds":round(dt,3)}
                pp.append(item);intervals.append(item)
            resolved[side,p]=pp;total+=observed;conflict+=bad
            if rr:by_period.append({"period":p,"observed_game_seconds":round(observed,3),"conflict_game_seconds":round(bad,3)})
        if abs(sum(play.values())-player_seconds)>1e-6:raise RuntimeError("Player time reconciliation failed")
        teams[side]={"observed_game_seconds":round(total,3) if total else None,"player_seconds":round(player_seconds,3) if total else None,"conflict_game_seconds":round(conflict,3),"periods":by_period,"players":[{"cap":n,"playing_seconds":round(play[n],3) if n in play else None,"excluded_seconds":round(ex[n],3) if n in ex else None,"periods":[{"period":p,"playing_seconds":round(v,3)} for p,v in sorted(per_player[n].items())]} for n in sorted(set(play)|set(ex))],"compositions":[{"caps":list(k),"seconds":round(v,3)} for k,v in comps.most_common()],"intervals":intervals}
    numerical=Counter()
    for p in range(1,periods+1):
        a,b=resolved["for",p],resolved["against",p]
        i=j=0
        while i<len(a) and j<len(b):
            x,y=a[i],b[j];lo=max(x["clock_end"],y["clock_end"]);hi=min(x["clock_start"],y["clock_start"])
            if hi>lo:numerical[(len(x["in_play"]),len(y["in_play"]))]+=hi-lo
            if x["clock_start"]<=y["clock_start"]:i+=1
            if y["clock_start"]<=x["clock_start"]:j+=1
    return {"scope":"candidate_game_clock_partial","profile":{"max_period_seconds":max_period_seconds,"periods":periods,"max_players":max_players},"rejected_intervals":rejected,"teams":teams,"simultaneous_game_seconds":round(sum(numerical.values()),3),"numerical_states":[{"for_players":a,"against_players":b,"seconds":round(v,3)} for (a,b),v in sorted(numerical.items())]}
