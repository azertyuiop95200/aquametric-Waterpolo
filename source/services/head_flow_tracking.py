"""Experimental head-only tracking with forward/backward flow and appearance checks.
No roster identity, no camera compensation, no metric or event validation.
"""
from collections import defaultdict
from math import hypot, isfinite
import cv2
import numpy as np
from services.local_object_tracking import detect

VERSION='head-flow-tracklets-v2'

def _patch(gray, x, y, r):
    if not r<=x<gray.shape[1]-r or not r<=y<gray.shape[0]-r:return None
    return cv2.getRectSubPix(gray,(2*r+1,2*r+1),(float(x),float(y))).astype(np.float32)

def _flow(prev,gray,points):
    """Flow is a proposal only. Require texture, round trip and patch similarity."""
    if not points:return []
    h,w=gray.shape;scale=h/720; r=max(4,round(7*scale))
    old=np.asarray(points,np.float32).reshape(-1,1,2)
    opts=dict(winSize=(21,21),maxLevel=2,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,25,.03))
    new,st,_=cv2.calcOpticalFlowPyrLK(prev,gray,old,None,**opts)
    if new is None or st is None:return [None]*len(points)
    back,st2,_=cv2.calcOpticalFlowPyrLK(gray,prev,new,None,**opts)
    if back is None or st2 is None:return [None]*len(points)
    out=[]
    for i,((x,y),(a,b)) in enumerate(zip(old[:,0],new[:,0])):
        if not st[i,0] or not st2[i,0] or not np.isfinite([a,b,*back[i,0]]).all() or np.linalg.norm(back[i,0]-old[i,0])>max(.7,1.3*scale) or hypot(a-x,b-y)>45*scale:
            out.append(None);continue
        p,q=_patch(prev,x,y,r),_patch(gray,a,b,r)
        if p is None or q is None or p.std()<7 or q.std()<7:
            out.append(None);continue
        p-=p.mean();q-=q.mean(); corr=float(np.sum(p*q)/(np.linalg.norm(p)*np.linalg.norm(q)))
        out.append((float(a),float(b)) if corr>=.70 else None)
    return out

def scan_head_flow(frames, max_flow_only=2, *, min_detector_support=1):
    """Redetection at each sample; at most two flow-supported samples without detection.
    Break ambiguous links rather than guess identity. Flow-supported points are not detections.
    """
    if type(max_flow_only) is not int or not 0<=max_flow_only<=2:raise ValueError('Limite de prolongation invalide.')
    if type(min_detector_support) is not int or not 1<=min_detector_support<=4:raise ValueError('Support indépendant invalide.')
    active={};tracks={};results=[];prev=None;last=None;resets=0;next_id=1;withheld=0
    for t,f in frames:
        if type(t) not in (int,float) or not isfinite(t) or t<0 or last is not None and t<=last:raise ValueError('Temps strictement croissants requis.')
        ds=[d for d in detect(f) if d['kind']=='head'];gray=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY);h,w=gray.shape;scale=h/720
        reset=prev is not None and (prev.shape!=gray.shape or t-last>.12 or float(cv2.absdiff(cv2.resize(prev,(160,90)),cv2.resize(gray,(160,90))).mean())>32)
        if reset:active={};resets+=1
        ids=list(active);pred=_flow(prev,gray,[(active[i]['x']*w,active[i]['y']*h) for i in ids]) if ids else []
        # If flow endpoints collide, neither can preserve identity.
        ambiguous={i for i,p in zip(ids,pred) if p is not None and any(q is not None and j!=i and hypot(p[0]-q[0],p[1]-q[1])<10*scale for j,q in zip(ids,pred))}
        links=defaultdict(list);rev=defaultdict(list)
        for i,p in zip(ids,pred):
            if i in ambiguous:continue
            prior=active[i]
            px,py=p if p is not None else (prior['x']*w,prior['y']*h)
            gate=(12+340*(t-last))*scale
            for j,d in enumerate(ds):
                if d['colour']!=active[i]['colour']:continue
                dist=hypot(d['x']*w-px,d['y']*h-py)
                if dist<=gate:links[i].append((dist,j));rev[j].append((dist,i))
        matched={}
        def unique(rows):return len(rows)==1 or len(rows)>1 and rows[1][0]-rows[0][0]>6*scale
        for i,ls in links.items():
            ls.sort();_,j=ls[0];rs=sorted(rev[j])
            if unique(ls) and unique(rs) and rs[0][1]==i:matched[j]=i
        new={};rows=[]
        def record(i,d,source,run):
            p=dict(second=round(float(t),6),x=d['x'],y=d['y'],point_source=source)
            prior=active.get(i,{})
            support=(prior.get('detector_support',0)+1 if prior.get('flow_run')==0 else 1) if source=='detector' else prior['detector_support']
            tracks[i]['points'].append(p);new[i]=dict(d,flow_run=run,detector_support=support)
            rows.append(dict(d,track_id=i,point_source=source,detector_support=support,identity_verified=False))
        for j,d in enumerate(ds):
            i=matched.get(j)
            if i is None:
                i=next_id;next_id+=1;tracks[i]=dict(id=i,kind='head',colour=d['colour'],identity_verified=False,points=[])
            record(i,d,'detector',0)
        for i,p in zip(ids,pred):
            if i in new or p is None or i in ambiguous or i in links or active[i]['flow_run']>=max_flow_only:continue
            # Do not continue through any competing detection, regardless of colour.
            if any(hypot(p[0]-d['x']*w,p[1]-d['y']*h)<(12+340*(t-last))*scale for d in ds):continue
            if active[i]['detector_support']<min_detector_support:
                withheld+=1;continue
            d=dict(kind='head',colour=active[i]['colour'],x=round(p[0]/w,6),y=round(p[1]/h,6),bbox=None,ranking_score=None,status='flow_candidate_not_detection')
            record(i,d,'optical_flow',active[i]['flow_run']+1)
        results.append(dict(second=round(float(t),6),scene_reset=bool(reset),detections=rows));active=new;prev=gray;last=t
    ts=list(tracks.values())
    return dict(engine=VERSION if min_detector_support==1 else 'head-flow-supported-v3',min_detector_support=min_detector_support,flow_support_withheld=withheld,tracks=ts,frames=results,tracklets_total=len(ts),tracklets_at_least_3=sum(len(x['points'])>=3 for x in ts),flow_only_points=sum(p['point_source']=='optical_flow' for tr in ts for p in tr['points']),resets=resets,coordinate_system='image_normalized',identity_verified=False,camera_compensated=False,metrics_validated=False,note='Pistes tête expérimentales. Les points de flux ne sont pas des détections indépendantes. Aucune identité ni mesure métrique certifiée.')


