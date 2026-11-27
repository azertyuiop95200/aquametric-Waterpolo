"""Experimental metrics on reviewed metric track segments, never image pixels."""
from math import hypot, atan2, degrees, isfinite
from numbers import Real


def num(x):
    return isinstance(x, Real) and not isinstance(x, bool) and isfinite(x)


def point(p):
    return isinstance(p, (list, tuple)) and len(p)==2 and all(map(num,p))


def motion(segments, *, sprint_mps, min_sprint_s, max_gap_s=.26, max_speed_mps=3.5):
    if not all(num(x) and x>0 for x in (sprint_mps,min_sprint_s,max_gap_s,max_speed_mps)) or sprint_mps>max_speed_mps:
        raise ValueError('invalid thresholds')
    observed=distance=fast=acc_time=0.; accelerations=[]; runs=[]; run=0.; last=None; end=None
    def flush():
        nonlocal run,last
        if run>=min_sprint_s: runs.append(run)
        run=0.; last=None
    for seg in segments:
        flush()
        for a,b in zip(seg,seg[1:]):
            t,u=a['second'],b['second']; p=(a['x_m'],a['y_m']); q=(b['x_m'],b['y_m'])
            if not all(map(num,(t,u))) or t<0 or u<=t or (end is not None and t<end):
                raise ValueError('overlapping or invalid times')
            end=u; dt=u-t
            if dt>max_gap_s or not point(p) or not point(q): flush(); continue
            d=hypot(q[0]-p[0],q[1]-p[1]); v=d/dt
            if v>max_speed_mps: flush(); continue
            observed+=dt; distance+=d; mid=(t+u)/2
            if last is not None:
                h=mid-last[0]; accelerations.append((v-last[1])/h); acc_time+=h
            last=(mid,v)
            if v>=sprint_mps: run+=dt; fast+=dt
            else:
                if run>=min_sprint_s: runs.append(run)
                run=0.
    flush()
    return dict(observed_s=observed,distance_m=distance if observed else None,
                mean_speed_mps=distance/observed if observed else None,
                acceleration_samples=len(accelerations),acceleration_support_s=acc_time,
                peak_speed_increase_mps2=max(0.,max(accelerations)) if accelerations else None,
                peak_speed_decrease_mps2=max(0.,-min(accelerations)) if accelerations else None,
                sprint_count=len(runs) if observed else None,sprint_s=sum(runs) if observed else None,
                above_threshold_s=fast if observed else None,status='experimental_proxy')


def reviewed_motion(metric,identity,**config):
    """Adapter for identity_aggregation players/track_ids and metric segments.
    Caller scopes to one source and camera calibration. Reject ambiguous tracks.
    """
    tracks={}; duplicates=set()
    for t in metric.get('tracks',[]):
        k=str(t['id'])
        if k in tracks: duplicates.add(k)
        tracks[k]=t
    owners={}
    for p in identity.get('players',[]):
        for k in set(map(str,p.get('track_ids',[]))): owners[k]=owners.get(k,0)+1
    rows=[]
    for p in identity.get('players',[]):
        ids=list(dict.fromkeys(map(str,p.get('track_ids',[]))))
        row=dict(side=p['side'],cap_number=p['cap_number'],track_ids=ids)
        if len(ids)!=1 or ids[0] not in tracks or ids[0] in duplicates or owners[ids[0]]!=1:
            row.update(status='unavailable_ambiguous_tracks',metrics=None)
        else:
            row.update(status='experimental_proxy',metrics=motion(tracks[ids[0]].get('segments',[]),**config))
        rows.append(row)
    return rows


def geometry(start,end,goal_posts):
    """Planar pass/shot direction relative to goal centre, and visible goal angle.
    Not actual ball trajectory or 3D opening; posts must be metric coordinates.
    """
    if not point(start) or not point(end) or len(goal_posts)!=2 or not all(map(point,goal_posts)):
        raise ValueError('metric coordinates required')
    a,b=goal_posts; g=((a[0]+b[0])/2,(a[1]+b[1])/2)
    if a==b: raise ValueError('distinct posts required')
    def vec(p,q): return (q[0]-p[0],q[1]-p[1])
    def angle(v,w):
        if not hypot(*v) or not hypot(*w): return None
        return degrees(atan2(abs(v[0]*w[1]-v[1]*w[0]),v[0]*w[0]+v[1]*w[1]))
    return dict(action_length_m=hypot(*vec(start,end)),direction_to_goal_deg=angle(vec(start,end),vec(start,g)),
                goal_angle_deg=angle(vec(start,a),vec(start,b)),status='planar_geometry_proxy')


def transition(evidence,ball_start,ball_end,attack_axis):
    """Use possession_evidence report row. Endpoints bound change, not exact onset.
    Ball positions must be reviewed at the evidence endpoints; axis points to target.
    """
    if evidence.get('status')!='opposite_endpoints' or evidence.get('exact_count')!=1:
        return dict(status='unavailable_unverified_transition',progress_m=None,mean_progress_mps=None)
    a,b=evidence['start_s'],evidence['end_s']
    if not all(map(num,(a,b))) or not 0<=a<b or not all(map(point,(ball_start,ball_end,attack_axis))) or not hypot(*attack_axis):
        raise ValueError('invalid transition geometry or timing')
    n=hypot(*attack_axis); progress=sum((ball_end[i]-ball_start[i])*attack_axis[i]/n for i in (0,1))
    return dict(status='endpoint_proxy',source=evidence.get('source'),period=evidence.get('period'),
                video_window_s=b-a,progress_m=progress,mean_progress_mps=progress/(b-a),
                recovery_s=None,game_duration_s=None)
