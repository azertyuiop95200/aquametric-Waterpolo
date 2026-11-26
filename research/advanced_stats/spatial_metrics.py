"""Prototype spatial metrics. Coordinates in calibrated metres, time in seconds.
No interpolation across missing frames; thresholds are configurable hypotheses.
Run python spatial_metrics.py to execute synthetic checks.
"""
from math import hypot, isfinite

def measure_pair(frames, attacker, defender, radius=1.5, max_gap=0.25):
    """Time-weighted proximity, not proof of defensive intent.
    frames: iterable of (timestamp, {player_id: (x,y)}).
    IDs must already be validated by tracking.
    """
    if not (isfinite(radius) and radius > 0 and isfinite(max_gap) and max_gap > 0):
        raise ValueError("Invalid thresholds")
    total = observed = close = weighted = 0.0
    prev = None
    def distance(players):
        a,b = players.get(attacker),players.get(defender)
        if a is None or b is None or not all(isfinite(x) for x in (*a,*b)):
            return None
        return hypot(a[0]-b[0],a[1]-b[1])
    for t, players in frames:
        if not isfinite(t): raise ValueError("Invalid timestamp")
        d = distance(players)
        if prev is not None:
            dt = t-prev[0]
            if dt <= 0: raise ValueError("Timestamps must increase")
            total += dt
            if dt <= max_gap and d is not None and prev[1] is not None:
                observed += dt
                weighted += dt*(d+prev[1])/2
                a,b = prev[1],d
                if max(a,b)<=radius: close+=dt
                elif min(a,b)<radius: close+=dt*(radius-min(a,b))/abs(b-a)
        prev = t,d
    return {"observed_s":observed,"coverage":observed/total if total else None,
            "proximity_s":close if observed else None,
            "mean_distance_m":weighted/observed if observed else None,
            "proximity_fraction":close/observed if observed else None,
            "status":"prototype"}

def self_test():
    from math import isclose
    a = {"a":(0,0),"b":(1,0)}
    b = {"a":(0,0),"b":(2,0)}
    r=measure_pair([(0,a),(.2,b),(.4,{})],"a","b")
    assert isclose(r["proximity_s"],.1)
    assert isclose(r["coverage"],.5)
    assert isclose(r["mean_distance_m"],1.5)
    assert measure_pair([(0,a),(1,a)],"a","b")["proximity_s"] is None
    assert measure_pair([(0,a),(.2,a)],"a","b")["proximity_fraction"] == 1
    assert measure_pair([(0,b),(.2,b)],"a","b")["proximity_fraction"] == 0
    print("6 synthetic assertions passed")
if __name__ == "__main__":
    self_test()
