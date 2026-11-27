"""Conservative union of already reviewed metric tracks for one player/source.
No re-identification, gap filling, camera stitching or change of source here.
"""
from collections import defaultdict
from math import hypot, isfinite


def _num(x):
    return type(x) in (float, int) and isfinite(x)


def merge_tracklets(tracks, *, max_gap_s=.26, max_speed_mps=3.5, conflict_m=.75):
    if not all(_num(v) and v>0 for v in (max_gap_s,max_speed_mps,conflict_m)):
        raise ValueError('invalid thresholds')
    spans=[]; starts=defaultdict(list); ends=defaultdict(list); rejected=0
    for ti,tr in enumerate(tracks):
        for si,seg in enumerate(tr.get('segments',[])):
            for a,b in zip(seg,seg[1:]):
                t,u=a['second'],b['second']; x,y=a['x_m'],a['y_m']; X,Y=b['x_m'],b['y_m']
                if not all(map(_num,(t,u,x,y,X,Y))) or not 0<=t<u or u-t>max_gap_s or hypot(X-x,Y-y)/(u-t)>max_speed_mps:
                    rejected+=1; continue
                k=len(spans); spans.append((t,u,x,y,X,Y,(ti,si))); starts[t].append(k); ends[u].append(k)
    def at(k,t):
        a,b,x,y,X,Y,_=spans[k]; f=(t-a)/(b-a)
        return {'second':t,'x_m':x+f*(X-x),'y_m':y+f*(Y-y)}
    def dist(p,q): return hypot(p['x_m']-q['x_m'],p['y_m']-q['y_m'])
    active=set(); segments=[]; last_edge=None; last_group=None; overlap=conflict=observed=0.
    times=sorted(set(starts)|set(ends))
    for a,b in zip(times,times[1:]):
        active.difference_update(ends[a]); active.update(starts[a]); dt=b-a
        if not active: last_edge=last_group=None; continue
        keys=sorted(active)
        if len(keys)>1:
            overlap+=dt
            if any(dist(at(i,t),at(j,t))>conflict_m for k,i in enumerate(keys) for j in keys[k+1:] for t in (a,b)):
                conflict+=dt; last_edge=last_group=None; continue
        k=min(keys,key=lambda i:(spans[i][1]-spans[i][0],i)); p,q=at(k,a),at(k,b); group=spans[k][-1]
        if segments and group==last_group and segments[-1][-1]['second']==a and dist(segments[-1][-1],p)<=1e-8:
            if k==last_edge: segments[-1][-1]=q
            else: segments[-1].append(q)
        else: segments.append([p,q])
        observed+=dt; last_edge=k; last_group=group
    return {'segments':segments,'observed_s':observed,'overlap_s':overlap,'conflict_s':conflict,'rejected_edges':rejected}
