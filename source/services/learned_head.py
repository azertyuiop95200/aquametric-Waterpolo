"""Experimental local linear HOG classifier; not verified player identities."""
import cv2
import numpy as np
from math import hypot

VERSION='local-hog-head-review-v1'

def hog():return cv2.HOGDescriptor((32,32),(16,16),(8,8),(8,8),9)

def detect_heads(frame, weights, bias, *, limit=24):
    if not isinstance(frame,np.ndarray) or frame.dtype!=np.uint8 or frame.ndim!=3 or frame.shape[2]!=3 or not 128<=frame.shape[0]<=2160 or not 128<=frame.shape[1]<=3840 or not .8<=frame.shape[1]/frame.shape[0]<=3.2:raise ValueError('Image invalide')
    if type(limit) is not int or not 1<=limit<=24:raise ValueError('Limite invalide')
    model=hog()
    try:v=np.asarray(weights,dtype=np.float32)
    except (TypeError,ValueError,OverflowError):raise ValueError('Modèle invalide') from None
    if type(bias) not in (int,float) or v.shape!=(model.getDescriptorSize(),) or not np.isfinite(v).all() or not np.isfinite(bias) or abs(bias)>1e4 or np.max(np.abs(v))>1e4:raise ValueError('Modèle invalide')
    model.setSVMDetector(np.r_[v,np.float32(bias)])
    h,w=frame.shape[:2];gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY); hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV);water=cv2.inRange(hsv,(65,30,40),(135,255,255));rows=[]
    for scale in (.8,1.,1.3,1.65):
        factor=scale*720/h
        scaled=cv2.resize(gray,None,fx=factor,fy=factor,interpolation=cv2.INTER_LINEAR)
        loc,scores=model.detect(scaled,hitThreshold=0,winStride=(8,8),padding=(0,0))
        for (x,y),score in zip(loc,scores):
            cx,cy=(x+16)/factor,(y+16)/factor
            if not .025*w<cx<.98*w or not .095*h<cy<.97*h:continue
            r=max(3,round(25*h/720));a,b=int(cx),int(cy);roi=water[max(0,b-r):min(h,b+r+1),max(0,a-r):min(w,a+r+1)]
            if np.mean(roi>0)<.24:continue
            rows.append(dict(kind='head',x=float(cx/w),y=float(cy/h),ranking_score=float(score),status='learned_candidate_not_verified',colour='unknown'))
    out=[]
    for d in sorted(rows,key=lambda x:-x['ranking_score']):
        if any(hypot((d['x']-q['x'])*w,(d['y']-q['y'])*h)<17*h/720 for q in out):continue
        out.append(d)
        if len(out)==limit:break
    return out


def review_disagreements(baseline, learned, width, height, *, extra_limit=6):
    """Keep the baseline intact; add bounded non-overlapping learned suggestions.
    No agreement is proof of a real head; these are review priorities only.
    """
    if type(width) is not int or type(height) is not int or not 128<=width<=3840 or not 128<=height<=2160 or not .8<=width/height<=3.2:raise ValueError('Dimensions invalides')
    if type(extra_limit) is not int or not 0<=extra_limit<=6:raise ValueError('Budget de revue invalide')
    for ds in (baseline,learned):
        if not isinstance(ds,list) or len(ds)>24:raise ValueError('Propositions hors limites')
        for d in ds:
            if not isinstance(d,dict) or d.get('kind')!='head' or not all(type(d.get(k)) in (int,float) and np.isfinite(d[k]) and 0<=d[k]<=1 for k in ('x','y')):raise ValueError('Proposition invalide')
    # The learned list is already ranked by its uncalibrated classifier margin.
    extras=[]
    for d in learned:
        if len(extras)>=extra_limit:break
        if any(hypot((d['x']-q['x'])*width,(d['y']-q['y'])*height)<17*height/720 for q in baseline+extras):continue
        extras.append(dict(d,review_source='learned_only',status='review_candidate_not_verified'))
    return dict(engine=VERSION,baseline=[dict(d) for d in baseline],additional_review_candidates=extras,
                total_review_candidates=len(baseline)+len(extras),statistical_use_allowed=False,
                identity_verified=False,metrics_validated=False,
                note='Suggestions de revue, pas des têtes confirmées. Marges de classement non probabilistes.')
