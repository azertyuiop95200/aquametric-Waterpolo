"""Sequential experimental vision baseline. Proposals are not verified sporting events."""
import argparse, gzip, json, math, time
from pathlib import Path
from collections import Counter
import cv2
import numpy as np

def proposals(frame):
    h,w=frame.shape[:2]; hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    water=cv2.inRange(hsv,(65,35,40),(135,255,255)); skin=cv2.bitwise_or(cv2.inRange(hsv,(0,45,65),(25,255,255)),cv2.inRange(hsv,(165,45,65),(179,255,255)))
    red=cv2.bitwise_or(cv2.inRange(hsv,(0,80,90),(9,255,255)),cv2.inRange(hsv,(165,80,90),(179,255,255)))
    white=cv2.inRange(hsv,(0,0,150),(179,70,255)); dark=cv2.inRange(hsv,(0,0,0),(179,255,85)); yellow=cv2.inRange(hsv,(15,115,135),(38,255,255))
    caps=[]; balls=[]
    for colour,mask in [('dark',dark),('light',white),('red',red),('yellow',yellow)]:
        for c in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
            a=cv2.contourArea(c);(x,y),r=cv2.minEnclosingCircle(c)
            if a<4 or not 1.5<=r<=h*.035 or a/(math.pi*r*r)<.30 or not (.04*w<x<.96*w and .12*h<y<.94*h):continue
            ix,iy=round(x),round(y);d=max(7,int(r*3));roi=(slice(max(0,iy-d),min(h,iy+d+1)),slice(max(0,ix-d),min(w,ix+d+1)))
            if np.mean(water[roi]>0)<.4:continue
            if colour in ('red','yellow') and r<=h*.022:
                if colour=='yellow' or .12<=np.mean(white[roi]>0)<=.65:balls.append([round(x/w,5),round(y/h,5),colour])
            if colour!='yellow' and np.mean(skin[roi]>0)>=.055:caps.append((x,y,colour,a/(math.pi*r*r)))
    kept=[]
    for p in sorted(caps,key=lambda p:-p[3]):
        if not any(math.hypot(p[0]-q[0],p[1]-q[1])<7 for q in kept):kept.append(p)
    return kept[:24],balls[:30]

class Tracker:
    def __init__(self,every=5):self.every=every;self.active={};self.prev=None;self.next_id=1;self.done=[]
    def close(self,k):
        p=self.active.pop(k);self.done.append({a:p[a] for a in ('id','start','end','count','colour','confirmations')})
    def step(self,frame,i):
        g=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY);h,w=g.shape
        cut=self.prev is not None and (self.prev.shape!=g.shape or np.mean(cv2.absdiff(self.prev,g))>42)
        if cut:
            for k in list(self.active):self.close(k)
        if self.prev is not None and self.active:
            ids=list(self.active);old=np.float32([self.active[k]['xy'] for k in ids]).reshape(-1,1,2)
            args=dict(winSize=(15,15),maxLevel=2,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,12,.03))
            new,st,_=cv2.calcOpticalFlowPyrLK(self.prev,g,old,None,**args)
            back,st2,_=cv2.calcOpticalFlowPyrLK(g,self.prev,new,None,**args) if new is not None else (None,None,None)
            for j,k in enumerate(ids):
                if back is None or not st[j,0] or not st2[j,0]:self.close(k);continue
                x,y=map(float,new[j,0]);err=float(np.linalg.norm(back[j,0]-old[j,0]));delta=float(np.linalg.norm(new[j,0]-old[j,0]))
                if err>1.1 or delta>20 or not (0<=x<w and 0<=y<h):self.close(k);continue
                self.active[k]['xy']=(x,y)
            collide=set();ids=list(self.active)
            for j,k in enumerate(ids):
                x,y=self.active[k]['xy']
                for l in ids[j+1:]:
                    X,Y=self.active[l]['xy']
                    if math.hypot(x-X,y-Y)<5:collide.update((k,l))
            for k in collide:self.close(k)
        caps,balls=proposals(frame);detect=cut or i%self.every==0 or self.prev is None
        if detect:
            used=set()
            for k in list(self.active):
                p=self.active[k];x,y=p['xy'];near=[j for j,(a,b,c,_) in enumerate(caps) if c==p['colour'] and math.hypot(x-a,y-b)<=9]
                if len(near)==1 and near[0] not in used:
                    j=near[0];used.add(j);p['xy']=caps[j][:2];p['last_det']=i;p['confirmations']+=1
                elif i-p['last_det']>=self.every*3:self.close(k)
            for j,(x,y,c,_) in enumerate(caps):
                if j in used or any(math.hypot(x-p['xy'][0],y-p['xy'][1])<10 for p in self.active.values()):continue
                k=self.next_id;self.next_id+=1;self.active[k]={'id':k,'xy':(x,y),'colour':c,'start':i,'end':i,'count':0,'last_det':i,'confirmations':1}
        rows=[]
        for p in self.active.values():
            p['count']+=1;p['end']=i;x,y=p['xy'];rows.append([p['id'],round(x/w,5),round(y/h,5),p['colour']])
        self.prev=g;return rows,balls,detect,cut
    def finish(self):
        for k in list(self.active):self.close(k)
        return self.done

