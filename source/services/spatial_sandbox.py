"""Coach what-if simulations; never modify a verified event or its observation."""
from copy import deepcopy
from math import hypot
from services.spatial_replay import review, number, xyz

def sandbox(baseline, edits, trials=32):
    if not isinstance(edits,dict): raise ValueError("Invalid scenario")
    scene=deepcopy(baseline)
    length,width=scene["length_m"],scene["width_m"]
    bounds=((0,length),(0,width),(0,3))
    vb=((-3,3),(-3,3),(-3,3))
    delay=number(edits.get("delay_s",0),0,3)
    speed=number(edits.get("ball_speed_m_s",12),2,30)
    def advance(p,v,t):
        out=[a+b*t for a,b in zip(p,v)]
        # Never silently clip a trajectory at a boundary.
        return list(xyz(out,bounds))
    start=list(xyz(edits.get("start",scene["start"]),bounds))
    scene["start"]=advance(start,xyz(edits.get("carrier_velocity",[0,0,0]),vb),delay)
    defenders=edits.get("defenders",scene["defenders"])
    if not isinstance(defenders,list) or len(defenders)!=len(scene["defenders"]):
        raise ValueError("Keep the observed defender roster")
    if sorted(d["id"] for d in defenders)!=sorted(d["id"] for d in scene["defenders"]):
        raise ValueError("Keep the observed defender identities")
    original={d["id"]:d for d in scene["defenders"]}
    scene["defenders"]=[dict(original[d["id"]],position=advance(xyz(d["position"],bounds),xyz(d["velocity"],vb),delay),
                            velocity=list(xyz(d["velocity"],vb))) for d in defenders]
    original_opts={o["id"]:o for o in scene["options"]}
    opts=edits.get("options",scene["options"])
    if not isinstance(opts,list) or len(opts)!=len(original_opts) or {o["id"] for o in opts}!=set(original_opts):
        raise ValueError("Keep the original option identifiers")
    scene["options"]=[]
    for o in opts:
        old=original_opts[o["id"]]
        t=number(o["duration_s"],.15,2)
        target=xyz(o["target"],bounds)
        # A pass endpoint is a receiver proxy, not a measured athlete identity.
        if old["kind"]=="pass":
            target=advance(target,xyz(o.get("receiver_velocity",[0,0,0]),vb),delay+t)
        scene["options"].append(dict(old,target=list(target),duration_s=t))
    proposed=[]
    if edits.get("suggest",True):
        for name,dy,z in [("gauche basse",-1.15,.22),("droite basse",1.15,.22),
                           ("gauche haute",-1.15,.68),("droite haute",1.15,.68),("centre",0,.45)]:
            if len(scene["options"])>=12: break
            target=[scene["goal_x"],width/2+dy,z]
            duration=max(.15,min(2,hypot(target[0]-scene["start"][0],target[1]-scene["start"][1])/speed))
            ident="Simulation · tir "+name
            if ident in original_opts: continue
            scene["options"].append(dict(id=ident,kind="shot",target=target,duration_s=duration))
            proposed.append(ident)
    result=review(scene,trials=trials)
    result.update(mode="coach_hypothesis",delay_s=delay,proposed_ids=proposed,
                  baseline_decision_second=baseline["decision_second"],
                  model_assumptions={"nominal_ball_horizontal_speed_m_s":speed,
                    "receiver_targets":"pass endpoints advanced at constant velocity",
                    "legal_and_athletic_feasibility":"not verified"})
    # Separate hypothetical comparison from the saved evidence, not a new event.
    for o in result["options"]:
        o["hypothetical"]=True
        o["generated"]=o["id"] in proposed
    return result
