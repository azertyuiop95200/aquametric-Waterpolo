"""Execution timing from corroborated action identities and visible control.
All times are source-video seconds. Visible lead-up is not necessarily total
control. Reception-to-release requires independently associated reception and
continuous control from that reception to the release, within timing tolerance.
"""
from collections import defaultdict, Counter
from bisect import bisect_right
from math import isfinite

RELEASES={"goal","shot_on_target","shot_off_target","shot_blocked","shot_unknown","pass_complete","assist","key_pass","bad_pass","pass_unknown"}
SUCCESS={"pass_complete","assist","key_pass"}

def stamp(e,key):
    p=e.get(key)
    if not isinstance(p,dict):return None
    t=p.get("second")
    return float(t) if type(t) in (float,int) and isfinite(t) and t>=0 else None

def identity(e,role):
    d=e.get("spatial_attribution",{}).get(role,{})
    m=d.get("match")
    n=e.get("cap_number" if role=="actor" else "receiver_cap_number")
    if d.get("status") in {"new_candidate","corroborated"} and isinstance(m,dict) and e.get("side") in ("for","against") and m.get("side")==e["side"] and type(n) is int and n==m.get("cap_number"):return e["side"],n
    return None

def execution_report(events,control,*,source_revision=None,tolerance=.15):
    if not source_revision or source_revision!=control.get("source_revision"):
        return {"scope":"source_unmatched","players":[],"teams":{},"rows":[]}
    if not isfinite(tolerance) or not 0<tolerance<=.25:raise ValueError("Invalid timing tolerance")
    spans=[]; rejected=Counter()
    for r in control.get("intervals",[]):
        a,b=r.get("start_second"),r.get("end_second")
        if type(a) not in (int,float) or type(b) not in (int,float) or not all(isfinite(x) for x in (a,b)) or not 0<=a<b:
            return {"scope":"invalid_control","players":[],"teams":{},"rows":[]}
        k=(r.get("side"),r.get("cap_number")) if r.get("status")=="identified" and r.get("side") in ("for","against") and type(r.get("cap_number")) is int else None
        spans.append((a,b,k))
    spans.sort(key=lambda r:r[:2])
    if any(b[0]<a[1]-1e-8 for a,b in zip(spans,spans[1:])):
        return {"scope":"conflicting_control","players":[],"teams":{},"rows":[]}
    starts=[s[0] for s in spans]
    valid=[];seen=set();receipts=defaultdict(list)
    for e in events:
        k=e.get("key")
        if not e.get("counted") or e.get("conflict") or e.get("is_replay") or e.get("event_type") not in RELEASES:continue
        if not k or k in seen:rejected["missing_or_duplicate_key"]+=1;continue
        seen.add(k);who=identity(e,"actor");t=stamp(e,"actor_position")
        if who is None or t is None:continue
        valid.append((t,e,who))
        if e["event_type"] in SUCCESS:
            dest=identity(e,"receiver");u=stamp(e,"receiver_position")
            if dest and dest!=who and dest[0]==who[0] and u is not None and t<=u<=t+12:receipts[dest].append((u,k))
    for k in receipts:receipts[k].sort()
    # Other observed releases by the same athlete invalidate a continuous
    # individual control link, even if the provider labelled one long span.
    releases=defaultdict(list)
    for t,e,k in valid:releases[k].append(t)
    for k in releases:releases[k].sort()
    rows=[]
    for t,e,k in sorted(valid,key=lambda r:r[0]):
        j=bisect_right(starts,t)-1
        # If a new control span starts exactly at the release, only the
        # preceding span can establish lead-up.
        if j>=0 and abs(starts[j]-t)<1e-8:j-=1
        if j<0:rejected["no_control"]+=1;continue
        a,b,who=spans[j]
        if who!=k or abs(b-t)>tolerance+1e-8 or t<=a:
            rejected["no_matching_control_end"]+=1;continue
        if any(a+1e-8<v<t-1e-8 for v in releases[k]):
            rejected["intervening_release"]+=1;continue
        observed=min(t,b)-a
        if observed<=0:continue
        rr=[(u,key) for u,key in receipts[k] if key!=e["key"] and abs(u-a)<=tolerance+1e-8 and u<t]
        exact=None
        if len(rr)==1:
            u,key=rr[0]
            if not any(u+1e-8<v<t-1e-8 for v in releases[k]):exact=t-u
        rows.append({"key":e["key"],"side":k[0],"cap":k[1],"kind":e["event_type"],"release_second":t,"visible_control_before_release_s":round(observed,3),"reception_to_release_s":round(exact,3) if exact is not None else None,"receipt_key":rr[0][1] if exact is not None else None})
    def profile(rr):
        def avg(v):return round(sum(v)/len(v),3) if v else None
        out={}
        for label,subset in (("pass",[r for r in rr if r["kind"] in {"pass_complete","assist","key_pass","bad_pass","pass_unknown"}]),("shot",[r for r in rr if r["kind"] not in {"pass_complete","assist","key_pass","bad_pass","pass_unknown"}])):
            exact=[r["reception_to_release_s"] for r in subset if r["reception_to_release_s"] is not None]
            out[label]={"control_samples":len(subset),"mean_visible_control_s":avg([r["visible_control_before_release_s"] for r in subset]),"reception_samples":len(exact),"mean_reception_to_release_s":avg(exact)}
        return out
    return {"scope":"partial_candidate_video_execution","tolerance_s":tolerance,"rows":rows,"rejected":dict(rejected),"teams":{s:profile([r for r in rows if r["side"]==s]) for s in ("for","against")},"players":[{"side":s,"cap":n,**profile([r for r in rows if (r["side"],r["cap"])==(s,n)])} for s,n in sorted({(r["side"],r["cap"]) for r in rows})]}
