"""Prioritise disagreements by independent neighbouring detections, not identity proof."""
from math import hypot
import cv2
import numpy as np
from services.learned_head import review_disagreements
from services.head_flow_tracking import _flow

VERSION='temporal-head-review-v1'

def prioritize(previous, current, following, baseline, learned, before, after, *, limit=3):
    """Three adjacent frames, same resolution. Neighbour candidates from the baseline.
    Rank by number of neighbours supported by reciprocal optical flow and proximity.
    No new statistical detections or identities are produced.
    """
    if type(limit) is not int or not 0<=limit<=6:raise ValueError('Budget invalide.')
    if not isinstance(current,np.ndarray) or current.ndim!=3 or current.shape[2]!=3:raise ValueError('Image centrale invalide.')
    if not all(isinstance(f,np.ndarray) and f.dtype==np.uint8 and f.shape==current.shape for f in (previous,current,following)):raise ValueError('Images incompatibles.')
    h,w=current.shape[:2];scale=h/720
    # Validate all lists using the same domain and no output from this call.
    review_disagreements(before,after,w,h,extra_limit=0)
    review_disagreements(baseline,learned,w,h,extra_limit=0)
    extras=[]
    for i,d in enumerate(learned):
        if any(hypot((d['x']-q['x'])*w,(d['y']-q['y'])*h)<17*scale for q in baseline+extras):continue
        extras.append(dict(d,learned_rank=i+1))
    g=cv2.cvtColor(current,cv2.COLOR_BGR2GRAY);points=[(d['x']*w,d['y']*h) for d in extras]
    evidence=[]
    for frame,ds in ((previous,before),(following,after)):
        q=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        cut=float(cv2.absdiff(cv2.resize(g,(160,90)),cv2.resize(q,(160,90))).mean())>32
        flow=[None]*len(points) if cut else _flow(g,q,points)
        support=[]
        for p in flow:
            if p is None: support.append(None);continue
            distances=sorted(hypot(p[0]-d['x']*w,p[1]-d['y']*h) for d in ds)
            # Refuse ambiguous neighbours; do not identify the candidate with a player.
            support.append(round(distances[0],4) if distances and distances[0]<=18*scale and (len(distances)==1 or distances[1]-distances[0]>6*scale) else None)
        evidence.append(support)
    rows=[]
    for i,d in enumerate(extras):
        a,b=evidence[0][i],evidence[1][i];n=int(a is not None)+int(b is not None)
        rows.append(dict(d,previous_support_px=a,following_support_px=b,temporal_support_count=n,status='review_candidate_not_verified',review_source='temporal_priority'))
    rows.sort(key=lambda d:(-d['temporal_support_count'],d['learned_rank']))
    return dict(engine=VERSION,baseline=[dict(d) for d in baseline],additional_review_candidates=rows[:limit],eligible_candidates=len(rows),statistical_use_allowed=False,identity_verified=False,metrics_validated=False,note='Ordre de revue uniquement ; une proximité optique ne confirme ni tête ni identité.')
