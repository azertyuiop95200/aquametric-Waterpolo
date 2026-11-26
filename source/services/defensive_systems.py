"""Goal-relative geometry. Thresholds are provisional engineering defaults.
Tactical roles 1..5 are reviewed perimeter matchups, 6 is the centre.
Never confuse a tactical role with a cap number.
"""
from math import hypot,isfinite
from collections import Counter,defaultdict

def dist(a,b):
    return hypot(a["x"]-b["x"],a["y"]-b["y"])
def local_features(attack,defence,carrier=None,centre=None):
    nearest=[{"attacker":p["id"],"defender":q["id"],"gap_m":round(dist(p,q),2)}
             for p in attack if defence for q in [min(defence,key=lambda q:dist(p,q))]]
    ball=next((p for p in attack if p["id"]==carrier),None)
    c=next((p for p in attack if p["id"]==centre),None)
    return {"attack_visible":len(attack),"defence_visible":len(defence),"nearest":nearest,
            "close_pairs":sum(x["gap_m"]<=1.5 for x in nearest),
            "centre_cover":sum(dist(c,q)<=2 for q in defence) if c else None,
            "carrier_cover":sum(dist(ball,q)<=1.5 for q in defence) if ball else None,
            "defensive_width_m":round(max(p["y"] for p in defence)-min(p["y"] for p in defence),2) if len(defence)>1 else None,
            "defensive_depth_m":round(max(p["x"] for p in defence)-min(p["x"] for p in defence),2) if len(defence)>1 else None}

def classify_frame(attack,defence,even_verified=False,carrier=None):
    ar={p.get("role"):p for p in attack};dr={p.get("role"):p for p in defence}
    c=ar.get(6)
    r=local_features(attack,defence,carrier,c["id"] if c else None)
    r.update(system="unknown",drops=[],splits=[])
    if not even_verified or len(attack)!=6 or len(defence)!=6 or set(ar)!=set(range(1,7)) or set(dr)!=set(range(1,7)):return r
    if len({p["id"] for p in attack})!=6 or len({p["id"] for p in defence})!=6:return r
    drops=[];splits=[];marks=[]
    for k in range(1,6):
        p,q=ar[k],dr[k];gap=dist(p,q)
        if gap<=1.5:marks.append(k)
        elif dist(q,c)<=2 and gap>=1.8:drops.append(k)
        elif 1.5<gap<=3.8 and any(1.2<=dist(q,ar[j])<=3.8 for j in (k-1,k+1) if 1<=j<=5):splits.append(k)
    central=dist(c,dr[6])<=1.8
    system="unknown"
    if central and len(marks)==5:system="press"
    elif central and carrier!=c["id"] and (r["carrier_cover"] or 0)>=2:system="trap"
    elif central and drops==[3] and 2 in splits and 4 in splits:system="zone_m"
    elif central and drops==[2,3,4]:system="zone_234"
    elif central and drops and set(drops)<={1,2} and not splits:system="zone_12"
    elif central and drops and set(drops)<={4,5} and not splits:system="zone_45"
    elif central and drops:system="mixed"
    r.update(system=system,drops=drops,splits=splits)
    return r

def classify_window(frames):
    frames=sorted(frames,key=lambda f:f["second"])
    samples=[dict(classify_frame(f["attack"],f["defence"],f.get("even_verified") is True,f.get("carrier")),second=f["second"]) for f in frames]
    r={"system":"unknown","samples":samples,"seconds":0,"scope":"geometric_hypothesis"}
    if len(frames)<5:return r
    dt=frames[-1]["second"]-frames[0]["second"]
    ids={f.get("possession_id") for f in frames}
    if dt<2 or None in ids or len(ids)!=1 or any(not 0<b["second"]-a["second"]<=.6 for a,b in zip(frames,frames[1:])):return r
    name,n=Counter(s["system"] for s in samples).most_common(1)[0]
    r["seconds"]=round(dt,2)
    if name!="unknown" and n/len(samples)>=.75:r.update(system=name,support=round(n/len(samples),3))
    return r

def metric_diagnostics(metric,reviews):
    """Local geometry only until reviewed roles and possession are provided."""
    buckets=defaultdict(lambda:{"for":[],"against":[]})
    for tr in metric.get("tracks",[]):
        a=(reviews or {}).get("tracks",{}).get(str(tr["id"]),{})
        side=a.get("side")
        if side not in ("for","against") or a.get("colour")=="red":continue
        for seg in tr.get("segments",[]):
            for p in seg:
                t=round(float(p["second"])*2)/2
                if abs(float(p["second"])-t)>.06:continue
                if not all(isfinite(float(p[k])) for k in ("x_m","y_m")):continue
                if not any(q["id"]==tr["id"] for q in buckets[t][side]):
                    buckets[t][side].append({"id":tr["id"],"x":p["x_m"],"y":p["y_m"]})
    return {"samples":[{"second":t,"for":local_features(r["for"],r["against"]),"against":local_features(r["against"],r["for"])} for t,r in sorted(buckets.items()) if r["for"] and r["against"]][:100],"scope":"local_geometry_not_system"}
