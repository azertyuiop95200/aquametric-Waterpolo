"""Coach what-if simulations; never modify a verified event or its observation."""
from copy import deepcopy
from math import copysign, hypot, isclose, sqrt
from services.spatial_replay import review, number, xyz

def intercept_time(start, receiver, velocity, speed):
    """Earliest horizontal interception in the allowed flight window.

    Solve |receiver + velocity*t - start| = speed*t without clipping time.
    Vertical motion is handled separately by the ballistic model.
    """
    dx, dy = receiver[0]-start[0], receiver[1]-start[1]
    vx, vy = velocity[:2]
    a = vx*vx + vy*vy - speed*speed
    b = 2*(dx*vx + dy*vy)
    c = dx*dx + dy*dy
    eps = 1e-10
    if abs(a) < eps:
        roots = [-c/b] if abs(b) >= eps else ([.15] if c < eps else [])
    else:
        disc = b*b - 4*a*c
        if disc < 0:
            return None
        q = -.5*(b + copysign(sqrt(disc), b))
        roots = [q/a, c/q] if q else [-b/(2*a)]
    valid = [t for t in roots if .15 <= t <= 2 and
             isclose(hypot(dx+vx*t, dy+vy*t), speed*t, rel_tol=1e-8, abs_tol=1e-8)]
    return min(valid) if valid else None


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
    def accelerate(p,v,a,t):
        a=xyz(a,((-2,2),(-2,2),(-2,2)))
        final_v=xyz([v[i]+a[i]*t for i in range(3)],vb)
        for j in range(9):
            u=t*j/8
            xyz([p[i]+v[i]*u+.5*a[i]*u*u for i in range(3)],bounds)
        return [p[i]+v[i]*t+.5*a[i]*t*t for i in range(3)],list(final_v)
    start=list(xyz(edits.get("start",scene["start"]),bounds))
    scene["start"],_=accelerate(start,xyz(edits.get("carrier_velocity",[0,0,0]),vb),edits.get("carrier_acceleration",[0,0,0]),delay)
    defenders=edits.get("defenders",scene["defenders"])
    if not isinstance(defenders,list) or len(defenders)!=len(scene["defenders"]):
        raise ValueError("Keep the observed defender roster")
    if sorted(d["id"] for d in defenders)!=sorted(d["id"] for d in scene["defenders"]):
        raise ValueError("Keep the observed defender identities")
    original={d["id"]:d for d in scene["defenders"]}
    scene["defenders"]=[]
    for d in defenders:
        p,v=accelerate(xyz(d["position"],bounds),xyz(d["velocity"],vb),d.get("acceleration",[0,0,0]),delay)
        scene["defenders"].append(dict(original[d["id"]],position=p,velocity=v,radius=number(d.get("radius",original[d["id"]]["radius"]),.15,1.8)))
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
        # Generate passes only to supplied receiver proxies; never invent a teammate.
        for o in opts:
            if len(scene["options"])>=10: break
            if original_opts[o["id"]]["kind"]!="pass": continue
            ident="Simulation · passe "+o["id"][:55]
            if ident in original_opts or ident in proposed: continue
            p=xyz(o["target"],bounds)
            v=xyz(o.get("receiver_velocity",[0,0,0]),vb)
            try:
                receiver=advance(p,v,delay)
                t=intercept_time(scene["start"],receiver,v,speed)
                if t is None:
                    continue
                target=advance(p,v,delay+t)
            except ValueError:
                continue
            scene["options"].append(dict(id=ident,kind="pass",target=target,duration_s=t))
            proposed.append(ident)
        for name,dy,z in [("gauche basse",-1.15,.22),("droite basse",1.15,.22),
                           ("gauche haute",-1.15,.68),("droite haute",1.15,.68),("centre",0,.45)]:
            if len(scene["options"])>=12: break
            target=[scene["goal_x"],width/2+dy,z]
            duration=hypot(target[0]-scene["start"][0],target[1]-scene["start"][1])/speed
            if not .15 <= duration <= 2:
                continue
            ident="Simulation · tir "+name
            if ident in original_opts: continue
            scene["options"].append(dict(id=ident,kind="shot",target=target,duration_s=duration))
            proposed.append(ident)
    result=review(scene,trials=trials)
    result.update(mode="coach_hypothesis",delay_s=delay,proposed_ids=proposed,
                  baseline_decision_second=baseline["decision_second"],
                  model_assumptions={"nominal_ball_horizontal_speed_m_s":speed,
                    "receiver_targets":"pass endpoints advanced at constant velocity; generated passes solve horizontal interception",
                    "generated_flight_window_s":[.15,2],
                    "generated_speed_constraint":"nominal horizontal speed; infeasible candidates omitted, not clipped",
                    "acceleration":"carrier and defenders accelerate before release, constant velocity during ball flight",
                    "legal_and_athletic_feasibility":"not verified"})
    # Separate hypothetical comparison from the saved evidence, not a new event.
    for o in result["options"]:
        o["hypothetical"]=True
        o["generated"]=o["id"] in proposed
    return result
