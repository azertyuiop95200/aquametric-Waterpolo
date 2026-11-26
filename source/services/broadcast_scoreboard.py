"""Guarded FFN-style scoreboard: separate field OCR, never flattened-number guesses."""
import re
import cv2
import numpy as np

BOXES={'home':(225,25,270,74),'away':(425,25,470,74),'clock':(300,16,402,57),'period':(288,57,322,83),'shot':(340,55,392,83)}

def read_broadcast_scoreboard(frame, read_text):
    """None = layout not recognized; {} = recognized but unreadable; never guess."""
    h,w=frame.shape[:2]
    if not 1.70 <= w/h <= 1.85: return None
    panel=frame[round(14*h/1078):round(82*h/1078),round(110*w/1918):round(610*w/1918)]
    if panel.size==0 or np.mean(np.max(panel,axis=2)<65)<.55: return None
    def crop(key):
        x1,y1,x2,y2=BOXES[key]
        return frame[round(y1*h/1078):round(y2*h/1078),round(x1*w/1918):round(x2*w/1918)]
    for key,lo,hi in [('period',(35,65,70),(90,255,255)),('shot',(15,90,90),(40,255,255))]:
        hsv=cv2.cvtColor(crop(key),cv2.COLOR_BGR2HSV)
        if np.count_nonzero(cv2.inRange(hsv,lo,hi))/hsv.shape[0]/hsv.shape[1]<.025: return None
    vals={}; confs=[]
    for key in BOXES:
        img=cv2.cvtColor(crop(key),cv2.COLOR_BGR2GRAY)
        img=cv2.resize(img,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC)
        _,img=cv2.threshold(img,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        img=cv2.copyMakeBorder(255-img,15,15,15,15,cv2.BORDER_CONSTANT,value=255)
        text,conf=read_text(img,key)
        vals[key]=str(text).strip(); confs.append(float(conf))
    if not all(re.fullmatch(r'\d{1,2}',vals[k]) for k in ('home','away','period','shot')): return {}
    if not re.fullmatch(r'\d{1,2}:\d{2}',vals['clock']): return {}
    home,away,period,shot=(int(vals[k]) for k in ('home','away','period','shot'))
    mm,ss=map(int,vals['clock'].split(':'))
    if not (0<=home<=40 and 0<=away<=40 and 1<=period<=4 and 0<=shot<=30 and 0<=ss<60 and 0<=mm*60+ss<=480): return {}
    return {'home_score':home,'away_score':away,'period':period,'clock_seconds':mm*60+ss,'shot_clock_seconds':shot,'ocr_confidence':min(confs),'raw_text':f'{home} - {away} Q{period} {vals["clock"]} possession={shot}'}

def clock_changes(rows):
    """Observed clock transitions only; never infer a referee's reason from a reset."""
    changes=[]
    rows=sorted([r for r in rows if r.get('shot_clock_seconds') is not None and r.get('clock_seconds') is not None],key=lambda r:r['second'])
    for a,b in zip(rows,rows[1:]):
        if a.get('period')!=b.get('period') or any(r.get(k) for r in (a,b) for k in ('is_replay','is_break','is_final')):continue
        if b['shot_clock_seconds']-a['shot_clock_seconds']>=5 and b['shot_clock_seconds'] in (18,20,28,30):
            changes.append({'start_second':a['second'],'end_second':b['second'],'before':a['shot_clock_seconds'],'after':b['shot_clock_seconds'],'game_clock_seconds':b['clock_seconds'],'reason':'unknown'})
    return changes