def scan_head_flow_supported(frames):
    """Experimental stricter flow policy; independent detections are never removed."""
    return scan_head_flow(frames,min_detector_support=2)


def audit_flow_support(frames, min_detector_support=2):
    """Counterfactual audit of historical points, not re-tracking or accuracy.
    Once a flow-only point is withheld, its chain cannot seed a later flow point.
    A later independent observation can seed a fresh chain. Raw observations stay intact.
    """
    if type(min_detector_support) is not int or not 1<=min_detector_support<=4:
        raise ValueError("Invalid independent support")
    active={};last=None;counts=defaultdict(int);by_colour=defaultdict(lambda:defaultdict(int))
    for frame in frames:
        second=frame["second"]
        if type(second) not in (int,float) or not isfinite(second) or second<0 or (last is not None and second<=last):
            raise ValueError("Invalid frame chronology")
        if frame.get("scene_reset") or (last is not None and second-last>.120001):active={}
        current={};seen=set()
        for d in frame["detections"]:
            if d.get("kind")!="head":continue
            i=d["track_id"]
            if type(i) is not int or i<1 or i in seen:raise ValueError("Duplicate or invalid track id")
            seen.add(i)
            colour=d["colour"]
            if colour not in ("cap_dark","cap_light","cap_red"):raise ValueError("Invalid head colour")
            prior=active.get(i)
            if prior and prior[2]!=colour:prior=None
            source=d.get("point_source")
            if source=="detector":
                support=prior[0]+1 if prior and prior[1]==0 else 1
                current[i]=(support,0,colour)
                key="detector_points"
            elif source=="optical_flow":
                if prior and prior[0]>=min_detector_support and prior[1]<2:
                    current[i]=(prior[0],prior[1]+1,colour);key="flow_retained"
                else:key="flow_withheld"
            else:raise ValueError("Unknown point provenance")
            counts[key]+=1;by_colour[colour][key]+=1
        active=current;last=second
    keys=("detector_points","flow_retained","flow_withheld")
    return dict(policy="consecutive-independent-support-v1",min_detector_support=min_detector_support,
                **{k:counts[k] for k in keys},
                by_colour={c:{k:v[k] for k in keys} for c,v in sorted(by_colour.items())},
                statistical_use_allowed=False,precision=None,recall=None,
                note="Historical flow point audit only; association after withholding can differ in a new video scan.")
