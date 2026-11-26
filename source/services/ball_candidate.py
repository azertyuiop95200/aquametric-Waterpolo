"""Conservative local ball-colour hypothesis tracker; not a trained detector.
Only measured 2D pixel observations, never a sports event or a metric distance.
"""
import math
import cv2
import numpy as np

def detect_candidates(frame):
    h,w=frame.shape[:2]
    hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,(15,115,135),(38,255,255))
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    for c in contours:
        area=cv2.contourArea(c); perimeter=cv2.arcLength(c,True)
        if perimeter<=0 or area<9 or area>h*w*.003: continue
        circularity=4*math.pi*area/(perimeter*perimeter)
        (x,y),radius=cv2.minEnclosingCircle(c)
        if radius<2 or circularity<.62 or radius>min(h,w)*.035: continue
        if not (.04*w<x<.96*w and .08*h<y<.94*h): continue
        reach=max(5,int(radius*4))
        roi=hsv[max(0,int(y)-reach):min(h,int(y)+reach+1),max(0,int(x)-reach):min(w,int(x)+reach+1)]
        if not roi.size: continue
        water=cv2.inRange(roi,(75,35,40),(135,255,255))
        if np.count_nonzero(water)/water.size<.45: continue
        candidates.append((float(x),float(y)))
    return candidates

def track_frames(frames, min_points=5):
    tracks=[]; points=[]; previous=None; shape=None
    def finish():
        nonlocal points,previous
        if len(points)>=min_points:
            span=max(math.hypot(p['x']-points[0]['x'],p['y']-points[0]['y']) for p in points)
            if span>=.015:
                tracks.append({'start_second':points[0]['second'],'end_second':points[-1]['second'],'points':points})
        points=[]; previous=None
    for t,frame in frames:
        h,w=frame.shape[:2]
        if shape is not None and shape!=(h,w): finish()
        shape=(h,w)
        candidates=detect_candidates(frame)
        if previous is not None and t-previous[0]>.35: finish()
        if previous is None:
            if len(candidates)!=1: continue
            x,y=candidates[0]
        else:
            _,px,py=previous
            near=[p for p in candidates if math.hypot((p[0]-px)/w,(p[1]-py)/h)<=.12]
            if len(near)!=1:
                finish(); continue
            x,y=near[0]
        points.append({'second':round(float(t),3),'x':round(x/w,5),'y':round(y/h,5)})
        previous=(t,x,y)
    finish()
    return tracks

def scan_windows(video_path, duration, moments, max_windows=4):
    """Read bounded contiguous windows; never treat missing frames as detections."""
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release(); return {'status':'unreadable','tracks':[],'windows':0}
    tracks=[]; windows=0; used=[]
    try:
        for m in moments[:max_windows*3]:
            if windows>=max_windows: break
            t=float(m.get('second',0)); start=max(0,t-1.5); end=min(float(duration),start+3)
            if end-start<.5 or any(start<b and end>a for a,b in used): continue
            used.append((start,end)); windows+=1
            def frames():
                for stamp in np.arange(start,end,.125):
                    cap.set(cv2.CAP_PROP_POS_MSEC,float(stamp)*1000)
                    ok,frame=cap.read()
                    if ok and frame is not None:
                        if frame.shape[1]>960:
                            frame=cv2.resize(frame,(960,max(1,round(frame.shape[0]*960/frame.shape[1]))))
                        yield float(stamp),frame
            tracks.extend(track_frames(frames()))
    finally: cap.release()
    return {'status':'candidate_only','tracks':tracks,'windows':windows,
            'note':'Hypothèses de trajectoire 2D par couleur et continuité, uniquement dans les fenêtres inspectées. Aucun ballon, tir, identité ou distance certifié.'}
