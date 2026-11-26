"""Intersect reviewed metric edges with observed control intervals.
No claim of off-ball movement during unobserved control; source time must match.
Distances use proportional clipping inside accepted measured edges only.
"""
from collections import defaultdict
from math import hypot,isfinite

def control_mobility(players,control,*,source_revision=None,control_revision=None):
    if not source_revision or source_revision!=control_revision:
        return {"scope":"source_unmatched","players":[],"teams":{}}
    intervals=[]
    for r in control.get("intervals",[]):
        try:a,b=float(r["start_second"]),float(r["end_second"])
        except (ValueError,TypeError,KeyError):continue
        if not (isfinite(a) and isfinite(b) and 0<=a<b):continue
        s,n=r.get("side"),r.get("cap_number")
        intervals.append((a,b,s,n,r.get("status")))
    intervals.sort()
    if any(b[0]<a[1]-1e-8 for a,b in zip(intervals,intervals[1:])):
        return {"scope":"conflicting_control_intervals","players":[],"teams":{}}
    rows=[];teams=defaultdict(lambda:defaultdict(float))
    for p in players:
        side,n=p.get("side"),p.get("cap_number")
        if side not in ("for","against") or type(n) is not int:continue
        sums=defaultdict(float); last=-1.
        for e in sorted(p.get("accepted_edges",[]),key=lambda q:q["start_second"]):
            try:a,b,x,y,X,Y=map(float,(e["start_second"],e["end_second"],e["x0"],e["y0"],e["x1"],e["y1"]))
            except (ValueError,TypeError,KeyError):continue
            if not all(isfinite(v) for v in (a,b,x,y,X,Y)) or not 0<=a<b or a<last-1e-8:
                return {"scope":"invalid_metric_edges","players":[],"teams":{}}
            last=b; d=hypot(X-x,Y-y);dt=b-a;used=0.
            for lo,hi,s,cap,status in intervals:
                if lo>=b:break
                sec=max(0.,min(b,hi)-max(a,lo))
                if not sec:continue
                if status=="identified" and s==side and cap==n:kind="with_ball"
                elif status=="identified" and s in ("for","against") and (s,cap)!=(side,n):kind="other_controller"
                else:kind="unknown_control"
                sums[kind+"_seconds"]+=sec;sums[kind+"_m"]+=d*sec/dt;used+=sec
            rest=max(0.,dt-used);sums["unknown_control_seconds"]+=rest;sums["unknown_control_m"]+=d*rest/dt
            sums["measured_seconds"]+=dt;sums["measured_m"]+=d
        if not sums["measured_seconds"]:continue
        if abs(sum(sums[k+"_m"] for k in ("with_ball","other_controller","unknown_control"))-sums["measured_m"])>1e-7:raise RuntimeError("Distance partition failed")
        for k,v in sums.items():teams[side][k]+=v
        def display(d):
            out={}
            for k in ("with_ball","other_controller","unknown_control","measured"):
                t=d[k+"_seconds"];out[k+"_seconds"]=round(t,3);out[k+"_m"]=round(d[k+"_m"],2) if t else None
                out[k+"_speed_m_s"]=round(d[k+"_m"]/t,3) if t else None
            return out
        rows.append({"side":side,"cap":n,**display(sums)})
    return {"scope":"partial_reviewed_metric_candidate_control","players":rows,"teams":{s:display(d) for s,d in teams.items()}}
