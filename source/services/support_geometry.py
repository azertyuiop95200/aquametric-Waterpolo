"""Observed off-ball support geometry; not inferred intention or causal impact."""
from math import hypot, isfinite


class SupportAccumulator:
    def __init__(self, attackers, defenders, carrier, goal_x, length, *, separation_m=1.5, support_radius_m=5.):
        if carrier not in attackers or not defenders or goal_x not in (0,length):
            raise ValueError('reviewed carrier, defenders and direction required')
        if not all(type(v) in (int,float) and isfinite(v) and v>0 for v in (separation_m,support_radius_m)):
            raise ValueError('invalid support thresholds')
        self.D=tuple(defenders); self.carrier=carrier; self.sign=1 if goal_x==length else -1
        self.separation=separation_m; self.radius=support_radius_m; self.observed=0.
        self.rows={i:dict(distance_m=0.,goal_progress_m=0.,nearest_defender_m_s=0.,carrier_distance_m_s=0.,support_open_s=0.,support_unknown_s=0.,separation_change_m=0.) for i in attackers if i!=carrier}

    def add(self, edges, start, end, states):
        dt=end-start
        if not isfinite(dt) or dt<=0 or set(states)!=set(self.rows): raise ValueError('invalid support interval')
        if any(s not in ('clear_2d','obstructed_2d','indeterminate') for s in states.values()): raise ValueError('invalid lane state')
        self.observed+=dt
        mid={i:tuple((x+y)/2 for x,y in zip(*v)) for i,v in edges.items()}
        def dist(p,q): return hypot(p[0]-q[0],p[1]-q[1])
        for i,row in self.rows.items():
            p,q=edges[i]; nearest=lambda j:min(dist(edges[i][j],edges[k][j]) for k in self.D)
            n=min(dist(mid[i],mid[k]) for k in self.D); c=dist(mid[i],mid[self.carrier])
            row['distance_m']+=dist(p,q); row['goal_progress_m']+=self.sign*(q[0]-p[0]); row['separation_change_m']+=nearest(1)-nearest(0)
            row['nearest_defender_m_s']+=dt*n; row['carrier_distance_m_s']+=dt*c
            # Bound whole interval, not just midpoint: relative movement of both players.
            drift=lambda k:dist(*edges[k])/2
            ne=[(dist(mid[i],mid[k]),drift(i)+drift(k)) for k in self.D]
            c_err=drift(i)+drift(self.carrier)
            within=c+c_err<=self.radius; separated=all(d-e>=self.separation for d,e in ne)
            impossible=c-c_err>self.radius or any(d+e<self.separation for d,e in ne) or states[i]=='obstructed_2d'
            if within and separated and states[i]=='clear_2d': row['support_open_s']+=dt
            elif not impossible: row['support_unknown_s']+=dt

    def result(self):
        t=self.observed; rows=[]
        for i,v in self.rows.items():
            r={k:v[k] if t else None for k in ('distance_m','goal_progress_m','separation_change_m','support_open_s','support_unknown_s')}
            r.update(id=i,nearest_defender_mean_m=v['nearest_defender_m_s']/t if t else None,carrier_distance_mean_m=v['carrier_distance_m_s']/t if t else None,support_open_fraction=v['support_open_s']/t if t else None)
            rows.append(r)
        return dict(observed_s=t,separation_m=self.separation,support_radius_m=self.radius,rows=rows,status='experimental_planar_support_proxy',position_error_m=None)
