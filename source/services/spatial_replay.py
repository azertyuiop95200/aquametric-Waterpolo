"""Counterfactual replay from explicit pre-action observations.
Model frequencies are conditional on user-supplied uncertainty, not xG.
"""
from math import isfinite, sqrt
from random import Random
from spatial_decision_3d import Track, assess, goal_angles

def number(value, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not isfinite(value) or not lo <= value <= hi:
        raise ValueError(f"Expected finite number in [{lo}, {hi}]")
    return float(value)

def xyz(value, bounds):
    if not isinstance(value,list) or len(value)!=3:
        raise ValueError("Expected three metric coordinates")
    return tuple(number(v,*b) for v,b in zip(value,bounds))

def label(value):
    if not isinstance(value,str) or not value.strip() or len(value)>80:
        raise ValueError("Invalid label")
    return value.strip()

def review(data, trials=160):
    if not isinstance(data,dict):
        raise ValueError("Expected object")
    if data.get("source") not in ("manual_video","calibrated_tracking"):
        raise ValueError("Specify observation provenance")
    if not isinstance(data.get("complete_defence"),bool):
        raise ValueError("Specify defensive visibility")
    length=number(data.get("length_m"),15,40)
    width=number(data.get("width_m"),10,25)
    goal_x=number(data.get("goal_x"),0,length)
    if goal_x not in (0,length):
        raise ValueError("Goal must lie on an end line")
    bounds=((0,length),(0,width),(0,3))
    start=xyz(data.get("start"),bounds)
    sigma=number(data.get("sigma_m"),0,2)
    decision_second=number(data.get("decision_second"),0,86400)
    raw=data.get("defenders")
    opts=data.get("options")
    if not isinstance(raw,list) or len(raw)>8 or not isinstance(opts,list) or not 1<=len(opts)<=12:
        raise ValueError("Maximum eight defenders and twelve options")
    tracks=[]
    for d in raw:
        tracks.append(Track(label(d["id"]),xyz(d["position"],bounds),
                     xyz(d["velocity"],((-3,3),(-3,3),(-3,3))),
                     number(d["radius"],.15,1.8),number(d["confidence"],0,1)))
    if len({d.id for d in tracks})!=len(tracks):
        raise ValueError("Duplicate defender")
    if not isinstance(data.get("chosen"),str):
        raise ValueError("Identify actual action")
    output=[]
    rng=Random(471)
    # Shared random perturbations across choices: comparison uses identical scenarios.
    draws=[([rng.gauss(0,sigma) for _ in range(3)],
            [[rng.gauss(0,sigma) for _ in range(3)] for d in tracks],
            [rng.gauss(0,sigma) for _ in range(3)]) for _ in range(trials)]
    def shift(v,n): return tuple(a+b for a,b in zip(v,n))
    for o in opts:
        ident=label(o["id"])
        kind=o["kind"]
        if kind not in ("shot","pass"):
            raise ValueError("Unknown action")
        end=xyz(o["target"],bounds)
        # The observed missed shot may be outside the frame or stop at a block.
        in_goal = (abs(end[0]-goal_x)<1e-6 and abs(end[1]-width/2)<=1.5 and end[2]<=.9) if kind=="shot" else None
        if kind=="shot" and ident!=data["chosen"] and not in_goal:
            raise ValueError("Alternative shot target must be inside the configured goal")
        duration=number(o["duration_s"],.15,2)
        r=assess(start,end,duration,tracks or None,1,steps=32)
        # A speed limit is not assumed to be a universal athlete capability.
        complete=data["complete_defence"] and bool(tracks) and all(d.confidence>=.5 for d in tracks)
        count=0
        if complete and sigma>0:
            for a,b,c in draws:
                shifted=[Track(d.id,shift(d.position,n),d.velocity,d.radius,d.confidence) for d,n in zip(tracks,b)]
                rr=assess(shift(start,a),shift(end,c),duration,shifted,1,steps=24)
                count+=rr["status"]=="clear_in_model"
        freq=count/trials if complete and sigma>0 else None
        # Wilson interval only reflects Monte Carlo sampling, not model validity.
        interval=None
        if freq is not None:
            z=1.96; den=1+z*z/trials
            mid=(freq+z*z/(2*trials))/den
            half=z*sqrt(freq*(1-freq)/trials+z*z/(4*trials*trials))/den
            interval=[max(0,mid-half),min(1,mid+half)]
        if not complete:
            r.update(status="unknown",clearance_m=None,closest_defender=None,closest_time_s=None)
        output.append(dict(r,id=ident,kind=kind,target=end,clearance_frequency=freq,
                           simulation_interval=interval,target_in_goal=in_goal,goal_probability=None,
                           pass_completion_probability=None))
    ids=[o["id"] for o in output]
    if len(set(ids))!=len(ids) or data["chosen"] not in ids:
        raise ValueError("Chosen action missing or duplicate option")
    return dict(model_version="replay-1",source=data["source"],start=start,
                defenders=[dict(id=d.id,position=d.position,velocity=d.velocity,radius=d.radius,confidence=d.confidence) for d in tracks],
                length_m=length,width_m=width,goal_x=goal_x,chosen=data["chosen"],options=output,
                goal_angles=goal_angles(start,goal_x,width/2) if abs(start[0]-goal_x)>1e-8 else None,
                sigma_m=sigma,trials=trials,complete_defence=complete,decision_second=decision_second,
                limitations=["Conditional geometric clearance, not scoring or completion probability",
                "Constant defender velocity and spherical reach; no learned goalkeeper or arm model",
                "Manual or supplied positions are not automatically reconstructed from pixels"])
