"""Reviewed goalkeeper placement; planar static projection, never save probability."""
from math import atan2, degrees, hypot, isfinite


def number(v): return type(v) in (int,float) and isfinite(v)

def snapshot(carrier, keeper, goal_x, length, width, goal_width, span=None):
    if not all(map(number,(*carrier,*keeper,goal_x,length,width,goal_width))) or not 0<goal_width<=width or goal_x not in (0,length):
        raise ValueError('invalid metric goal or positions')
    if any(not (0<=x<=length and 0<=y<=width) for x,y in (carrier,keeper)):
        raise ValueError('outside calibrated pool')
    if span is not None and (not number(span) or not 0<span<=3): raise ValueError('invalid assumed lateral span')
    x,y=carrier; k,j=keeper; cy=width/2; d=abs(goal_x-x); g=abs(goal_x-k)
    lo,hi=cy-goal_width/2,cy+goal_width/2
    angle=degrees(atan2(hi-y,d)-atan2(lo-y,d)) if d>1e-8 else None
    r=dict(keeper_depth_m=g,keeper_lateral_offset_m=j-cy,carrier_distance_to_goal_m=hypot(d,y-cy),goal_angle_deg=angle,alignment_error_m=None,projected_interval_y_m=None,projected_fraction=None)
    # Carrier centre is a positional proxy, not the observed release point.
    if d>1e-8 and 0<=g<d-1e-8:
        f=(d-g)/d; axis=y+f*(cy-y);r['alignment_error_m']=j-axis
        if span is not None:
            a=max(lo,y+(j-span/2-y)/f);b=min(hi,y+(j+span/2-y)/f)
            r['projected_interval_y_m']=[a,b] if b>a else None
            r['projected_fraction']=max(0.,b-a)/goal_width
    return r


class KeeperAccumulator:
    def __init__(self, role, carrier, defenders, goal_x, length, width):
        if not isinstance(role,dict) or role.get('provenance')!='coach_review' or role.get('keeper') not in defenders or goal_x not in (0,length): raise ValueError('reviewed goalkeeper required')
        self.keeper=role['keeper'];self.carrier=carrier;self.goal_x=goal_x;self.length=length;self.width=width
        self.goal_width=role.get('goal_width_m');self.span=role.get('assumed_lateral_span_m')
        if not number(self.goal_width) or not 0<self.goal_width<=width or (self.span is not None and (not number(self.span) or not 0<self.span<=3)): raise ValueError('explicit goal width and valid optional span required')
        self.observed=0.;self.lateral_distance=0.;self.depth_distance=0.;self.first=None
        self.sums={k:[0.,0.] for k in ('keeper_depth_m','keeper_lateral_offset_m','carrier_distance_to_goal_m','goal_angle_deg','alignment_abs_error_m','projected_fraction')}

    def add(self, edges, start, end):
        dt=end-start
        if not number(dt) or dt<=0: raise ValueError('invalid interval')
        p,q=edges[self.keeper];a,b=edges[self.carrier]
        mid=lambda u,v:tuple((x+y)/2 for x,y in zip(u,v))
        c,k=mid(a,b),mid(p,q);r=snapshot(c,k,self.goal_x,self.length,self.width,self.goal_width,self.span)
        self.observed+=dt;self.lateral_distance+=abs(q[1]-p[1]);self.depth_distance+=abs(q[0]-p[0])
        r['alignment_abs_error_m']=abs(r['alignment_error_m']) if r['alignment_error_m'] is not None else None
        for key,v in self.sums.items():
            if r[key] is not None:v[0]+=dt*r[key];v[1]+=dt
        if self.first is None:self.first=dict(second=(start+end)/2,carrier=c,keeper=k,**r)

    def result(self):
        return dict(keeper=self.keeper,carrier=self.carrier,observed_s=self.observed,goal_width_m=self.goal_width,assumed_lateral_span_m=self.span,lateral_distance_m=self.lateral_distance if self.observed else None,depth_distance_m=self.depth_distance if self.observed else None,means={k:v[0]/v[1] if v[1] else None for k,v in self.sums.items()},supports_s={k:v[1] for k,v in self.sums.items()},snapshot=self.first,position_error_m=None,save_probability=None,reaction_time_s=None,status='experimental_planar_keeper_geometry')
