"""Derived indicators with explicit prerequisites, coverage and traceable events."""
from collections import defaultdict, Counter
from math import isfinite
from services.elite_performance import tags, clock, END_LABELS

SHOTS={"goal","shot_on_target","shot_off_target","shot_blocked","shot_unknown"}
PASS_OK={"pass_complete","key_pass","assist"}
PASS_ALL=PASS_OK|{"bad_pass"}

def numeric(value,lo=0,hi=100000):
    try:
        v=float(value)
        return v if isfinite(v) and lo<=v<=hi else None
    except (ValueError,TypeError):return None

def metric(value,n,unit,requirement,ids=()):
    return {"value":value,"n":n,"unit":unit,"requirement":requirement,
            "state":"derived_sample" if value is not None else "not_measured",
            "event_ids":[i for i in ids if i is not None]}

def complete_possessions(rows):
    groups=defaultdict(list)
    for e in rows:
        t=tags(e);p=t.get("possession") or t.get("possession_id")
        q=t.get("period")
        if p and q in {"1","2","3","4"}:
            groups[(e.get("match_id"),e.get("perspective"),q,p)].append(e)
    completed=[];rejected=0
    for (_,side,q,p),seq in groups.items():
        starts=[e for e in seq if e.get("event_type")=="possession_start"]
        ends=[e for e in seq if e.get("event_type")=="possession_end"]
        if len(starts)!=1 or len(ends)!=1:rejected+=1;continue
        a,b=clock(starts[0]),clock(ends[0]); outcome=tags(ends[0]).get("outcome")
        if a is None or b is None or a[0]!=b[0] or a[1]<b[1] or outcome not in END_LABELS or outcome=="unknown":
            rejected+=1;continue
        # All sport actions must have the same valid clock and fall within boundaries.
        if any(clock(e) is None or clock(e)[0]!=a[0] or not b[1]<=clock(e)[1]<=a[1] for e in seq):
            rejected+=1;continue
        completed.append(dict(side=side,period=int(q),possession=p,seconds=round(a[1]-b[1],3),
                             outcome=outcome,phase=starts[0].get("phase") or "auto",
                             event_ids=[e.get("id") for e in seq],start_id=starts[0].get("id"),
                             end_id=ends[0].get("id"),passes=sum(e.get("event_type") in PASS_ALL for e in seq),
                             pass_coverage=tags(ends[0]).get("passes_complete")=="yes"))
    return completed,rejected

def pass_network(rows,valid_ids):
    pairs=defaultdict(list); seen=set(); rejected=0
    for e in rows:
        if e.get("event_type") not in PASS_OK:continue
        t=tags(e);pid=e.get("player_id")
        try: receiver=int(t.get("receiver_id",""))
        except (TypeError,ValueError):rejected+=1;continue
        # No self-pass, no cross-side link and no duplicate physical action ID.
        if pid is None or pid==receiver or receiver not in valid_ids or pid not in valid_ids:
            rejected+=1;continue
        uid=t.get("action_id")
        if uid:
            key=(e.get("match_id"),e.get("perspective"),t.get("period"),uid)
            if key in seen:continue
            seen.add(key)
        else:
            rejected+=1;continue
        pairs[(pid,receiver)].append(e.get("id"))
    return {"edges":[{"from_id":a,"to_id":b,"count":len(ids),"event_ids":ids} for (a,b),ids in sorted(pairs.items())],
            "rejected_or_unlinked":rejected,"scope":"explicit_completed_pass_ids"}

