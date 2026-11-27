"""Calibrated 2D proximity proxy; not defensive intent or match playing time."""
from math import hypot, isfinite, sqrt
from numbers import Real


def _position(p):
    if not isinstance(p, (tuple, list)) or len(p) != 2:
        return None
    if not all(isinstance(x, Real) and not isinstance(x, bool) and isfinite(x) for x in p):
        return None
    return tuple(map(float, p))


def _inside(p, q, radius):
    """Fraction of linear relative trajectory within a circle, inclusive boundary."""
    dx, dy = q[0]-p[0], q[1]-p[1]
    length = hypot(dx, dy)
    if length == 0:
        return float(hypot(*p) <= radius)
    ux, uy = dx/length, dy/length
    along = p[0]*ux+p[1]*uy
    across = abs(p[0]*uy-p[1]*ux)
    if across >= radius:
        return 0.0
    half = sqrt((radius-across)*(radius+across))
    lo, hi = (-along-half)/length, (-along+half)/length
    return max(0.0, min(1.0, hi)-max(0.0, lo))


def measure_pair(frames, attacker, defender, radius=1.5, max_gap=0.25, position_error_m=0.0):
    """Frames (video seconds, {id: (x,y) metres}); one uninterrupted context.
    position_error_m is a deterministic bound per player, not a confidence interval.
    Mean distance uses midpoint quadrature (32 subintervals). Identity and camera
    calibration must be validated upstream; split periods/possessions/camera cuts.
    """
    if attacker == defender:
        raise ValueError('distinct player IDs required')
    if not all(isinstance(v, Real) and isfinite(v) for v in (radius,max_gap,position_error_m)) or radius <= 0 or max_gap <= 0 or position_error_m < 0:
        raise ValueError('invalid thresholds')
    total = observed = close = lower = upper = weighted = 0.0
    prev = None
    for t, players in frames:
        if not isinstance(t, Real) or not isfinite(t):
            raise ValueError('invalid timestamp')
        a, b = _position(players.get(attacker)), _position(players.get(defender))
        p = None if a is None or b is None else (a[0]-b[0], a[1]-b[1])
        if prev is not None:
            dt = t-prev[0]
            if dt <= 0:
                raise ValueError('timestamps must increase')
            total += dt
            q = prev[1]
            if dt <= max_gap and p is not None and q is not None:
                observed += dt
                close += dt*_inside(q,p,radius)
                rlo = radius-2*position_error_m
                lower += dt*_inside(q,p,rlo) if rlo >= 0 else 0.0
                upper += dt*_inside(q,p,radius+2*position_error_m)
                weighted += dt*sum(hypot(q[0]+(p[0]-q[0])*(i+.5)/32,q[1]+(p[1]-q[1])*(i+.5)/32) for i in range(32))/32
        prev = t,p
    return {'observed_s':observed,'coverage':observed/total if total else None,
            'proximity_s':close if observed else None,
            'mean_distance_m':weighted/observed if observed else None,
            'proximity_fraction':close/observed if observed else None,
            'proximity_lower_s':lower if observed else None,
            'proximity_upper_s':upper if observed else None,
            'window_s':total,'position_error_m':position_error_m,'status':'prototype'}


def self_test():
    from math import isclose
    from random import Random
    def run(x,y,**kw):
        return measure_pair([(0,{'a':x,'b':(0,0)}),(.2,{'a':y,'b':(0,0)})],'a','b',**kw)
    assert isclose(run((1,0),(2,0))['proximity_s'],.1)
    assert isclose(run((1,0),(2,0))['mean_distance_m'],1.5)
    assert isclose(run((-2,0),(2,0))['proximity_s'],.15)
    assert isclose(run((-2,0),(2,0))['mean_distance_m'],1)
    assert run((-2,1.5),(2,1.5))['proximity_s']==0
    assert run((1.5,0),(1.5,0))['proximity_fraction']==1
    assert run((2,0),(2,0))['proximity_fraction']==0
    assert run((1,0),(1,0))['proximity_fraction']==1
    assert run((0,0),(0,0),max_gap=.1)['proximity_s'] is None
    assert run((float('nan'),0),(1,0))['coverage']==0
    assert run((1,),(1,0))['proximity_s'] is None
    assert run(('x',0),(1,0))['proximity_s'] is None
    assert measure_pair([], 'a','b')['coverage'] is None
    r=run((1.4,0),(1.4,0),position_error_m=.1)
    assert r['proximity_lower_s']==0 and r['proximity_upper_s']==.2
    r=measure_pair([(0,{'a':(1,0),'b':(0,0)}),(.2,{'a':(2,0),'b':(0,0)}),(.4,{})],'a','b')
    assert isclose(r['coverage'],.5)
    for frames, a,b in [([], 'a','a'), ([(0,{}),(0,{})],'a','b'), ([(float('nan'),{})],'a','b')]:
        try: measure_pair(frames,a,b)
        except ValueError: pass
        else: raise AssertionError('invalid input accepted')
    rng=Random(42)
    for _ in range(250):
        p,q=[tuple(rng.uniform(-4,4) for _ in range(2)) for j in range(2)]
        f=_inside(p,q,1.5)
        assert 0<=f<=1 and isclose(f,_inside(q,p,1.5),abs_tol=1e-12)
        oracle=sum(hypot(p[0]+(q[0]-p[0])*(i+.5)/4000,p[1]+(q[1]-p[1])*(i+.5)/4000)<=1.5 for i in range(4000))/4000
        assert abs(f-oracle)<=.0005
    print('18 deterministic checks + 250 seeded geometry cases passed')

if __name__ == '__main__':
    self_test()
