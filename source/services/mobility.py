"""Time-weighted mobility from reviewed, metric track fragments in ONE common coordinate system.
No imputation; no substitution for regulation clock, and no inferred sprints.
"""
from collections import defaultdict
from math import hypot,isfinite,ceil,floor

def summarize_tracks(tracks, *, length_m=25., width_m=20., max_gap=.26, max_speed=3.5, conflict_m=.75, cell_m=2.):
    if not all(isfinite(x) and x>0 for x in (length_m,width_m,max_gap,max_speed,conflict_m,cell_m)):raise ValueError('Invalid mobility parameters')
    nx,ny=ceil(length_m/cell_m),ceil(width_m/cell_m)
    if nx*ny>10000:raise ValueError('Grid too large')
    edges=[]; starts=defaultdict(list); ends=defaultdict(list); rejected=0
    for tr in tracks:
        for seg in tr.get('segments',[]):
            for a,b in zip(seg,seg[1:]):
                try:t,u,x,y,X,Y=map(float,(a['second'],b['second'],a['x_m'],a['y_m'],b['x_m'],b['y_m']))
                except (KeyError,ValueError,TypeError):rejected+=1;continue
                if not all(isfinite(v) for v in (t,u,x,y,X,Y)) or not 0<=t<u or u-t>max_gap+1e-8 or not (0<=x<=length_m and 0<=X<=length_m and abs(y)<=width_m/2 and abs(Y)<=width_m/2) or hypot(X-x,Y-y)/(u-t)>max_speed:
                    rejected+=1;continue
                i=len(edges); edges.append((t,u,x,y,X,Y));starts[t].append(i);ends[u].append(i)
    def point(e,t):
        a,b,x,y,X,Y=e;f=(t-a)/(b-a);return x+f*(X-x),y+f*(Y-y)
    active=set();last=None;duration=distance=overlap=conflict=0.;grid=defaultdict(float);speeds=[];accepted=[]
    def deposit(a,b,dt):
        x,y=a;X,Y=b; y+=width_m/2;Y+=width_m/2;cuts={0.,1.}
        for p,q,n in ((x,X,nx),(y,Y,ny)):
            if p==q:continue
            for k in range(max(1,floor(min(p,q)/cell_m)+1),min(n,ceil(max(p,q)/cell_m))):
                f=(k*cell_m-p)/(q-p)
                if 0<f<1:cuts.add(f)
        z=sorted(cuts)
        for lo,hi in zip(z,z[1:]):
            m=(lo+hi)/2;i=min(nx-1,max(0,int((x+m*(X-x))/cell_m)));j=min(ny-1,max(0,int((y+m*(Y-y))/cell_m)))
            grid[i,j]+=dt*(hi-lo)
    for t in sorted(set(starts)|set(ends)):
        if last is not None and t>last and active:
            dt=t-last;ids=sorted(active);rows=[edges[i] for i in ids]
            if len(rows)>1:overlap+=dt
            ab=[(point(e,last),point(e,t)) for e in rows]
            bad=any(hypot(a[0][0]-b[0][0],a[0][1]-b[0][1])>conflict_m or hypot(a[1][0]-b[1][0],a[1][1]-b[1][1])>conflict_m for i,a in enumerate(ab) for b in ab[i+1:])
            if bad:conflict+=dt
            else:
                i=min(range(len(rows)),key=lambda i:(rows[i][1]-rows[i][0],ids[i]));a,b=ab[i];d=hypot(b[0]-a[0],b[1]-a[1]);duration+=dt;distance+=d;speeds.append((d/dt,dt));deposit(a,b,dt)
                accepted.append({'start_second':last,'end_second':t,'x0':a[0],'y0':a[1],'x1':b[0],'y1':b[1]})
        for i in ends[t]:active.discard(i)
        active.update(starts[t]);last=t
    def percentile(q):
        if not duration:return None
        s=0
        for v,dt in sorted(speeds):
            s+=dt
            if s+1e-9>=q*duration:return round(v,3)
        return round(max(v for v,dt in speeds),3)
    if abs(sum(grid.values())-duration)>1e-6:raise RuntimeError('Heatmap duration reconciliation failed')
    return {'distance_m':round(distance,2) if duration else None,'observed_seconds':round(duration,3),'overlap_seconds':round(overlap,3),'conflict_seconds':round(conflict,3),'mean_speed_m_s':round(distance/duration,3) if duration else None,'median_speed_m_s':percentile(.5),'p90_speed_m_s':percentile(.9),'rejected_edges':rejected,'heatmap':{'length_m':length_m,'width_m':width_m,'cell_m':cell_m,'cells':[{'x_m':i*cell_m,'y_m':j*cell_m-width_m/2,'width_m':min(cell_m,length_m-i*cell_m),'height_m':min(cell_m,width_m-j*cell_m),'seconds':round(v,6)} for (i,j),v in sorted(grid.items())]},'accepted_edges':accepted,'scope':'partial_metric_video_time'}
