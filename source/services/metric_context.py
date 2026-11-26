"""Join reviewed metric tracks, spatially associated actions and bounded possessions.
Distances are planar head-position proxies; no full-match or ball-flight claim.
"""
from collections import defaultdict, Counter
from bisect import bisect_right
from math import hypot,atan2,degrees,isfinite

SIDES=("for","against")
SHOTS={"goal","shot_on_target","shot_off_target","shot_blocked","shot_unknown"}
PASSES={"pass_complete","assist","key_pass","bad_pass","pass_unknown"}

def _edge(r):
    try:v=tuple(float(r[k]) for k in ("start_second","end_second","x0","y0","x1","y1"))
    except (ValueError,TypeError,KeyError):return None
    return v if all(isfinite(x) for x in v) and 0<=v[0]<v[1] else None

def _position(e,t):
    a,b,x,y,X,Y=e;f=(t-a)/(b-a)
    return x+(X-x)*f,y+(Y-y)*f

def _time(e,field):
    p=e.get(field)
    if not isinstance(p,dict):return None
    t=p.get("second")
    return float(t) if type(t) in (float,int) and isfinite(t) and t>=0 else None

def _matched(e,role):
    d=e.get("spatial_attribution",{}).get(role,{})
    m=d.get("match")
    if d.get("status") not in {"new_candidate","corroborated"} or not isinstance(m,dict):return None
    n=e.get("cap_number" if role=="actor" else "receiver_cap_number")
    if e.get("side")!=m.get("side") or n!=m.get("cap_number"):return None
    return e["side"],n

class MetricIndex:
    def __init__(self,players,length,width):
        self.data={}
        duplicates=Counter((p.get("side"),p.get("cap_number")) for p in players)
        for p in players:
            k=(p.get("side"),p.get("cap_number"))
            if k[0] not in SIDES or type(k[1]) is not int or duplicates[k]!=1:continue
            rr=[_edge(r) for r in p.get("accepted_edges",[])]
            if any(r is None for r in rr):continue
            rr.sort()
            if any(b[0]<a[1]-1e-8 for a,b in zip(rr,rr[1:])):continue
            if any(not (0<=r[2]<=length and 0<=r[4]<=length and abs(r[3])<=width/2 and abs(r[5])<=width/2) for r in rr):continue
            self.data[k]=(rr,[r[0] for r in rr])
    def at(self,k,t):
        if k not in self.data or t is None:return None
        rr,starts=self.data[k];j=bisect_right(starts,t)-1
        if j<0 or t>rr[j][1]:return None
        p=_position(rr[j],t)
        if j>0 and abs(rr[j][0]-t)<1e-8 and abs(rr[j-1][1]-t)<1e-8 and hypot(*[a-b for a,b in zip(p,_position(rr[j-1],t))])>.25:return None
        return p
    def others(self,k,t):
        return [(q,p) for q in self.data if q!=k for p in [self.at(q,t)] if p is not None]

