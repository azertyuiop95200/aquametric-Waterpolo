"""Causal horizontal velocity estimate from a contiguous pre-decision track.
Never uses a sample after the decision. No gap bridging or silent zero fallback.
"""
from math import hypot
from .collective_review import num

def estimate(player,t,L,W,*,window=.6,min_support=.3,max_age=.12):
    if not all(map(num,(t,L,W,window,min_support,max_age))) or not 0<min_support<=window<=1 or not 0<=max_age<=.25:
        raise ValueError('Invalid velocity window')
    edges=[]
    for seg in player.get('segments',[]):
        for a,b in zip(seg,seg[1:]):
            s,u=a['second'],b['second'];p=(a['x_m'],a['y_m']);q=(b['x_m'],b['y_m'])
            if not all(map(num,(s,u,*p,*q))) or not 0<u-s<=.260000001 or u>t or u<=t-window:continue
            if any(not (0<=x<=L and 0<=y<=W) for x,y in (p,q)) or hypot(q[0]-p[0],q[1]-p[1])/(u-s)>3.5:continue
            if s<t-window:
                f=(t-window-s)/(u-s);p=tuple(p[i]+f*(q[i]-p[i]) for i in (0,1));s=t-window
            edges.append((s,u,p,q))
    edges.sort(key=lambda e:e[:2])
    if not edges or t-edges[-1][1]>max_age+1e-9:return None
    if any(a[1]>b[0]+1e-9 for a,b in zip(edges,edges[1:])):return None
    run=[edges[-1]]
    for e in reversed(edges[:-1]):
        nxt=run[-1]
        if abs(e[1]-nxt[0])>1e-9 or hypot(e[3][0]-nxt[2][0],e[3][1]-nxt[2][1])>1e-6:break
        run.append(e)
    a,b=run[-1],run[0];duration=b[1]-a[0]
    if duration<min_support-1e-9:return None
    v=[(b[3][i]-a[2][i])/duration for i in (0,1)]
    if any(abs(x)>3 for x in v):return None
    return dict(velocity=[*v,0.],start_s=a[0],end_s=b[1],support_s=duration,age_s=t-b[1],start_xy=list(a[2]),end_xy=list(b[3]))

def in_bounds(position,velocity,horizon,L,W):
    return all(0<=position[i]+velocity[i]*horizon<=bound for i,bound in enumerate((L,W)))


def estimate_reviewed(snapshot, identity, t, L, W):
    """Use a single reviewed forward track, unsmoothed projection only.
    Identity and calibration are retrospective reviews, not online predictions.
    Ambiguous simultaneous tracks are withheld instead of fused.
    """
    summary=(snapshot.get('automatic') or {}).get('summary') or {}
    metric=summary.get('metric_field_map') or {}
    ref=metric.get('reference_second')
    if not num(ref) or not 0<=ref<=t:return None
    reviews=(summary.get('identity_reviews') or {}).get('tracks') or {}
    candidates=[]
    for track in metric.get('tracks',[]):
        key=str(track['id']);r=reviews.get(key,{})
        if r.get('provenance')!='coach_review' or not r.get('evidence') or f"{r.get('side')}:{r.get('cap_number')}"!=identity:continue
        seed=track.get('forward_from_s')
        if not num(seed) or not 0<=seed<=t:continue
        segments=[]
        for seg in track.get('raw_segments',[]):
            run=[]
            for p in seg:
                time,x,y=(p.get(k) for k in ('second','x_m','y_m'))
                if all(map(num,(time,x,y))) and seed<=time<=t and 0<=x<=L and -W/2<=y<=W/2:
                    run.append(dict(second=time,x_m=x,y_m=y+W/2))
                else:
                    if run:segments.append(run);run=[]
            if run:segments.append(run)
        m=estimate({'segments':segments},t,L,W)
        if m is None:continue
        m['track_id']=key;m['forward_from_s']=seed;m['reference_second']=ref;m['provenance']='unsmoothed_forward_metric_v1'
        m['position_xy']=[m['end_xy'][i]+m['velocity'][i]*m['age_s'] for i in (0,1)]
        if not 0<=m['position_xy'][0]<=L or not 0<=m['position_xy'][1]<=W:continue
        candidates.append(m)
    return candidates[0] if len(candidates)==1 else None
