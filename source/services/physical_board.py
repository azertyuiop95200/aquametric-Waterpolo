"""Close-up scoreboard reading; never infer game clock or club from a physical board."""
import cv2
import numpy as np
import re

def _components(mask):
    cs,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    return sorted([(cv2.boundingRect(c),cv2.contourArea(c)) for c in cs],key=lambda v:-v[1])

def read_physical_board(frame,reader):
    h,w=frame.shape[:2]; hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    blue=cv2.inRange(hsv,(85,70,60),(120,255,220)); white=cv2.inRange(hsv,(0,0,140),(179,65,255))
    red=cv2.inRange(hsv,(0,75,120),(12,255,255))|cv2.inRange(hsv,(165,75,120),(179,255,255))
    green=cv2.inRange(hsv,(35,80,110),(90,255,255))
    whites=_components(white); candidates=[]
    for (bx,by,bw,bh),area in _components(blue)[:12]:
        if not (bw>=w*.045 and bh>=h*.035 and 1.3<bw/bh<3 and area/(bw*bh)>.68):continue
        for (wx,wy,ww,wh),wa in whites[:30]:
            dx=bx-wx
            if not (1.35<dx/bw<2.2 and abs(by-wy)<bh*.6 and .7<ww/bw<1.3 and .7<wh/bh<1.3 and wa/(ww*wh)>.7):continue
            def crop(mask,x,y,X,Y):
                return mask[max(0,round(y)):min(h,round(Y)),max(0,round(x)):min(w,round(X))]
            def read(mask,kind):
                if not mask.size:return None
                coords=cv2.findNonZero(mask)
                if coords is None:return None
                x,y,W,H=cv2.boundingRect(coords)
                if H<10:return None
                tight=mask[y:y+H,x:x+W]
                img=cv2.copyMakeBorder(255-tight,16,16,16,16,cv2.BORDER_CONSTANT,value=255)
                return str(reader(img,kind) or '').strip()
            panel=crop(hsv[:,:,2],wx-ww*.12,wy-bh*1.65,bx+bw*1.1,by+bh*2.65)
            if not panel.size or np.mean(panel<125)<.48:continue
            vals=[]
            for x,y,W,H in [(wx,wy,ww,wh),(bx,by,bw,bh)]:
                vals.append(read(crop(red,x-W*.10,y-H*1.65,x+W*1.17,y+H*.02),'score'))
            if any(v is None or not re.fullmatch(r'\d{1,2}',v) or int(v)>40 for v in vals):continue
            clock=read(crop(white,wx+ww*.72,max(wy+wh,by+bh*.75),bx+bw*.72,by+bh*2.55),'clock')
            if clock and not re.fullmatch(r'\d{1,2}:\d{2}',clock):clock=None
            if clock and int(clock.split(':')[1])>=60:clock=None
            period=read(crop(green,wx+ww*.95,min(wy,by)-bh*.7,bx, max(wy,by)+bh*.55),'period')
            candidates.append({'white_score':int(vals[0]),'blue_score':int(vals[1]),'display_clock':clock,'display_period':int(period) if period and re.fullmatch('[1-4]',period) else None})
    return candidates[0] if len(candidates)==1 else None

def consensus(rows):
    from collections import defaultdict
    groups=defaultdict(list)
    for row in rows:
        if row.get('white_score') is None or row.get('blue_score') is None:continue
        groups[(row['white_score'],row['blue_score'])].append(row)
    supported=[]
    for key,rr in groups.items():
        rr=sorted(rr,key=lambda r:r['second']); times=sorted(set(r['second'] for r in rr))
        if len(times)<2 or times[-1]-times[0]<.5:continue
        supported.append((times[-1],key,rr))
    if not supported:return None
    _,key,rr=max(supported,key=lambda x:x[0])
    timed=[(r['second'],int(r['display_clock'].split(':')[0])*60+int(r['display_clock'].split(':')[1])) for r in rr if r.get('display_clock')]
    direction='unknown'
    if len(timed)>=3 and all(0<=v-u<=b-a+1.2 for (a,u),(b,v) in zip(timed,timed[1:])) and timed[-1][1]>timed[0][1]:direction='increasing'
    elif len(timed)>=3 and all(0<=u-v<=b-a+1.2 for (a,u),(b,v) in zip(timed,timed[1:])) and timed[-1][1]<timed[0][1]:direction='decreasing'
    return {'white_score':key[0],'blue_score':key[1],'start_second':rr[0]['second'],'end_second':rr[-1]['second'],'observations':len(set(r['second'] for r in rr)),'display_clock_direction':direction,'clock_kind':'unresolved','scope':'observed_score_not_event_total','rows':rr}

def scan_tail(video_path,duration,reader):
    cap=cv2.VideoCapture(str(video_path));rows=[]
    if not cap.isOpened():cap.release();return None
    try:
        for second in sorted(set(max(0.,duration-i) for i in (12,9,6,4,3,2,1,.7))):
            cap.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,frame=cap.read()
            if not ok:continue
            r=read_physical_board(frame,reader)
            if r:rows.append(dict(r,second=round(second,3)))
    finally:cap.release()
    return consensus(rows)
