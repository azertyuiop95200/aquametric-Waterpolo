"""Conservative complete-possession sample: explicit bounds in continuous visible cores.
No inference from isolated shots, timeouts, rebounds or a score increment.
"""
from collections import Counter, defaultdict
from math import isfinite

SIDES=("for","against")
OUTCOMES={"goal","save","off_target","post","blocked","bad_pass","steal","offensive_foul","shot_clock","handling","period_end","unknown"}
SHOTS={"goal","shot_on_target","shot_off_target","shot_blocked","shot_unknown"}
PASSES={"pass_complete","assist","key_pass","bad_pass","pass_unknown"}

def complete_possessions(events, segments, lineups):
    by=defaultdict(list)
    # Merge only exactly adjacent, fully visible cores. Missing or limited
    # segments break a chain; old records without bounds stay independent.
    groups={}; last_end=None; group=None
    for seg in sorted(segments,key=lambda v:v["index"]):
        payload=seg.get("result",{})
        visible=(seg.get("status")=="complete" and payload.get("scene")=="water_polo"
                 and any(v.get("family")=="possessions" and v.get("status")=="visible" for v in payload.get("observability",[]))
                 and not any(v.get("family")=="possessions" and v.get("status")!="visible" for v in payload.get("observability",[])))
        a,b=seg.get("start"),seg.get("end")
        bounded=type(a) in (float,int) and type(b) in (float,int) and isfinite(a) and isfinite(b) and 0<=a<b
        if not visible:
            last_end=None;group=None;continue
        if not bounded or last_end is None or abs(a-last_end)>1e-6:
            group=seg["index"]
        groups[seg["index"]]=(group,a,b) if bounded else (group,None,None)
        last_end=b if bounded else None
    for e in events:
        idx=e.get("segment_index")
        if idx not in groups:continue
        g,a,b=groups[idx];t=e.get("second")
        if type(t) not in (int,float) or not isfinite(t) or (a is not None and not a<=t<b):continue
        # A conflicting or replay observation must not silently become
        # positive evidence. Keep it as a boundary barrier when relevant.
        if e.get("is_replay") or e.get("conflict"):
            by[g].append({**e,"event_type":"_barrier"})
        elif e.get("counted") is True:
            by[g].append(e)
    rejected=Counter(); candidates=[]
    def clock(e):
        v=e.get("game_clock_seconds")
        return float(v) if type(v) in (float,int) and isfinite(v) and 0<=v<=480 and e.get("game_clock_evidence") else None
    for i,rr in by.items():
        start=None
        for e in sorted(rr,key=lambda a:a["second"]):
            kind=e.get("event_type")
            if kind=="_barrier":
                if start is not None:rejected["interrupted"]+=1
                start=None;continue
            if start is not None and e.get("period") is not None and e.get("period")!=start.get("period"):
                rejected["period_change"]+=1;start=None
            if kind=="possession_start":
                if start is not None:rejected["unclosed_start"]+=1
                start=e if e.get("side") in SIDES and e.get("team_evidence") else None
            elif kind=="possession_end":
                if start is None:rejected["unpaired_end"]+=1;continue
                a=start;start=None
                p=a.get("period");ca,cb=clock(a),clock(e);sa,sb=a["second"],e["second"]
                if a["side"]!=e.get("side") or not e.get("team_evidence") or type(p) is not int or not 1<=p<=4 or p!=e.get("period") or ca is None or cb is None or not 0<=cb<ca or not 0<sb-sa or ca-cb>sb-sa+1:
                    rejected["inconsistent_bounds"]+=1;continue
                inner=[x for x in rr if sa<=x["second"]<=sb and x.get("event_type") in SHOTS|PASSES]
                if any(x.get("side")!=a["side"] for x in inner):
                    rejected["opposing_or_unknown_actions"]+=1;continue
                outcome=e.get("possession_outcome","unknown")
                if outcome not in OUTCOMES:outcome="unknown"
                goals=sum(x["event_type"]=="goal" for x in inner)
                if (outcome=="goal" and goals!=1) or (outcome!="goal" and goals):
                    rejected["goal_outcome_conflict"]+=1;continue
                candidates.append({"side":a["side"],"period":p,"start_second":sa,"end_second":sb,"clock_start":ca,"clock_end":cb,"game_seconds":ca-cb,"outcome":outcome,"shots":sum(x["event_type"] in SHOTS for x in inner),"passes":sum(x["event_type"] in PASSES for x in inner)})
        if start is not None:rejected["unclosed_start"]+=1
    # Core segments normally do not overlap. Reject all contradictory overlapping
    # candidate possessions rather than picking the most flattering result.
    bad=set()
    for i,a in enumerate(candidates):
        for j in range(i+1,len(candidates)):
            b=candidates[j]
            if a["period"]==b["period"] and min(a["clock_start"],b["clock_start"])>max(a["clock_end"],b["clock_end"]):
                bad.update((i,j))
    rejected["overlapping_possessions"]+=len(bad)
    rows=[r for i,r in enumerate(candidates) if i not in bad]
    def constant_count(side,r):
        spans=sorted((x for x in lineups.get("teams",{}).get(side,{}).get("intervals",[]) if x["period"]==r["period"] and min(x["clock_start"],r["clock_start"])>max(x["clock_end"],r["clock_end"])),key=lambda x:x["clock_end"])
        cursor=r["clock_end"]; counts=set()
        for x in spans:
            lo=max(x["clock_end"],r["clock_end"]);hi=min(x["clock_start"],r["clock_start"])
            if abs(lo-cursor)>1e-6:return None
            counts.add(len(x["in_play"]));cursor=hi
        return next(iter(counts)) if len(counts)==1 and abs(cursor-r["clock_start"])<=1e-6 else None
    for r in rows:
        other="against" if r["side"]=="for" else "for"
        a,b=constant_count(r["side"],r),constant_count(other,r)
        r["numerical_state"]=("advantage" if a>b else "disadvantage" if a<b else "equal") if a is not None and b is not None else "unresolved_or_changing"
    def stats(rr):
        n=len(rr);c=Counter(r["outcome"] for r in rr);known=n-c["unknown"]
        return {"possessions":n if n else None,"goals":c["goal"] if n else None,"unresolved_outcomes":c["unknown"] if n else None,
                "goal_pct":round(100*c["goal"]/n,1) if n and known==n else None,
                "mean_game_seconds":round(sum(r["game_seconds"] for r in rr)/n,2) if n else None,
                "detected_passes_per_possession":round(sum(r["passes"] for r in rr)/n,2) if n else None,
                "detected_shots_per_possession":round(sum(r["shots"] for r in rr)/n,2) if n else None,
                "outcomes":dict(c)}
    teams={}
    for s in SIDES:
        rr=[r for r in rows if r["side"]==s]
        teams[s]={"overall":stats(rr),"numerical":{k:stats([r for r in rr if r["numerical_state"]==k]) for k in ("equal","advantage","disadvantage","unresolved_or_changing")}}
    return {"scope":"complete_observed_candidate_possessions_only","teams":teams,"rejected":dict(rejected),"rows":rows}
