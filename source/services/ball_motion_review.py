"""Assisted colour-independent ball proposals from three consecutive frames.
Two reviewed seeds constrain a short extrapolation, never a ball identity or event.
"""
from math import hypot, isfinite
import cv2
import numpy as np

VERSION='assisted-ball-motion-v1'

def propose(previous,current,following,*,frame_index,seeds):
    frames=(previous,current,following)
    if not isinstance(current,np.ndarray):raise ValueError('Image centrale invalide.')
    if not all(isinstance(f,np.ndarray) and f.dtype==np.uint8 and f.ndim==3 and f.shape[2]==3 and f.shape==current.shape for f in frames):
        raise ValueError('Trois images BGR de même format requises.')
    h,w=current.shape[:2]; scale=h/720
    if not 128<=h<=2160 or not 128<=w<=3840:raise ValueError('Dimensions invalides.')
    if type(frame_index) is not int or not isinstance(seeds,list) or len(seeds)!=2:raise ValueError('Deux repères revus requis.')
    for s in seeds:
        if not isinstance(s,dict) or s.get('reviewed') is not True or type(s.get('frame')) is not int or s['frame']<0 or not all(type(s.get(k)) in (int,float) and isfinite(s[k]) and 0<=s[k]<=1 for k in ('x','y')):raise ValueError('Repère invalide.')
    a,b=seeds; gap=b['frame']-a['frame']; horizon=frame_index-b['frame']
    if not 1<=gap<=5 or not 1<=horizon<=5:raise ValueError('Recherche limitée à cinq images après les repères.')
    vx=(b['x']-a['x'])*w/gap;vy=(b['y']-a['y'])*h/gap
    if hypot(vx,vy)>90*scale:raise ValueError('Déplacement initial hors domaine expérimental.')
    x=b['x']*w+vx*horizon;y=b['y']*h+vy*horizon;r=(16+7*horizon)*scale
    base=dict(engine=VERSION,frame_index=frame_index,seed_frames=[a['frame'],b['frame']],prediction_xy=[round(x/w,6),round(y/h,6)],radius_px=round(r,3),candidates=[],confirmed=False,identity_verified=False)
    if not 0<=x<w or not 0<=y<h:return dict(base,status='prediction_outside_frame')
    greys=[cv2.cvtColor(f,cv2.COLOR_BGR2GRAY) for f in frames];g,m,k=greys
    # Refuse large visual changes, including scene cuts and fast uncorrected pans.
    if max(float(cv2.absdiff(g,m).mean()),float(cv2.absdiff(k,m).mean()))>32:return dict(base,status='scene_motion_refused')
    delta=np.minimum(cv2.absdiff(g,m),cv2.absdiff(k,m));mask=(delta>=8).astype(np.uint8)*255
    n,_,stats,centres=cv2.connectedComponentsWithStats(mask,connectivity=8);out=[]
    for (left,top,bw,bh,area),(cx,cy) in zip(stats[1:],centres[1:]):
        dist=hypot(cx-x,cy-y)
        if dist>r or not (8*scale**2<=area<=650*scale**2 and 3*scale<=bw<=50*scale and 3*scale<=bh<=35*scale and .3<=bw/bh<=4 and area/(bw*bh)>=.23):continue
        pad=max(1,round(25*scale));roi=(slice(max(top-pad,0),min(h,top+bh+pad)),slice(max(left-pad,0),min(w,left+bw+pad)))
        strength=float(np.mean(delta[top:top+bh,left:left+bw]));noise=float(np.mean(mask[roi]>0));shape=min(bw/bh,bh/bw)*area/(bw*bh)
        score=.45*min(strength/35,1)+.3*shape+.25*(1-min(noise/.35,1))-.5*dist/r
        if score<=0:continue
        out.append(dict(x=round(float(cx/w),6),y=round(float(cy/h),6),bbox=[round(left/w,6),round(top/h,6),round((left+bw)/w,6),round((top+bh)/h,6)],ranking_score=round(float(score),6),status='motion_candidate_not_verified'))
    out.sort(key=lambda d:-d['ranking_score'])
    return dict(base,status='candidates' if out else 'no_supported_candidate',candidates=out[:8])

def scan_motion_clip(path,frame_index,seeds,*,mode="motion"):
    """Three exact source-local frames; 25 fps nominal domain only."""
    if mode not in ("motion","fusion"):raise ValueError("Mode inconnu.")
    if type(frame_index) is not int or frame_index<1:raise ValueError('Indice central invalide.')
    c=cv2.VideoCapture(str(path))
    try:
        if not c.isOpened():raise ValueError('Vidéo locale illisible.')
        fps=float(c.get(cv2.CAP_PROP_FPS))
        total=int(c.get(cv2.CAP_PROP_FRAME_COUNT))
        if not isfinite(fps) or abs(fps-25)>1e-6 or frame_index+1>=total:
            raise ValueError('Prototype limité aux vidéos de 25 i/s avec deux images adjacentes.')
        if not c.set(cv2.CAP_PROP_POS_FRAMES,frame_index-1):raise ValueError('Recherche vidéo impossible.')
        frames=[]
        for i in range(frame_index-1,frame_index+2):
            ok,f=c.read()
            if not ok or f is None or round(c.get(cv2.CAP_PROP_POS_FRAMES))!=i+1:
                raise ValueError('Index de décodage non vérifiable.')
            frames.append(f)
        if mode=="fusion":
            from services.ball_assisted_fusion import fuse
            result=fuse(*frames,frame_index=frame_index,seeds=seeds)
        else:
            result=propose(*frames,frame_index=frame_index,seeds=seeds)
        result["tracking_mode"]=mode
        result.update(source_frame_count_reported=total,source_fps_reported=fps,
                      nominal_second=frame_index/fps,pts_validated=False,
                      seed_review_verified_by_server=False)
        return result
    finally:c.release()
