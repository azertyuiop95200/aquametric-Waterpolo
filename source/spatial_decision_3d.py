"""Metric 3D decision geometry. Coordinates in metres, z above water.
No calibrated probabilities: outputs are geometric feasibility indicators.
"""
from dataclasses import dataclass
from math import atan2, degrees, sqrt, isfinite
from typing import Optional

Vec = tuple[float, float, float]

def sub(a: Vec,b: Vec)->Vec:
    return tuple(x-y for x,y in zip(a,b))

def norm(a: Vec)->float:
    return sqrt(sum(x*x for x in a))

def segment_distance(p: Vec, a: Vec, b: Vec) -> float:
    ab=sub(b,a)
    length2=sum(x*x for x in ab)
    u=max(0.,min(1.,sum(x*y for x,y in zip(sub(p,a),ab))/length2)) if length2 else 0.
    return norm(sub(p,tuple(a[i]+u*ab[i] for i in range(3))))

@dataclass(frozen=True)
class ReachSegment:
    """Explicit relative endpoints, moving with the defender, not inferred anatomy."""
    part: str
    start_offset: Vec
    end_offset: Vec
    radius: float
    def __post_init__(self):
        if self.part not in ("body","left_arm","right_arm"):
            raise ValueError("Invalid reach part")
        if len(self.start_offset)!=3 or len(self.end_offset)!=3 or not all(isfinite(x) for x in (*self.start_offset,*self.end_offset,self.radius)):
            raise ValueError("Invalid reach geometry")
        if not .03 <= self.radius <= .8 or max(norm(self.start_offset),norm(self.end_offset))>2:
            raise ValueError("Reach outside model bounds")

@dataclass(frozen=True)
class Track:
    id: str
    position: Vec
    velocity: Vec = (0.,0.,0.)
    radius: float = .65
    confidence: float = 1.
    reach_segments: tuple[ReachSegment,...] = ()
    def __post_init__(self):
        if not all(isfinite(x) for x in (*self.position,*self.velocity,self.radius,self.confidence)):
            raise ValueError("nonfinite track")
        if self.radius < 0 or not 0 <= self.confidence <= 1:
            raise ValueError("invalid track")
        if len(self.reach_segments)>3 or len({s.part for s in self.reach_segments})!=len(self.reach_segments):
            raise ValueError("Duplicate or excessive reach parts")

def goal_angles(origin: Vec, goal_x: float, center_y: float, width: float=3., height: float=.9):
    if width<=0 or height<=0 or abs(goal_x-origin[0])<1e-8:
        raise ValueError("invalid goal geometry")
    dx=abs(goal_x-origin[0])
    lo=center_y-width/2-origin[1]
    hi=center_y+width/2-origin[1]
    distance=sqrt(dx*dx+(center_y-origin[1])**2)
    return {"horizontal_deg":degrees(atan2(hi,dx)-atan2(lo,dx)),
            "vertical_center_deg":degrees(atan2(height-origin[2],distance)-atan2(-origin[2],distance)),
            "distance_m":distance}

def trajectory(start: Vec,end: Vec,duration: float,gravity: float=9.81,steps: int=40):
    if duration<=0 or steps<2 or gravity<0 or not all(isfinite(x) for x in (*start,*end,duration,gravity)):
        raise ValueError("invalid trajectory")
    return [(duration*i/steps, tuple(start[j]+(end[j]-start[j])*i/steps+
        (gravity*duration**2/2*(i/steps)*(1-i/steps) if j==2 else 0)
        for j in range(3))) for i in range(steps+1)]

def assess(start: Vec,end: Vec,duration: float,defenders: Optional[list[Track]], observation_confidence: float,
           gravity: float=9.81, ball_radius: float=.11, steps: int=40):
    if not 0<=observation_confidence<=1 or ball_radius<0:
        raise ValueError("invalid confidence or radius")
    path=trajectory(start,end,duration,gravity,steps)
    velocity=tuple((end[j]-start[j])/duration+(gravity*duration/2 if j==2 else 0) for j in range(3))
    result={"flight_s":duration,"launch_speed_m_s":norm(velocity),
            "launch_elevation_deg":degrees(atan2(velocity[2],norm((velocity[0],velocity[1],0)))),
            "peak_height_m":max(p[2] for _,p in path),"path":[{"t_s":t,"xyz_m":p} for t,p in path],
            "clearance_m":None,"closest_defender":None,"closest_time_s":None,"closest_part":None,
            "confidence":observation_confidence,"status":"unknown","model":"ballistic_constant_velocity_v2"}
    if defenders is None or not defenders or observation_confidence==0:
        return result
    # Conservative discretization allowance using bound on relative speed.
    candidates=[]
    for d in defenders:
        bound=norm(velocity)+gravity*duration+norm(d.velocity)
        for t,p in path:
            q=tuple(d.position[j]+d.velocity[j]*t for j in range(3))
            allowance=ball_radius+bound*duration/(2*steps)
            if not any(s.part=="body" for s in d.reach_segments):
                candidates.append((norm(sub(p,q))-d.radius-allowance,d.id,t,"sphere_proxy"))
            for s in d.reach_segments:
                a=tuple(q[i]+s.start_offset[i] for i in range(3))
                b=tuple(q[i]+s.end_offset[i] for i in range(3))
                candidates.append((segment_distance(p,a,b)-s.radius-allowance,d.id,t,s.part))
    c,who,t,part=min(candidates)
    result.update(clearance_m=c,closest_defender=who,closest_time_s=t,closest_part=part,
                  confidence=min(observation_confidence,*(d.confidence for d in defenders)),
                  status="potential_obstruction" if c<=0 else "clear_in_model")
    if result["confidence"]<.5:
        result["status"]="uncertain"
    return result

def compare_options(start: Vec, options: list[dict], defenders: Optional[list[Track]], confidence: float):
    """Options must be legal candidates supplied at the decision timestamp.
    No outcome information or future measured defender positions are accepted.
    """
    evaluated=[]
    for option in options:
        r=assess(start,tuple(option["target"]),option["duration_s"],defenders,confidence)
        evaluated.append({"id":option["id"],"kind":option["kind"],**r})
    # Comparable geometry only, not a ranking of tactical expected value.
    return sorted(evaluated,key=lambda r:(r["status"]=="clear_in_model",r["clearance_m"] if r["clearance_m"] is not None else float("-inf")),reverse=True)
