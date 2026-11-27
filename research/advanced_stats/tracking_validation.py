"""Coverage-aware image-plane checkpoint validation, with explicit seed exclusion."""
from math import hypot, isfinite
from statistics import median, mean


def evaluate(references, predictions, *, seed_frames=(), tolerance_px=10.):
    """Inputs map (local_track_id, frame_index) to native (x,y) pixels.

    This is conditional tracking accuracy, not detection recall or re-ID accuracy.
    Missing predictions remain in the denominator of coverage and usable fraction.
    Seed frames are not validation evidence. No metric distance is inferred.
    """
    if type(tolerance_px) not in (int,float) or not isfinite(tolerance_px) or tolerance_px<=0:
        raise ValueError('positive pixel tolerance required')
    seeds=set(seed_frames)
    def xy(p):
        if not isinstance(p,(list,tuple)) or len(p)!=2 or any(type(v) not in (int,float) or not isfinite(v) for v in p):
            raise ValueError('finite native pixel pair required')
        return p
    for k in references:
        if not isinstance(k,tuple) or len(k)!=2 or not isinstance(k[0],str) or not k[0] or type(k[1]) is not int or k[1]<0:
            raise ValueError('invalid checkpoint key')
    errors=[];n=0;good=0
    for k,p in references.items():
        if k[1] in seeds:continue
        n+=1;p=xy(p)
        q=predictions.get(k)
        if q is None:continue
        q=xy(q);d=hypot(q[0]-p[0],q[1]-p[1]);errors.append(d);good+=d<=tolerance_px
    errors.sort()
    def quantile(p):
        if not errors:return None
        i=(len(errors)-1)*p;lo=int(i);hi=min(lo+1,len(errors)-1);return errors[lo]+(i-lo)*(errors[hi]-errors[lo])
    return dict(expected=n,available=len(errors),coverage=len(errors)/n if n else None,
                median_px=median(errors) if errors else None,mean_px=mean(errors) if errors else None,p90_px=quantile(.9),
                within_tolerance=good,tolerance_px=tolerance_px,usable_fraction=good/n if n else None)
