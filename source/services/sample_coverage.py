"""Duration coverage counts union of distinct processed video intervals."""
from math import isfinite
def interval_union_seconds(intervals,duration):
    if not duration or not isfinite(float(duration)) or duration<=0:return 0.0
    rows=[]
    for a,b in intervals:
        a,b=float(a),float(b)
        if not isfinite(a) or not isfinite(b):continue
        a,b=max(0.,a),min(float(duration),b)
        if b>a:rows.append((a,b))
    total=0.;left=right=0.
    for a,b in sorted(rows):
        if a>right:
            total+=right-left;left,right=a,b
        else:right=max(right,b)
    return total+right-left
