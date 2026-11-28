"""CPU baseline, water-polo image candidates, not an identity/event detector."""
from collections import defaultdict
from math import hypot, isfinite
import cv2
import numpy as np

VERSION='local-colour-tracklets-v1'

def detect(frame, max_ball=12, max_heads=24):
    if not isinstance(frame,np.ndarray) or frame.ndim!=3 or frame.shape[2]!=3 or frame.dtype!=np.uint8:
        raise ValueError('Image BGR uint8 requise.')
    h,w=frame.shape[:2]
    if not 128<=h<=2160 or not 128<=w<=3840:raise ValueError('Dimensions non prises en charge.')
    hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    water=cv2.inRange(hsv,(65,30,40),(135,255,255))
    skin=cv2.bitwise_or(cv2.inRange(hsv,(0,45,65),(25,255,255)),cv2.inRange(hsv,(165,45,65),(179,255,255)))
    pink=cv2.inRange(hsv,(158,35,75),(179,255,255))
    dark=cv2.inRange(hsv,(0,0,0),(179,255,90))
    light=cv2.inRange(hsv,(0,0,130),(179,85,255))
    red=cv2.bitwise_or(cv2.inRange(hsv,(0,100,65),(9,255,255)),cv2.inRange(hsv,(170,100,65),(179,255,255)))
    scale=h/720.; result=[]
    def region_ratio(mask,x,y,r):
        x,y,r=int(x),int(y),max(3,int(r));roi=mask[max(0,y-r):min(h,y+r+1),max(0,x-r):min(w,x+r+1)]
        return float(np.mean(roi>0)) if roi.size else 0.
    for cls,mask in [('ball_candidate',pink),('cap_dark',dark),('cap_light',light),('cap_red',red)]:
        n,_,stats,centres=cv2.connectedComponentsWithStats(mask,connectivity=8)
        for i in range(1,n):
            x,y,bw,bh,a=map(int,stats[i]);cx,cy=map(float,centres[i]);ball=cls=='ball_candidate'
            if not ((5 if ball else 12)*scale**2<=a<=(600 if ball else 1250)*scale**2 and 2*scale<=bw<= (35 if ball else 52)*scale and 2*scale<=bh<=(35 if ball else 52)*scale):continue
            ratio=bw/bh;fill=a/(bw*bh)
            if not .48<=ratio<=2.1 or fill<.30:continue
            if not .025*w<cx<.98*w or not .095*h<cy<.97*h:continue
            r=max(bw,bh);wr=region_ratio(water,cx,cy,max(22*scale,r*1.6));sr=region_ratio(skin,cx,cy,max(18*scale,r*1.4))
            if wr<(.24 if ball else .27) or (not ball and sr<.045):continue
            shape=min(ratio,1/ratio)*fill
            score=.50*shape+.35*wr+.15*(min(a/(120*scale**2),1) if ball else min(sr/.18,1))
            result.append(dict(kind='ball' if ball else 'head',colour=cls,x=round(cx/w,6),y=round(cy/h,6),bbox=[round(x/w,6),round(y/h,6),round((x+bw)/w,6),round((y+bh)/h,6)],ranking_score=round(score,6),status='candidate'))
    out=[]
    for kind,limit in [('ball',max_ball),('head',max_heads)]:
        kept=[]
        for p in sorted((p for p in result if p['kind']==kind),key=lambda p:-p['ranking_score']):
            if any(hypot((p['x']-q['x'])*w,(p['y']-q['y'])*h)<(9 if kind=='ball' else 17)*scale for q in kept):continue
            kept.append(p)
            if len(kept)>=limit:break
        out.extend(kept)
    return out

class Tracker:
    """Mutual-nearest detection association. No bridging across missed samples/cuts.
    Track IDs are local anonymous hypotheses, not athlete identities.
    """
    def __init__(self,max_gap=.24,ambiguity_px=6):
        if not isfinite(max_gap) or not 0<max_gap<=1 or not isfinite(ambiguity_px) or ambiguity_px<0:raise ValueError('Paramètres invalides.')
        self.max_gap=max_gap;self.ambiguity_px=ambiguity_px;self.tracks={};self.active={};self.last=None;self.shape=None;self.next_id=1;self.resets=0
    def step(self,second,shape,detections,cut=False):
        if not isinstance(second,(int,float)) or not isfinite(second) or second<0 or (self.last is not None and second<=self.last):raise ValueError('Temps strictement croissants requis.')
        h,w=shape[:2];dt=None if self.last is None else second-self.last
        if cut or self.shape!= (h,w) or (dt is not None and dt>self.max_gap):
            self.active={};self.resets+=int(self.last is not None)
        ds=list(detections)
        for d in ds:
            if d.get('kind') not in {'ball','head'} or not all(isinstance(d.get(k),(float,int)) and isfinite(d[k]) and 0<=d[k]<=1 for k in ('x','y')):raise ValueError('Détection invalide.')
        ids=list(self.active);pairs=defaultdict(list);reverse=defaultdict(list)
        for i in ids:
            p=self.active[i]
            for j,d in enumerate(ds):
                if p['kind']!=d['kind']:continue
                if p['kind']=='head' and p['colour']!=d['colour']:continue
                dist=hypot((p['x']-d['x'])*w,(p['y']-d['y'])*h)
                gate=(14+1600*dt if d['kind']=='ball' else 12+340*dt)*h/720 if dt is not None else 0
                if dist<=gate:pairs[i].append((dist,j));reverse[j].append((dist,i))
        matched={}
        def unambiguous(vals):return len(vals)==1 or (len(vals)>1 and vals[1][0]-vals[0][0]>self.ambiguity_px*h/720)
        for i,vals in pairs.items():
            vals.sort();dist,j=vals[0];rev=sorted(reverse[j])
            if unambiguous(vals) and unambiguous(rev) and rev[0][1]==i:matched[j]=i
        active={};rows=[]
        for j,d in enumerate(ds):
            i=matched.get(j)
            if i is None:
                i=self.next_id;self.next_id+=1;self.tracks[i]=dict(id=i,kind=d['kind'],colour=d['colour'],identity_verified=False,points=[])
            p=dict(second=round(float(second),6),x=d['x'],y=d['y']);self.tracks[i]['points'].append(p);active[i]=d;rows.append(dict(d,track_id=i))
        self.active=active;self.last=second;self.shape=(h,w)
        return rows
    def summary(self):
        out=list(self.tracks.values())
        return dict(engine=VERSION,tracks=out,tracklets_total=len(out),tracklets_at_least_3=sum(len(x['points'])>=3 for x in out),resets=self.resets,coordinate_system='image_normalized',identity_verified=False,camera_compensated=False,metrics_validated=False)


def scan(frames):
    """Iterable of (source-local second, BGR image), chronological, caller-bound."""
    tr=Tracker();results=[];prev=None
    for t,f in frames:
        tiny=cv2.resize(cv2.cvtColor(f,cv2.COLOR_BGR2GRAY),(160,90))
        cut=prev is not None and float(cv2.absdiff(prev,tiny).mean())>45
        rows=tr.step(t,f.shape,detect(f),cut=cut)
        results.append(dict(second=round(float(t),6),scene_reset=bool(cut),detections=rows));prev=tiny
    return dict(tr.summary(),frames=results,note='Propositions couleur et pistes anonymes. Scores de tri non probabilistes. Aucun événement ou temps de jeu confirmé.')
