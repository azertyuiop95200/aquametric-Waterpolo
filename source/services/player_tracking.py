"""Conservative head tracklets; image coordinates only until calibrated.
A manual seed or a colour proposal is not a verified roster identity.
"""
import cv2
import numpy as np
from math import hypot
from services.cap_reading import crop_observation, select_reading_frames


def cap_proposals(frame):
    """Skin-adjacent dark/light head blobs in water, not a trained detector."""
    h,w=frame.shape[:2]; hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    water=cv2.inRange(hsv,(65,35,40),(135,255,255))
    skin=cv2.bitwise_or(cv2.inRange(hsv,(0,45,65),(25,255,255)),cv2.inRange(hsv,(165,45,65),(179,255,255)))
    dark=cv2.inRange(hsv,(0,0,0),(179,255,85))
    light=cv2.inRange(hsv,(0,0,145),(179,75,255))
    out=[]
    for colour,mask in [('dark',dark),('light',light)]:
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            a=cv2.contourArea(c); (x,y),r=cv2.minEnclosingCircle(c)
            if a<12 or not 3<=r<=min(h,w)*.025 or a/(np.pi*r*r)<.28 or not (.03*w<x<.97*w and .14*h<y<.92*h):continue
            x0,y0=int(x),int(y); d=max(10,int(r*3))
            roi=(slice(max(0,y0-d),min(h,y0+d+1)),slice(max(0,x0-d),min(w,x0+d+1)))
            if np.mean(water[roi]>0)<.38 or np.mean(skin[roi]>0)<.055:continue
            out.append({'x':float(x/w),'y':float(y/h),'colour':colour,'score':float(a/(np.pi*r*r))})
    kept=[]
    for p in sorted(out,key=lambda q:-q['score']):
        if not any(hypot((p['x']-q['x'])*w,(p['y']-q['y'])*h)<12 for q in kept):kept.append(p)
    return kept[:24]


def track_frames(frames,seeds=None,max_gap=.25):
    """LK with forward/backward check; retire on ambiguity/cut; no re-ID."""
    prev=None; last=None; active={}; all_tracks=[]; n=0
    for t,frame in frames:
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY); h,w=gray.shape
        if prev is None:
            for i,p in enumerate(seeds if seeds is not None else cap_proposals(frame)):
                if not (0<=p['x']<=1 and 0<=p['y']<=1):continue
                track={'id':i+1,'colour':p.get('colour','unknown'),'cap_number':None,'team':None,'origin':'manual_seed' if seeds is not None else 'colour_candidate','points':[{'second':round(t,3),'x':p['x'],'y':p['y']}]}
                track['reading_frames']=[crop_observation(frame,track['points'][-1])]
                active[i+1]=(np.array([p['x']*w,p['y']*h],dtype=np.float32),track); all_tracks.append(track)
        elif t-last>max_gap or prev.shape!=gray.shape or float(np.mean(cv2.absdiff(prev,gray)))>45:
            break
        elif active:
            ids=list(active); old=np.array([active[i][0] for i in ids],np.float32).reshape(-1,1,2)
            args=dict(winSize=(21,21),maxLevel=2,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,20,.03))
            new,st,_=cv2.calcOpticalFlowPyrLK(prev,gray,old,None,**args)
            if new is None:break
            back,st2,_=cv2.calcOpticalFlowPyrLK(gray,prev,new,None,**args)
            if back is None:break
            for k,i in enumerate(ids):
                x,y=map(float,new[k,0]); error=float(np.linalg.norm(back[k,0]-old[k,0])); move=float(np.linalg.norm(new[k,0]-old[k,0]))
                near=sum(float(np.linalg.norm(new[k,0]-new[j,0]))<10 for j in range(len(ids)) if j!=k and st[j,0])
                if not st[k,0] or not st2[k,0] or error>1.25 or move>max(w,h)*.045 or near or not(0<=x<w and 0<=y<h):
                    active.pop(i,None);continue
                track=active[i][1]; track['points'].append({'second':round(t,3),'x':round(x/w,5),'y':round(y/h,5)});active[i]=(new[k,0],track)
                track['reading_frames'].append(crop_observation(frame,track['points'][-1]))
        prev=gray;last=t;n+=1
        if not active:break
    for tr in all_tracks:
        tr['reading_frames']=select_reading_frames(tr['reading_frames'])
    return [tr for tr in all_tracks if len(tr['points'])>=5],n


def scan_player_windows(path,duration,moments,seeds=None,max_windows=3):
    cap=cv2.VideoCapture(str(path)); tracks=[]; windows=[]
    if not cap.isOpened():cap.release();return {'status':'unreadable','tracks':[],'windows':[]}
    try:
        starts=[0.] if seeds is not None else [0.]+[max(0,float(m.get('second',0))-1) for m in moments[:8]]
        for start in starts:
            if len(windows)>=max_windows:break
            end=min(float(duration),start+6.)
            if end-start<.5 or any(start<x['end'] and end>x['start'] for x in windows):continue
            def frames():
                for t in np.arange(start,end,.125):
                    cap.set(cv2.CAP_PROP_POS_MSEC,float(t)*1000);ok,f=cap.read()
                    if ok and f is not None:
                        if f.shape[1]>1280:f=cv2.resize(f,(1280,round(f.shape[0]*1280/f.shape[1])))
                        yield float(t),f
            rows,n=track_frames(frames(),seeds)
            for tr in rows:tr['id']=len(tracks)+1;tr['window']=len(windows)+1;tracks.append(tr)
            windows.append({'start':round(start,3),'end':round(end,3),'frames':n,'tracklets':len(rows)})
    finally:cap.release()
    return {'status':'candidate_only','tracks':tracks,'windows':windows,'coordinate_system':'image_normalized','identity_verified':False,'camera_compensated':False,'note':'Trajectoires locales non certifiées, sans réidentification entre fenêtres. La caméra peut bouger. Aucun numéro, équipe, temps de jeu ou distance métrique déduit.'}