def scan(path,output,summary,width=480,every=5,progress=None):
    cv2.setNumThreads(2);cap=cv2.VideoCapture(str(path));fps=cap.get(cv2.CAP_PROP_FPS);expected=round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not cap.isOpened() or not math.isfinite(fps) or fps<=0:cap.release();raise ValueError('Vidéo non lisible')
    tracker=Tracker(every);n=0;bins={};tot=Counter();start=time.monotonic()
    try:
        with gzip.open(output,'wt',encoding='utf8',compresslevel=3) as f:
            while True:
                ok,frame=cap.read()
                if not ok:break
                h,w=frame.shape[:2];frame=cv2.resize(frame,(width,round(h*width/w)),interpolation=cv2.INTER_AREA) if w!=width else frame
                tracks,balls,detect,cut=tracker.step(frame,n)
                f.write(json.dumps({'frame':n,'second':round(n/fps,4),'tracks':tracks,'ball_candidates':balls,'cap_detection':bool(detect),'cut':bool(cut)},separators=(',',':'))+'\n')
                b=bins.setdefault(int(n/fps//10),Counter());b['frames']+=1
                for k,v in [('track_frames',bool(tracks)),('ball_candidate_frames',bool(balls)),('single_ball_candidate_frames',len(balls)==1),('cap_detection_frames',detect),('cuts',cut)]:b[k]+=int(v);tot[k]+=int(v)
                n+=1
                if progress and n%250==0:progress(n,expected)
    finally:cap.release()
    tracks=tracker.finish();lengths=[p['count']/fps for p in tracks];r={'source':Path(path).name,'fps_nominal':fps,'expected_frames':expected,'processed_frames':n,'frame_coverage_pct':round(100*n/expected,4) if expected else None,'status':'complete_decode' if expected and n==expected else 'coverage_unverified_or_incomplete','duration_s':round(n/fps,3),'analysis_width_px':width,'cap_detection_every_frames':every,'runtime_s':round(time.monotonic()-start,2),'counts':dict(tot),'tracklets':len(tracks),'tracklets_ge_1s':sum(x>=1 for x in lengths),'tracklets_ge_5s':sum(x>=5 for x in lengths),'longest_tracklet_s':round(max(lengths,default=0),2),'tracklet_records':tracks,'bins':[{'start_s':k*10,**v} for k,v in sorted(bins.items())],'limitations':['Couleurs et flux optique : candidats non validés, pas de modèle entraîné.','Pas de réidentification entre ruptures ni de numéro/équipe certifié.','Coordonnées image non calibrées : aucune distance en mètres, passe, tir, faute ou possession n’est inféré.','Temps nominal frame/fps pour vidéo à cadence constante ; pas de validation VFR.']}
    Path(summary).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('--out',required=True);p.add_argument('--summary',required=True);p.add_argument('--width',type=int,default=480);p.add_argument('--every',type=int,default=5);a=p.parse_args();r=scan(a.video,a.out,a.summary,a.width,a.every,lambda n,e:print(f'{n}/{e}',flush=True));print({k:v for k,v in r.items() if k not in ('bins','tracklet_records')})