def event_geometry(events,players,*,length_m=25.,width_m=20.):
    if not all(isfinite(v) and v>0 for v in (length_m,width_m)):raise ValueError("Invalid field")
    ix=MetricIndex(players,length_m,width_m);rows=[];rejected=Counter();seen=set()
    for e in events:
        kind=e.get("event_type")
        if kind not in SHOTS|PASSES or not e.get("counted") or e.get("conflict") or e.get("is_replay"):continue
        key=e.get("key")
        if not key or key in seen:rejected["missing_or_duplicate_key"]+=1;continue
        seen.add(key);k=_matched(e,"actor");t=_time(e,"actor_position")
        p=ix.at(k,t)
        if p is None:rejected["actor_metric_unavailable"]+=1;continue
        x,y=p; others=ix.others(k,t)
        opp=[(hypot(x-a,y-b),q[1]) for q,(a,b) in others if q[0]!=k[0]]
        team=[hypot(x-a,y-b) for q,(a,b) in others if q[0]==k[0]]
        r={"key":key,"side":k[0],"cap":k[1],"kind":kind,"second":t,"x_m":round(x,3),"y_m":round(y,3),
           "opponents_measured":len(opp),"teammates_measured":len(team),
           "nearest_measured_opponent_m":round(min(opp)[0],3) if opp else None,
           "nearest_measured_opponent_cap":min(opp)[1] if opp else None,
           "measured_teammates_within_3m":sum(d<=3 for d in team) if team else None}
        if kind in SHOTS:
            # No attack direction inferred from cap or proximity.
            r["goal_geometry"]=[{"goal_x_m":g,"range_m":round(hypot(x-g,y),3),
                "opening_deg":round(degrees(atan2(3*abs(x-g),(x-g)**2+y*y-2.25)),2) if abs(x-g)>1e-8 else None} for g in (0.,length_m)]
        if kind in {"pass_complete","assist","key_pass"}:
            receiver=_matched(e,"receiver");u=_time(e,"receiver_position")
            q=ix.at(receiver,u) if receiver and receiver!=k and receiver[0]==k[0] and u is not None and t<=u<=t+12 else None
            if q is not None:
                X,Y=q;r.update(receiver_cap=receiver[1],receiver_x_m=round(X,3),receiver_y_m=round(Y,3),endpoint_separation_m=round(hypot(X-x,Y-y),3),observed_interval_s=round(u-t,3),longitudinal_delta_m=round(X-x,3),lateral_delta_m=round(Y-y,3))
            else:rejected["receiver_metric_unavailable"]+=1
        rows.append(r)
    def profile(rr):
        passes=[r["endpoint_separation_m"] for r in rr if "endpoint_separation_m" in r]
        gaps=[r["nearest_measured_opponent_m"] for r in rr if r["nearest_measured_opponent_m"] is not None]
        return {"located_actions":len(rr),"located_shots":sum(r["kind"] in SHOTS for r in rr),"located_pass_endpoints":len(passes),"mean_pass_endpoint_separation_m":round(sum(passes)/len(passes),3) if passes else None,"opponent_gap_samples":len(gaps),"mean_nearest_measured_opponent_m":round(sum(gaps)/len(gaps),3) if gaps else None}
    return {"scope":"partial_reviewed_geometry_candidate_actions","length_m":length_m,"width_m":width_m,"rows":rows,"rejected":dict(rejected),"teams":{s:profile([r for r in rows if r["side"]==s]) for s in SIDES},"players":[{"side":s,"cap":n,**profile([r for r in rows if (r["side"],r["cap"])==(s,n)])} for s,n in sorted({(r["side"],r["cap"]) for r in rows})]}

def phase_mobility(players,possessions,*,source_revision=None,possession_revision=None,length_m=25.,width_m=20.):
    if not source_revision or source_revision!=possession_revision:return {"scope":"source_unmatched","players":[],"teams":{}}
    spans=[]
    for r in possessions:
        a,b=r.get("start_second"),r.get("end_second");s=r.get("side")
        if type(a) not in (int,float) or type(b) not in (int,float) or not all(isfinite(v) for v in (a,b)) or not 0<=a<b or s not in SIDES:continue
        spans.append((a,b,s))
    spans.sort()
    if any(b[0]<a[1]-1e-8 for a,b in zip(spans,spans[1:])):return {"scope":"conflicting_possessions","players":[],"teams":{}}
    ix=MetricIndex(players,length_m,width_m);teams=defaultdict(Counter);out=[];starts=[a for a,b,s in spans]
    def display(c):
        return {k:{"seconds":round(c[k+"_s"],3),"distance_m":round(c[k+"_m"],3) if c[k+"_s"] else None,"mean_speed_m_s":round(c[k+"_m"]/c[k+"_s"],3) if c[k+"_s"] else None} for k in ("attack","defence","unknown","total")}
    for (side,n),(rr,_) in sorted(ix.data.items()):
        c=Counter()
        for a,b,x,y,X,Y in rr:
            dt=b-a;d=hypot(X-x,Y-y);used=0.
            j=max(0,bisect_right(starts,a)-1)
            while j<len(spans):
                lo,hi,s=spans[j];j+=1
                if lo>=b:break
                t=max(0.,min(hi,b)-max(lo,a))
                k="attack" if s==side else "defence";c[k+"_s"]+=t;c[k+"_m"]+=d*t/dt;used+=t
            t=max(0.,dt-used);c["unknown_s"]+=t;c["unknown_m"]+=d*t/dt;c["total_s"]+=dt;c["total_m"]+=d
        if not c["total_s"]:continue
        if abs(sum(c[k+"_m"] for k in ("attack","defence","unknown"))-c["total_m"])>1e-7:raise RuntimeError("Phase distance reconciliation failed")
        teams[side].update(c);out.append({"side":side,"cap":n,**display(c)})
    return {"scope":"partial_metric_video_time_candidate_possessions","players":out,"teams":{s:display(c) for s,c in teams.items()}}
