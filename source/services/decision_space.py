"""Static planar decision support, not counterfactual prediction.
All player positions are projected head proxies at a common instant.
No claim of pass availability, actual interception or expected goals.
"""
from math import hypot,atan2,degrees,isfinite
from collections import Counter
from services.metric_context import MetricIndex,_matched,_time

def gap(a,b,q):
    dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
    if den<=1e-12:return hypot(q[0]-a[0],q[1]-a[1])
    u=max(0.,min(1.,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/den))
    return hypot(q[0]-a[0]-u*dx,q[1]-a[1]-u*dy)

def minimum(a,b,opponents):
    return min((gap(a,b,q) for q in opponents),default=None)

def geometry(p,g,goal_width=3.):
    x,y=p;h=goal_width/2;d=abs(x-g)
    return {"range_m":hypot(d,y),"angle_deg":degrees(atan2(goal_width*d,d*d+y*y-h*h)) if d>1e-8 else None}

def scene_options(actor,teammates,opponents,goal_x,*,radius=.6,goal_width=3.):
    """teammates = [(id,(x,y))]; opponents = [(x,y)].
    Screen sampled straight water-plane lines against fixed disks.
    Radius is an engineering scenario, not measured reach.
    """
    if not all(isfinite(x) and x>0 for x in (radius,goal_width)):raise ValueError("Invalid scenario")
    def shot(p):
        r=geometry(p,goal_x,goal_width)
        targets=[-goal_width/2+goal_width*(i+.5)/15 for i in range(15)]
        lanes=[minimum(p,(goal_x,y),opponents) for y in targets]
        r["sampled_unobstructed_fraction"]=sum(v>radius for v in lanes)/len(lanes) if opponents and r["angle_deg"] is not None else None
        return r
    base=shot(actor)
    out=[]
    for n,p in teammates:
        if hypot(p[0]-actor[0],p[1]-actor[1])<1e-6:continue
        r=shot(p);d=minimum(actor,p,opponents)
        near=min((hypot(p[0]-q[0],p[1]-q[1]) for q in opponents),default=None)
        r.update(id=n,x=p[0],y=p[1],pass_separation_m=hypot(p[0]-actor[0],p[1]-actor[1]),
                 lane_min_gap_m=d,receiver_min_gap_m=near,
                 range_gain_m=base["range_m"]-r["range_m"],
                 angle_gain_deg=r["angle_deg"]-base["angle_deg"] if r["angle_deg"] is not None and base["angle_deg"] is not None else None,
                 longitudinal_gain_m=abs(actor[0]-goal_x)-abs(p[0]-goal_x),
                 lane_scenario=("near_measured_defender" if d<=radius else "no_measured_defender_within_radius") if d is not None else "unknown")
        out.append(r)
    # Pareto flags compare geometric alternatives only, not success likelihood.
    def dominates(a,b):
        keys=("range_gain_m","angle_gain_deg","lane_min_gap_m","receiver_min_gap_m","sampled_unobstructed_fraction")
        if any(a[k] is None or b[k] is None for k in keys):return False
        return all(a[k]>=b[k]-1e-8 for k in keys) and any(a[k]>b[k]+1e-8 for k in keys)
    for r in out:r["pareto_candidate"]=bool(opponents and all(r[k] is not None for k in ("angle_gain_deg","sampled_unobstructed_fraction")) and not any(dominates(o,r) for o in out if o is not r))
    return {"goal_x":goal_x,"actor_shot":base,"alternatives":out,"radius_m":radius,"goal_width_m":goal_width,"opponent_count":len(opponents),"scope":"static_planar_scenario"}

def decision_report(events,players,*,length_m=25.,width_m=20.):
    ix=MetricIndex(players,length_m,width_m);rows=[];seen=set();rejected=Counter()
    for e in events:
        if e.get("event_type") not in {"shot_on_target","shot_off_target","shot_blocked","shot_unknown","bad_pass","pass_unknown","goal","pass_complete","assist","key_pass"} or not e.get("counted") or e.get("conflict") or e.get("is_replay"):continue
        key=e.get("key")
        if not key or key in seen:continue
        seen.add(key);k=_matched(e,"actor");t=_time(e,"actor_position");p=ix.at(k,t)
        if p is None:rejected["no_actor_metric"]+=1;continue
        # Include only simultaneous measurements; never borrow later positions.
        others=ix.others(k,t);mates=[(q[1],v) for q,v in others if q[0]==k[0]];opp=[v for q,v in others if q[0]!=k[0]]
        points=[{"side":k[0],"cap":k[1],"x":p[0],"y":p[1],"actor":True}]+[{"side":q[0],"cap":q[1],"x":v[0],"y":v[1],"actor":False} for q,v in others]
        # Attack direction not independently established by current global metric map.
        scenarios=[scene_options(p,mates,opp,g) for g in (0.,length_m)]
        rows.append({"key":key,"side":k[0],"cap":k[1],"second":t,"kind":e["event_type"],"shot_clock_seconds":e.get("shot_clock_seconds"),"points":points,"scenarios":scenarios,"direction_verified":False,"coverage":"partial_visible_players","failed_pass_target_known":False})
    return {"scope":"candidate_static_decision_support","length_m":length_m,"width_m":width_m,"rows":rows,"rejected":dict(rejected)}
