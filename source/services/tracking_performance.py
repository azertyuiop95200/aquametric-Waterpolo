"""Time-weighted motion statistics from reviewed, metric 2D tracks.
No interpolation across missing intervals, no conversion of video time into game time.
"""
from collections import defaultdict
from math import floor,hypot
from services.identity_aggregation import edges

def motion_summary(tracks,cell_m=2.0):
    spans=[s for tr in tracks for s in edges(tr) if all(abs(v)<=100 for v in s[2:])]
    starts=defaultdict(list);ends=defaultdict(list)
    for i,e in enumerate(spans):
        starts[e[0]].append(i);ends[e[1]].append(i)
    boundaries=sorted(set(starts)|set(ends));active=set()
    seconds=distance=conflict=overlap=0.;speeds=[];cells=defaultdict(float)
    def point(e,t):
        f=(t-e[0])/(e[1]-e[0])
        return (e[2]+f*(e[4]-e[2]),e[3]+f*(e[5]-e[3]))
    for a,b in zip(boundaries,boundaries[1:]):
        active.difference_update(ends[a]);active.update(starts[a])
        if not active:continue
        dt=b-a;mid=(a+b)/2
        if len(active)>1:
            overlap+=dt
            positions=[point(spans[i],mid) for i in active]
            if any(hypot(x-u,y-v)>.75 for j,(x,y) in enumerate(positions) for u,v in positions[j+1:]):
                conflict+=dt;continue
        # Same shortest-interval policy as identity_aggregation.distance_union.
        i=min(active,key=lambda i:(spans[i][1]-spans[i][0],i))
        e=spans[i];speed=hypot(e[4]-e[2],e[5]-e[3])/(e[1]-e[0])
        seconds+=dt;distance+=speed*dt;speeds.append((speed,dt))
        x,y=point(e,mid);cells[(floor(x/cell_m),floor(y/cell_m))]+=dt
    def quantile(q):
        if not speeds:return None
        total=0.
        for v,dt in sorted(speeds):
            total+=dt
            if total>=seconds*q:return round(v,3)
        return round(max(v for v,dt in speeds),3)
    return dict(observed_seconds=round(seconds,3),distance_m=round(distance,3) if seconds else None,
                average_speed_mps=round(distance/seconds,3) if seconds else None,
                peak_sample_speed_mps=round(max(v for v,dt in speeds),3) if speeds else None,
                speed_p90_mps=quantile(.9),overlap_seconds=round(overlap,3),conflict_seconds=round(conflict,3),
                cell_m=cell_m,occupancy=[dict(x_index=x,y_index=y,seconds=round(t,3),share_pct=round(100*t/seconds,1)) for (x,y),t in sorted(cells.items())],
                scope="partial_metric_video_tracking",note="Occupation par milieu d'intervalle de suivi; vitesse de déplacement 2D, pas vitesse instantanée maximale de nage.")

def motion_report(metric,identity):
    tracks={str(t["id"]):t for t in metric.get("tracks",[]) if "id" in t}
    players=[]
    for p in identity.get("players",[]):
        valid=[tracks[str(i)] for i in p.get("track_ids",[]) if str(i) in tracks]
        m=motion_summary(valid)
        # Match the reviewed identity; no guessed cap numbers.
        players.append(dict(side=p["side"],cap_number=p["cap_number"],name=p["name"],**m))
    return dict(players=players,scope="reviewed_identity_metric_tracks_only")
