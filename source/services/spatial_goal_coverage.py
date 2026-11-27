"""Conditional goal aperture samples, never a calibrated scoring probability."""
from math import hypot, degrees, atan2
from spatial_decision_3d import assess

def goal_coverage(start, goal_x, width, tracks, keeper_id, complete_defence, speed, *, columns=9, rows=3):
    """Sample equal-area cells for ball-centre targets inside the goal opening.

    Flight time is derived from a fixed nominal horizontal speed. A cell
    classification applies only to its centre, not every point in the cell.
    """
    if not 2 <= speed <= 30 or not 1 <= columns <= 15 or not 1 <= rows <= 7:
        raise ValueError("Invalid goal coverage resolution or speed")
    keeper=next((d for d in tracks if d.id==keeper_id),None)
    keeper_known=keeper is not None and keeper.confidence>=.5
    defence_known=bool(complete_defence and keeper_known and tracks and all(d.confidence>=.5 for d in tracks))
    radius=.11
    span_y=3-2*radius
    span_z=.9-2*radius
    cell_area=span_y*span_z/(columns*rows)
    cells=[]
    for row in range(rows):
        z=.9-radius-(row+.5)*span_z/rows
        for col in range(columns):
            y=width/2-1.5+radius+(col+.5)*span_y/columns
            target=(goal_x,y,z)
            duration=hypot(goal_x-start[0],y-start[1])/speed
            cell=dict(row=row,col=col,target=target,flight_s=duration,keeper_status="unknown",defence_status="unknown",
                      keeper_clearance_m=None,defence_clearance_m=None,closest_part=None,closest_defender=None)
            if not .15<=duration<=2:
                cell.update(keeper_status="outside_flight_window",defence_status="outside_flight_window")
            else:
                if keeper_known:
                    a=assess(start,target,duration,[keeper],1,steps=32)
                    cell.update(keeper_status=a["status"],keeper_clearance_m=a["clearance_m"])
                if defence_known:
                    a=assess(start,target,duration,tracks,1,steps=32)
                    cell.update(defence_status=a["status"],defence_clearance_m=a["clearance_m"],
                                closest_part=a["closest_part"],closest_defender=a["closest_defender"])
            cells.append(cell)
    def summary(key,known):
        feasible=[c for c in cells if c[key] in ("clear_in_model","potential_obstruction")]
        clear=sum(c[key]=="clear_in_model" for c in feasible)
        return dict(evaluated=len(feasible),clear=clear if known and feasible else None,
                    clear_fraction=clear/len(feasible) if known and feasible else None,
                    sampled_clear_area_m2=clear*cell_area if known and len(feasible)==len(cells) else None)
    position=None
    if keeper_known:
        x,y,z=keeper.position
        dx=abs(goal_x-x)
        position=dict(depth_m=dx,lateral_offset_m=y-width/2,velocity_y_m_s=keeper.velocity[1],
                      angular_offset_from_shooter_deg=degrees(atan2(y-start[1],abs(x-start[0])))-degrees(atan2(width/2-start[1],abs(goal_x-start[0]))))
    return dict(model="goal_aperture_grid_v1",keeper_id=keeper_id,keeper_known=keeper_known,
                complete_defence=defence_known,columns=columns,rows=rows,cell_area_m2=cell_area,
                ball_center_aperture_m2=span_y*span_z,nominal_horizontal_speed_m_s=speed,
                cells=cells,keeper=summary("keeper_status",keeper_known),defence=summary("defence_status",defence_known),
                keeper_position=position,goal_probability=None,
                limitations=["Cell-centre samples, not exact covered area or goal probability",
                             "Ball radius and straight horizontal ballistic flight; no bounce, drag or adaptive keeper response",
                             "Only explicitly supplied keeper geometry and motion; other defenders evaluated separately",
                             "Grid estimate is conditional on nominal speed and supplied observation, not a measured save rate"])
