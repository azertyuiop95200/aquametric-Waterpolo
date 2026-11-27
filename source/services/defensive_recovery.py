"""Post-change defensive movement in reviewed video windows, not reaction time."""
from bisect import bisect_right
from math import hypot, isfinite


def number(v): return type(v) in (float, int) and isfinite(v)


def analyze_recovery(report, evidence, review):
    """Use a reviewed post-control window; never infer onset from endpoint evidence.
    Reviewed roster contains field players only; keeper exclusion is explicit.
    Distances use common observed intervals and a fixed goal-relative axis.
    """
    L,W=report['length_m'],report['width_m']; a,b=review.get('start_s'),review.get('end_s')
    side=evidence.get('before'); other=evidence.get('after'); end=evidence.get('end_s')
    if (evidence.get('status')!='opposite_endpoints' or type(evidence.get('exact_count')) is not int or evidence['exact_count']!=1
        or side not in ('for','against') or other not in ('for','against') or side==other
        or evidence.get('source')!=report['source'] or evidence.get('period')!=report['period']
        or review.get('source')!=report['source'] or review.get('period')!=report['period']
        or evidence.get('id') is None or review.get('transition_id')!=evidence['id']
        or review.get('provenance')!='coach_review' or review.get('continuous_play_reviewed') is not True
        or review.get('roster_reviewed') is not True or review.get('field_players_only') is not True
        or not all(map(number,(a,b,end,L,W))) or not report['start_s']<=end<=a<b<=report['end_s']
        or b-a>30 or review.get('own_goal_x') not in (0,L)):
        raise ValueError('reviewed post-change window and direction required')
    ids=review.get('defenders'); goal=review['own_goal_x']; sign=1 if goal==L else -1
    if not isinstance(ids,list) or not ids or any(not isinstance(i,str) or not i.startswith(side+':') for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('distinct reviewed field-player roster required')
    rows={}; duplicates=set()
    for p in report['players']:
        k=f"{p['side']}:{p['cap_number']}"
        if k in rows: duplicates.add(k)
        rows[k]=p
    cuts={a,b}; tracks={}
    for i in ids:
        spans=[]
        if i not in duplicates and i in rows and rows[i].get('metrics') is not None:
            for seg in rows[i].get('segments',[]):
                for p,q in zip(seg,seg[1:]):
                    t,u=p['second'],q['second']; P=(p['x_m'],p['y_m']); Q=(q['x_m'],q['y_m'])
                    if not all(map(number,(t,u,*P,*Q))) or not 0<u-t<=.26 or hypot(Q[0]-P[0],Q[1]-P[1])/(u-t)>3.5: continue
                    if any(not (0<=x<=L and 0<=y<=W) for x,y in (P,Q)) or u<=a or t>=b: continue
                    spans.append((t,u,P,Q));cuts.update((max(a,t),min(b,u)))
        spans.sort()
        if any(s[1]>t[0] for s,t in zip(spans,spans[1:])): raise ValueError('overlapping player edges')
        tracks[i]=([s[0] for s in spans],spans)
    def edge(i,t,u):
        starts,spans=tracks[i]; k=bisect_right(starts,(t+u)/2)-1
        if k<0: return None
        s,e,P,Q=spans[k]
        if not s<=t<u<=e: return None
        def at(v): return tuple(P[j]+(Q[j]-P[j])*(v-s)/(e-s) for j in (0,1))
        return at(t),at(u)
    def half_fraction(x,y):
        x,y=sign*(x-L/2),sign*(y-L/2)
        if min(x,y)>=0: return 1.
        if max(x,y)<=0: return 0.
        return max(x,y)/abs(x-y)
    accum={i:[0.,0.,0.] for i in ids}; common=0.; first=last=None; cuts=sorted(cuts)
    for t,u in zip(cuts,cuts[1:]):
        edges={i:edge(i,t,u) for i in ids}
        if any(v is None for v in edges.values()): continue
        dt=u-t;common+=dt
        for i,(p,q) in edges.items():
            v=accum[i];v[0]+=hypot(q[0]-p[0],q[1]-p[1]);v[1]+=sign*(q[0]-p[0]);v[2]+=dt*half_fraction(p[0],q[0])
        if first is None: first={'second':t,'positions':{i:v[0] for i,v in edges.items()}}
        last={'second':u,'positions':{i:v[1] for i,v in edges.items()}}
    players=[dict(id=i,distance_m=v[0] if common else None,goalward_progress_m=v[1] if common else None,mean_goalward_mps=v[1]/common if common else None,own_half_s=v[2] if common else None) for i,v in accum.items()]
    return dict(status='experimental_reviewed_post_change',start_s=a,end_s=b,own_goal_x=goal,observed_s=common,coverage=common/(b-a),players=players,first=first,last=last,mean_team_goalward_mps=sum(v[1] for v in accum.values())/(len(ids)*common) if common else None,recovery_time_s=None,game_duration_s=None,position_error_m=None)
