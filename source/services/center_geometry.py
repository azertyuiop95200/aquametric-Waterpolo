"""Geometry of an explicitly reviewed centre/marker pair; not contact or duel outcome."""
from math import hypot, isfinite
from .tactical_trajectories import _interval


def fraction_between(a,b,lo,hi):
    if a==b: return (0.,1.) if lo<=a<=hi else None
    u,v=sorted(((lo-a)/(b-a),(hi-a)/(b-a)))
    u,v=max(0.,u),min(1.,v)
    return (u,v) if v>u else None


class CenterAccumulator:
    def __init__(self, role, attackers, defenders, goal_x, length, width, *, radius=1.5, depth=4., half_width=3., error=None):
        if role.get('provenance')!='coach_review' or role.get('center') not in attackers or role.get('marker') not in defenders or goal_x not in (0,length):
            raise ValueError('explicit reviewed centre and marker required')
        if not all(type(v) in (int,float) and isfinite(v) and v>0 for v in (radius,depth,half_width,length,width)) or depth>length or half_width>width/2:
            raise ValueError('invalid centre geometry')
        if error is not None and (type(error) not in (int,float) or not isfinite(error) or error<0): raise ValueError('invalid error bound')
        self.center,self.marker=role['center'],role['marker']; self.goal_x=goal_x; self.width=width
        self.radius,self.depth,self.half_width,self.error=radius,depth,half_width,error
        self.t=self.zone=self.near=self.goal_side=self.distance=self.lower=self.upper=0.
        self.snapshot=None

    def add(self, edges, start, end):
        dt=end-start
        if not isfinite(dt) or dt<=0: raise ValueError('invalid interval')
        p,q=edges[self.center]; a,b=edges[self.marker]
        r=(a[0]-p[0],a[1]-p[1]); s=(b[0]-q[0],b[1]-q[1])
        def measure(v): return 0. if v is None else v[1]-v[0]
        self.t+=dt
        x=fraction_between(abs(self.goal_x-p[0]),abs(self.goal_x-q[0]),0,self.depth)
        y=fraction_between(p[1],q[1],self.width/2-self.half_width,self.width/2+self.half_width)
        if x and y: self.zone+=dt*max(0.,min(x[1],y[1])-max(x[0],y[0]))
        self.near+=dt*measure(_interval(r,s,self.radius))
        # Strictly goal-side; coincident longitudinal coordinates are neutral.
        sign=1 if self.goal_x>0 else -1
        v,w=sign*r[0],sign*s[0]
        if v>0 and w>=0 or w>0 and v>=0: self.goal_side+=dt
        elif v*w<0: self.goal_side+=dt*max(v,w)/abs(v-w)
        self.distance+=dt*hypot((r[0]+s[0])/2,(r[1]+s[1])/2)
        if self.error is not None:
            low=self.radius-2*self.error
            self.lower+=dt*measure(_interval(r,s,low)) if low>0 else (dt if low==0 and r==s==(0,0) else 0.)
            self.upper+=dt*measure(_interval(r,s,self.radius+2*self.error))
        if self.snapshot is None: self.snapshot={'second':(start+end)/2,'center':[(p[i]+q[i])/2 for i in (0,1)],'marker':[(a[i]+b[i])/2 for i in (0,1)]}

    def result(self):
        t=self.t
        return dict(center=self.center,marker=self.marker,observed_s=t,zone_s=self.zone if t else None,marker_proximity_s=self.near if t else None,marker_goal_side_s=self.goal_side if t else None,marker_mean_distance_m=self.distance/t if t else None,proximity_lower_s=self.lower if t and self.error is not None else None,proximity_upper_s=self.upper if t and self.error is not None else None,position_error_bound_m=self.error,radius_m=self.radius,zone_depth_m=self.depth,zone_half_width_m=self.half_width,snapshot=self.snapshot,status='experimental_reviewed_role_geometry')
