"""Conditional two-leg attack alternatives; no independent probability product."""
from dataclasses import replace
from math import hypot
from spatial_decision_3d import assess
from services.spatial_goal_coverage import goal_coverage

def two_step_attack(start, goal_x, length, width, tracks, keeper_id, complete,
                    speed, options, reception_s, receiver_velocities, budget_s=None):
    if not 0 <= reception_s <= 1.5 or not 2 <= speed <= 30:
        raise ValueError("Invalid sequence timing")
    bounds=((0,length),(0,width),(0,3))
    def inside(p):
        return all(lo<=v<=hi for v,(lo,hi) in zip(p,bounds))
    direct=goal_coverage(start,goal_x,width,tracks,keeper_id,complete,speed)
    def cell_eligible(c,elapsed=0):
        return budget_s is None or elapsed+c["flight_s"]<=budget_s
    direct_cells=[c for c in direct["cells"] if cell_eligible(c)]
    known=direct["complete_defence"]
    def best(cells):
        valid=[c for c in cells if c["defence_clearance_m"] is not None]
        return max(valid,key=lambda c:c["defence_clearance_m"]) if valid else None
    d=best(direct_cells)
    rows=[]
    for o in options:
        if o["kind"]!="pass": continue
        row=dict(pass_id=o["id"],pass_status=o["status"],pass_clearance_m=o["clearance_m"],
                 pass_flight_s=o["flight_s"],reception_s=reception_s,shot_start=None,
                 status="unknown",joint_clearance_m=None,goal_probability=None,
                 total_duration_s=None,shot_target=None,shot_clearance_m=None,
                 direct_clearance_delta_m=None,shot_cells_clear=None)
        elapsed=o["flight_s"]+reception_s
        v=receiver_velocities.get(o["id"],(0,0,0))
        origin=tuple(p+q*reception_s for p,q in zip(o["target"],v))
        row["shot_start"]=origin
        row["shot_release_s"]=elapsed
        if not inside(origin) or (budget_s is not None and elapsed>=budget_s):
            row["status"]="outside_bounds_or_budget";rows.append(row);continue
        advanced=[replace(t,position=tuple(p+q*elapsed for p,q in zip(t.position,t.velocity)),
                          reach_elapsed_s=min(5,t.reach_elapsed_s+elapsed)) for t in tracks]
        if not all(inside(t.position) for t in advanced):
            row["status"]="defender_projection_outside_bounds";rows.append(row);continue
        m=goal_coverage(origin,goal_x,width,advanced,keeper_id,complete,speed)
        cells=[c for c in m["cells"] if cell_eligible(c,elapsed)]
        b=best(cells)
        if b is None or o["clearance_m"] is None or not known:
            row["status"]="unknown" if not known else "no_evaluable_shot"
        else:
            joint=min(o["clearance_m"],b["defence_clearance_m"])
            row.update(status="clear_in_model" if joint>0 else "potential_obstruction",
                       joint_clearance_m=joint,shot_target=b["target"],shot_clearance_m=b["defence_clearance_m"],
                       total_duration_s=elapsed+b["flight_s"],
                       direct_clearance_delta_m=joint-d["defence_clearance_m"] if d else None,
                       shot_cells_clear=sum(c["defence_status"]=="clear_in_model" for c in cells))
        rows.append(row)
    return dict(model="pass_then_shot_v1",direct_best=d,alternatives=rows,budget_s=budget_s,
                goal_probability=None,limitations=["Conditional geometry of both legs; reception assumed, not predicted",
                "Minimum clearance across both legs, not product of probabilities",
                "Defenders follow supplied velocity and reach clock; no adaptive response inferred",
                "Reception and release delay explicit; budget is user-supplied, not inferred match clock",
                "Pressure during ball control and legal/athletic feasibility are not evaluated"])