def tsap(rows):
    # TSAP categories must be explicitly classified, never inferred from ordinary event labels.
    count=Counter();seen=set();ids=[]
    for e in rows:
        t=tags(e);cat=t.get("tsap");uid=t.get("action_id")
        if cat not in {"rb","cb","nb","lb","ob","ss"} or not uid:continue
        key=(e.get("match_id"),e.get("perspective"),t.get("period"),uid,cat)
        if key in seen:continue
        seen.add(key);count[cat]+=1;ids.append(e.get("id"))
    n=sum(count.values());complete=bool(n) and any(tags(e).get("tsap_coverage")=="complete" for e in rows)
    # A complete assertion applies to the explicitly reviewed sample, not the whole match.
    vp=count["rb"]+count["cb"] if complete else None
    ei=(count["ob"]+count["ss"])/(10+count["lb"]) if complete else None
    return {"counts":dict(count),"sample":n,"complete_annotation_asserted":complete,
            "volume_play":vp,"efficiency_index":round(ei,3) if ei is not None else None,
            "performance_score":round(vp/2+ei*10,3) if vp is not None else None,
            "event_ids":ids,"source":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10532484/"}

METRIC_SPEC={"shot_speed_kmh":(SHOTS,0,180,"km/h"),"release_time_s":(SHOTS,0,10,"s"),
          "shot_distance_m":(SHOTS,0,40,"m"),"shot_release_height_m":(SHOTS,0,3,"m"),
          "shot_horizontal_angle_deg":(SHOTS,0,180,"°"),"shot_vertical_angle_deg":(SHOTS,0,180,"°"),
          "pass_distance_m":(PASS_ALL,0,40,"m"),"pass_speed_kmh":(PASS_ALL,0,180,"km/h"),
          "sprint_5m_s":({"sprint"},0,30,"s"),"sprint_10m_s":({"sprint"},0,60,"s"),
          "max_swim_speed_mps":({"sprint","distance_sample"},0,5,"m/s")}
def observed_numeric(rows):
    out={}
    for key,(types,lo,hi,unit) in METRIC_SPEC.items():
        vals=[];ids=[]
        for e in rows:
            if e.get("event_type") not in types:continue
            t=tags(e)
            if t.get("measurement") not in {"calibrated","verified_metric"}:continue
            v=numeric(t.get(key) if key in t else t.get("distance_m") if key=="shot_distance_m" else None,lo,hi)
            if v is not None:vals.append(v);ids.append(e.get("id"))
        out[key]={"mean":metric(round(sum(vals)/len(vals),3) if vals else None,len(vals),unit,"mesure calibrée explicitement renseignée",ids),
                  "max":metric(max(vals) if vals else None,len(vals),unit,"mesure calibrée explicitement renseignée",ids)}
    return out

def advanced_report(events,roster):
    rows=[e for e in events if str(e.get("confidence") or "").upper() in {"CONFIRMED","VERIFIED"}]
    sides={}
    players=[]
    for side in ("for","against"):
        rr=[e for e in rows if e.get("perspective")==side]
        poss,rejected=complete_possessions(rr)
        n=len(poss);ids=[e for p in poss for e in p["event_ids"]]
        pass_poss=[p for p in poss if p["pass_coverage"]]
        side_ids={e["player_id"] for e in rr if e.get("player_id") is not None}
        if side=="for":side_ids|={p["id"] for p in roster}
        sides[side]={
            "possessions":poss,"incomplete_possession_groups":rejected,
            "goals_per_possession":metric(round(sum(p["outcome"]=="goal" for p in poss)/n,3) if n else None,n,"but/possession","possessions appariées, classées et horodatées",ids),
            "possession_duration":metric(round(sum(p["seconds"] for p in poss)/n,3) if n else None,n,"s","horloge de jeu, début et fin appariés",ids),
            "passes_per_possession":metric(round(sum(p["passes"] for p in pass_poss)/len(pass_poss),3) if pass_poss else None,len(pass_poss),"passes/possession","annotation exhaustive des passes de la possession déclarée",ids),
            "pass_network":pass_network(rr,side_ids),"numeric":observed_numeric(rr)}
        for pid in sorted(side_ids):
            pr=[e for e in rr if e.get("player_id")==pid]
            name=next((p["name"] for p in roster if p["id"]==pid and side=="for"),None) or next((e.get("player") for e in pr if e.get("player")),None) or "Non nommée"
            players.append(dict(side=side,player_id=pid,name=name,tsap=tsap(pr),numeric=observed_numeric(pr)))
    return {"scope":"confirmed_annotation_sample","sides":sides,"players":players}
