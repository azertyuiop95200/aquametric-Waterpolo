"""Descriptive surface geometry over explicitly reviewed possession subwindows."""
from bisect import bisect_right
from math import hypot, isfinite, sqrt
try:
    from services.tactical_trajectories import _interval, _exposure
    from services.spatial_dominance import SpaceAccumulator
except ModuleNotFoundError as e:
    if e.name != 'services': raise
    from tactical_trajectories import _interval, _exposure
    from spatial_dominance import SpaceAccumulator


def number(v): return type(v) in (int,float) and isfinite(v)
def sub(a,b): return (a[0]-b[0],a[1]-b[1])
def norm(a): return hypot(*a)


def segment_distance(p,a,b):
    v=sub(b,a); w=sub(p,a); d=v[0]**2+v[1]**2
    f=max(0.,min(1.,(v[0]*w[0]+v[1]*w[1])/d)) if d else 0.
    return norm((w[0]-f*v[0],w[1]-f*v[1]))


def shape(points):
    n=len(points); x=sum(p[0] for p in points)/n; y=sum(p[1] for p in points)/n
    return {'width_m':max(p[1] for p in points)-min(p[1] for p in points),
            'depth_m':max(p[0] for p in points)-min(p[0] for p in points),
            'rms_radius_m':sqrt(sum((p[0]-x)**2+(p[1]-y)**2 for p in points)/n)}


def analyze_window(report, window, *, lane_radius_m=.65, proximity_m=1.5, max_step_s=.1):
    """One fixed, reviewed roster and carrier, complete control interval.
    Midpoint shape quadrature; exact linear proximity; conservative planar lane
    bounds. No inference of legal/airborne pass feasibility or physical pressure.
    All durations are video seconds. IDs are side:cap_number.
    """
    if not all(number(v) and v>0 for v in (lane_radius_m,proximity_m,max_step_s)) or max_step_s>.26:
        raise ValueError('invalid thresholds')
    a,b=window.get('start_s'),window.get('end_s'); side=window.get('attacking_side')
    if (window.get('source')!=report['source'] or window.get('period')!=report['period'] or
        window.get('control_reviewed') is not True or window.get('roster_reviewed') is not True or
        side not in ('for','against') or not all(map(number,(a,b))) or not report['start_s']<=a<b<=report['end_s']):
        raise ValueError('unverified or out-of-scope possession window')
    A,D=window.get('attackers',[]),window.get('defenders',[]); carrier=window.get('carrier')
    other='against' if side=='for' else 'for'
    if not A or not D or any(not isinstance(i,str) or not i.startswith(side+':') for i in A) or any(not isinstance(i,str) or not i.startswith(other+':') for i in D) or len(set(A+D))!=len(A+D) or carrier not in A:
        raise ValueError('invalid fixed roster/carrier')
    if window.get('goal_x') not in (0,report['length_m']): raise ValueError('attack direction required')
    space=SpaceAccumulator(report['length_m'],report['width_m'],A,D,position_error_m=window.get('position_error_bound_m'))
    rows={}; duplicates=set()
    for p in report['players']:
        k=f"{p['side']}:{p['cap_number']}"
        if k in rows: duplicates.add(k)
        rows[k]=p
    cuts={a,b}; tracks={}
    for i in A+D:
        spans=[]
        if i not in duplicates and i in rows and rows[i].get('metrics') is not None:
            for seg in rows[i].get('segments',[]):
                for p,q in zip(seg,seg[1:]):
                    t,u=p['second'],q['second']; P=(p['x_m'],p['y_m']); Q=(q['x_m'],q['y_m'])
                    if not all(map(number,(t,u,*P,*Q))) or not 0<u-t<=.26 or norm(sub(Q,P))/(u-t)>3.5: continue
                    if u<=a or t>=b: continue
                    spans.append((t,u,P,Q)); cuts.update((max(a,t),min(b,u)))
        spans.sort(); tracks[i]=([s[0] for s in spans],spans)
    def edge(i,t,u):
        starts,spans=tracks[i]; k=bisect_right(starts,(t+u)/2)-1
        if k<0: return None
        s,e,P,Q=spans[k]
        if not s<=t<u<=e: return None
        def at(v): return tuple(P[j]+(Q[j]-P[j])*(v-s)/(e-s) for j in (0,1))
        return at(t),at(u)
    def mean(p,q): return tuple((x+y)/2 for x,y in zip(p,q))
    base=sorted(cuts); cuts=[a]
    from math import ceil
    for t,u in zip(base,base[1:]):
        n=ceil((u-t)/max_step_s)
        cuts.extend(t+(u-t)*j/n for j in range(1,n)); cuts.append(u)
    observed=0.; totals={s:{k:0. for k in ('width_m','depth_m','rms_radius_m')} for s in ('attack','defence')}
    pressure={i:[0.,0.] for i in A}; lanes={i:[0.,0.,0.] for i in A if i!=carrier}; snapshots=[]
    for t,u in zip(cuts,cuts[1:]):
        edges={i:edge(i,t,u) for i in A+D}
        if any(v is None for v in edges.values()): continue
        space.add(edges,t,u)
        dt=u-t; observed+=dt; mid={i:mean(*v) for i,v in edges.items()}
        for s,ids in (('attack',A),('defence',D)):
            for k,v in shape([mid[i] for i in ids]).items(): totals[s][k]+=dt*v
        for i in A:
            intervals=[v for j in D if (v:=_interval(sub(edges[i][0],edges[j][0]),sub(edges[i][1],edges[j][1]),proximity_m)) is not None]
            for k in (1,2): pressure[i][k-1]+=dt*_exposure(intervals,k)
        state={}
        for i in lanes:
            x,y=mid[carrier],mid[i]; motion=max(norm(sub(*edges[carrier])),norm(sub(*edges[i])))/2
            bounds=[(segment_distance(mid[j],x,y),motion+norm(sub(*edges[j]))/2) for j in D]
            if norm(sub(x,y))<=1e-9: k=2
            elif all(d-e>lane_radius_m for d,e in bounds): k=0
            elif any(d+e<=lane_radius_m for d,e in bounds): k=1
            else: k=2
            lanes[i][k]+=dt; state[i]=('clear_2d','obstructed_2d','indeterminate')[k]
        if not snapshots: snapshots.append({'second':(t+u)/2,'positions':mid,'lanes':state})
    def value(v): return v if observed else None
    return {'id':window.get('id'),'start_s':a,'end_s':b,'attacking_side':side,'goal_x':window['goal_x'],
            'attackers':A,'defenders':D,'carrier':carrier,'observed_s':observed,'coverage':observed/(b-a),
            'shape':{s:{k:v/observed if observed else None for k,v in m.items()} for s,m in totals.items()},
            'pressure':[{'id':i,'proximity_s':value(v[0]),'double_proximity_s':value(v[1])} for i,v in pressure.items()],
            'lanes':[{'receiver':i,'clear_s':value(v[0]),'obstructed_s':value(v[1]),'indeterminate_s':value(v[2]),'clear_fraction':v[0]/observed if observed else None} for i,v in lanes.items()],
            'snapshot':snapshots[0] if snapshots else None,'lane_radius_m':lane_radius_m,'proximity_m':proximity_m,
            'status':'experimental_planar_proxy','game_duration_s':None,'position_error_m':None,
            'spatial_dominance':space.result()}
