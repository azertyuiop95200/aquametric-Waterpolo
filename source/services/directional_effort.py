"""Directional and repeated-effort proxies on non-overlapping metric segments."""
from math import atan2, degrees, hypot, isfinite


def directional_effort(segments, *, sprint_mps, min_sprint_s, turn_deg=60., turn_min_speed_mps=.5, repeated_gap_s=5., max_gap_s=.26, max_speed_mps=3.5):
    if not all(type(v) in (int,float) and isfinite(v) and v>0 for v in (sprint_mps,min_sprint_s,turn_deg,turn_min_speed_mps,repeated_gap_s,max_gap_s,max_speed_mps)) or turn_deg>180:
        raise ValueError('invalid thresholds')
    turns=[]; sprints=[]; gaps=[]; vector_acc=[]; pairs=0; observed=0.
    for seg in segments:
        prev=None; run=None; bouts=[]; continuous=[]
        def finish():
            nonlocal run
            if run is not None and run[1]-run[0]+1e-9>=min_sprint_s:
                if continuous and run[0]-continuous[-1][1]<=repeated_gap_s: gaps.append(run[0]-continuous[-1][1])
                continuous.append(run); bouts.append(run)
            run=None
        for a,b in zip(seg,seg[1:]):
            t,u=a['second'],b['second']; dt=u-t
            if not 0<dt<=max_gap_s: finish(); prev=None; continuous.clear(); continue
            vx=(b['x_m']-a['x_m'])/dt; vy=(b['y_m']-a['y_m'])/dt; speed=hypot(vx,vy)
            if speed>max_speed_mps: finish(); prev=None; continuous.clear(); continue
            observed+=dt; mid=(t+u)/2
            if prev is not None:
                old_t,ox,oy=prev; h=mid-old_t
                vector_acc.append(hypot(vx-ox,vy-oy)/h)
                if min(hypot(ox,oy),speed)>=turn_min_speed_mps:
                    pairs+=1; angle=degrees(atan2(abs(ox*vy-oy*vx),ox*vx+oy*vy))
                    if angle>=turn_deg: turns.append({'second':t,'x_m':a['x_m'],'y_m':a['y_m'],'angle_deg':angle})
            if speed>=sprint_mps:
                run=(t,u) if run is None else (run[0],u)
            else: finish()
            prev=(mid,vx,vy)
        finish()
        sprints.extend({'start_s':a,'end_s':b,'duration_s':b-a} for a,b in bouts)
    return {'observed_s':observed,'turn_eligible_pairs':pairs,'turn_count':len(turns) if pairs else None,'turns':turns,
            'peak_vector_acceleration_mps2':max(vector_acc) if vector_acc else None,'sprint_episodes':sprints,
            'repeated_sprint_pairs':len(gaps) if observed else None,'observed_inter_sprint_gaps_s':gaps,
            'status':'experimental_proxy','turn_threshold_deg':turn_deg,'turn_min_speed_mps':turn_min_speed_mps,'repeated_gap_threshold_s':repeated_gap_s}
