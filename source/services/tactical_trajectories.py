"""Tactical proxies from calibrated 2D tracks, one stable possession per call.
No automatic identity, calibration, or tactical-intent inference.
"""
from math import hypot, isfinite, sqrt
from numbers import Real


def _number(v):
    return isinstance(v, Real) and not isinstance(v, bool) and isfinite(v)


def _point(v):
    return tuple(v) if isinstance(v, (list, tuple)) and len(v) == 2 and all(map(_number, v)) else None


def _sub(a, b):
    return (a[0]-b[0], a[1]-b[1])


def _interval(p, q, r):
    """Time fraction interval inside radius along a linear relative trajectory."""
    dx, dy = _sub(q, p)
    length = hypot(dx, dy)
    if not length:
        return (0., 1.) if hypot(*p) <= r else None
    ux, uy = dx/length, dy/length
    cross = abs(p[0]*uy-p[1]*ux)
    if cross >= r:
        return None  # moving tangent has zero duration
    along = p[0]*ux+p[1]*uy
    half = sqrt((r-cross)*(r+cross))
    lo, hi = max(0., (-along-half)/length), min(1., (-along+half)/length)
    return (lo, hi) if hi > lo else None


def _exposure(intervals, minimum):
    """Length of union with at least minimum simultaneous defenders."""
    events = sorted((t, d) for lo, hi in intervals for t, d in ((lo, 1), (hi, -1)))
    last, count, duration = 0., 0, 0.
    for t, delta in events:
        if count >= minimum:
            duration += t-last
        count += delta
        last = t
    return duration


def analyze(frames, attackers, defenders, *, carrier=None, radius_m=1.5,
            max_gap_s=.25, provenance='synthetic', window_id='segment'):
    """frames: (video seconds, {player_id: [x_m,y_m]}), no camera/phase cuts.
    Teams are explicit, fixed, complete active rosters for this window. A known
    carrier must hold the ball throughout; otherwise pass carrier=None. A caller
    supplying verified_tracks is responsible for validation, not this function.
    """
    A, D = tuple(attackers), tuple(defenders)
    ids = A+D
    if not A or not D or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('distinct nonempty team IDs required')
    if carrier is not None and carrier not in A:
        raise ValueError('carrier must be an attacker')
    if not all(_number(v) and v > 0 for v in (radius_m,max_gap_s)) or provenance not in ('synthetic','verified_tracks'):
        raise ValueError('invalid configuration')
    if not isinstance(window_id,str) or not window_id:
        raise ValueError('window_id required')
    movement = {i: [0.,0.] for i in ids} # observed seconds, distance
    pressure = {i: [0.,0.,0.,0.,0.] for i in A} # seconds, union, double, separation change, positive separation
    previous = None
    total = 0.
    for t, positions in frames:
        if not _number(t) or t < 0:
            raise ValueError('invalid timestamp')
        p = {i: _point(positions.get(i)) for i in ids}
        if previous is not None:
            t0, q = previous
            dt = t-t0
            if dt <= 0:
                raise ValueError('timestamps must increase')
            total += dt
            if dt <= max_gap_s:
                valid = {i for i in ids if q[i] is not None and p[i] is not None}
                for i in valid:
                    movement[i][0] += dt
                    movement[i][1] += hypot(*_sub(p[i],q[i]))
                if all(i in valid for i in D):
                    for i in A:
                        if i not in valid:
                            continue
                        before = [_sub(q[i],q[j]) for j in D]
                        after = [_sub(p[i],p[j]) for j in D]
                        intervals = [v for a,b in zip(before,after) if (v := _interval(a,b,radius_m)) is not None]
                        m = pressure[i]
                        m[0] += dt
                        m[1] += dt*_exposure(intervals,1)
                        m[2] += dt*_exposure(intervals,2)
                        delta = min(map(lambda x:hypot(*x),after))-min(map(lambda x:hypot(*x),before))
                        m[3] += delta
                        m[4] += max(0.,delta)
        previous = t,p
    def ratio(a,b): return a/b if b else None
    return {'schema_version':'1.0','window_id':window_id,'window_s':total,
            'provenance':provenance,'status':'experimental_proxy','radius_m':radius_m,'max_gap_s':max_gap_s,
            'players':[{'player_id':i,'observed_s':m[0],'coverage':ratio(m[0],total),
                        'distance_m':m[1] if m[0] else None,'mean_speed_mps':ratio(m[1],m[0])}
                       for i,m in movement.items()],
            'attackers':[{'player_id':i,'full_defender_observed_s':m[0],'coverage':ratio(m[0],total),
                          'team_proximity_s':m[1] if m[0] else None,'double_proximity_s':m[2] if m[0] else None,
                          'team_proximity_fraction':ratio(m[1],m[0]),
                          'offball_net_separation_delta_m':m[3] if m[0] and carrier is not None and i!=carrier else None,
                          'offball_positive_separation_m':m[4] if m[0] and carrier is not None and i!=carrier else None}
                         for i,m in pressure.items()]}
