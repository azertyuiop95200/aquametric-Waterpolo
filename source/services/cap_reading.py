"""Deferred cap-number evidence: sharp images first, identities only after review.

Sharpness is an image-ranking heuristic, not a digit confidence score. No OCR
is implied. Never bridge an unobserved interval or assume a cap colour is a club.
"""
import cv2
import numpy as np
from collections import Counter

def crop_observation(frame,point):
    h,w=frame.shape[:2]
    x,y=round(float(point["x"])*w),round(float(point["y"])*h)
    r=max(12,round(min(h,w)*.035))
    if not (r<=x<w-r and r<=y<h-r):return None
    crop=frame[y-r:y+r+1,x-r:x+r+1]
    if crop.size==0:return None
    grey=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    sharpness=float(cv2.Laplacian(grey,cv2.CV_64F).var())
    return {"second":float(point["second"]),"x":float(point["x"]),"y":float(point["y"]),
            "radius_x":round(r/w,5),"radius_y":round(r/h,5),"sharpness":round(sharpness,2)}

def select_reading_frames(rows,limit=8,min_spacing=.4):
    picked=[]
    for r in sorted((r for r in rows if r),key=lambda r:-r["sharpness"]):
        if all(abs(r["second"]-p["second"])>=min_spacing for p in picked):
            picked.append(r)
        if len(picked)>=limit:break
    return sorted(picked,key=lambda r:r["second"])

def reviewed_identity(votes):
    """Only explicitly reviewed readings of the SAME uninterrupted track.
    Reject disagreement; two distinct instants required. Never equate colour
    alone with side, and never infer missing number. This is not full re-ID.
    """
    valid=[]
    for v in votes:
        if v.get("reviewed") is not True or v.get("side") not in {"for","against"}:continue
        n=v.get("cap_number")
        if type(n) is not int or not 1<=n<=30:continue
        if not isinstance(v.get("second"),(float,int)) or not np.isfinite(v["second"]):continue
        valid.append(v)
    keys={(v["side"],v["cap_number"]) for v in valid}
    if len(keys)!=1:return None
    times=sorted({v["second"] for v in valid})
    if len(times)<2 or times[-1]-times[0]<.4:return None
    side,cap=next(iter(keys)); colours=Counter(v.get("colour","unknown") for v in valid)
    return {"side":side,"cap_number":cap,"colours":sorted(colours),"status":"reviewed_multi_frame",
            "evidence_seconds":times}

