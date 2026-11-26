"""Goal-relative metric geometry: reviewed anchors and partial tracks."""
from math import hypot,isfinite
import cv2
import numpy as np

def calibrate(anchors,width=20.,length=25.):
    width=float(width); length=float(length)
    if not 12.5<=width<=20 or not 15<=length<=30: raise ValueError("Dimensions hors profil senior.")
    img=np.asarray(anchors,dtype=float)
    if img.shape!=(5,2) or not np.isfinite(img).all() or (img<0).any() or (img>1).any():raise ValueError("Cinq repères image normalisés requis.")
    world=np.array([[0,-1.5],[0,1.5],[0,width/2],[2,width/2],[6,width/2]],float)
    H,_=cv2.findHomography(world,img,0)
    if H is None or not np.isfinite(H).all():raise ValueError("Repères dégénérés.")
    error=float(np.max(np.linalg.norm(cv2.perspectiveTransform(world[None],H)[0]-img,axis=1)))
    if error>.012 or abs(np.linalg.det(H))<1e-10:raise ValueError("Repères incohérents.")
    return {"H":np.linalg.inv(H),"width":width,"length":length,"fit_error_normalized":error}

def project(cal,x,y):
    p=cal["H"]@np.array([x,y,1.])
    if not np.isfinite(p).all() or abs(p[2])<1e-8:return None
    a,b=p[:2]/p[2]
    if not -.3<=a<=cal["length"]+.3 or abs(b)>cal["width"]/2+.3:return None
    return float(a),float(b)

class CameraAligner:
    def __init__(self,reference,polygon):
        self.h,self.w=reference.shape[:2];self.mask=np.zeros((self.h,self.w),np.uint8)
        xy=np.array(polygon,float)
        if xy.ndim!=2 or xy.shape[1]!=2 or not 3<=len(xy)<=16 or not np.isfinite(xy).all() or (xy<0).any() or (xy>1).any():raise ValueError("Masque de décor invalide.")
        cv2.fillPoly(self.mask,[np.round(xy*[self.w,self.h]).astype(np.int32)],255)
        self.sift=cv2.SIFT_create(nfeatures=1000);self.k,self.d=self.features(reference)
        if self.d is None or len(self.k)<25:raise ValueError("Décor de référence insuffisant.")
    def features(self,frame):
        return self.sift.detectAndCompute(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),self.mask)
    def align(self,frame):
        k,d=self.features(frame)
        if d is None:return None
        matches=cv2.BFMatcher().knnMatch(d,self.d,k=2);good=[m for pair in matches if len(pair)==2 for m,n in [pair] if m.distance<.72*n.distance]
        if len(good)<25:return None
        a=np.float32([k[m.queryIdx].pt for m in good]);b=np.float32([self.k[m.trainIdx].pt for m in good])
        test=np.arange(len(a))%5==0;H,inliers=cv2.findHomography(a[~test],b[~test],cv2.RANSAC,2.)
        if H is None or inliers is None or int(inliers.sum())<18 or float(inliers.mean())<.55:return None
        pred=cv2.perspectiveTransform(a[test][None],H)[0];err=np.linalg.norm(pred-b[test],axis=1)
        if np.median(err)>2.5 or np.mean(err<4)<.6:return None
        aa=a[~test][inliers.ravel().astype(bool)]
        if np.ptp(aa[:,0])<self.w*.20 or np.ptp(aa[:,1])<self.h*.07:return None
        corners=np.float32([[[0,0],[self.w,0],[self.w,self.h],[0,self.h]]]);warped=cv2.perspectiveTransform(corners,H)[0]
        if not np.isfinite(warped).all() or not cv2.isContourConvex(warped.astype(np.float32)) or not .5<abs(cv2.contourArea(warped))/(self.w*self.h)<2.:return None
        return H,float(np.median(err)),int(inliers.sum())
    def point(self,H,x,y):
        z=cv2.perspectiveTransform(np.array([[[x*self.w,y*self.h]]],float),H)[0,0]
        return float(z[0]/self.w),float(z[1]/self.h)

def measure(points, *, max_gap=.26, max_speed=3.5):
    """Partial planar track; thresholds are experimental, not rules."""
    if not all(isfinite(v) and v>0 for v in (max_gap,max_speed)):
        raise ValueError("Invalid experimental thresholds")
    segments=[]; current=[]; rejected=0; invalid=0
    last_seen=-float("inf"); nonmonotonic=0
    for p in points:
        if p is not None:
            try:
                p=dict(p); t,x,y=(float(p[k]) for k in ("second","x_m","y_m"))
                if not all(isfinite(v) for v in (t,x,y)) or t<0:raise ValueError()
                p.update(second=t,x_m=x,y_m=y,raw_x_m=x,raw_y_m=y)
            except (ValueError,TypeError,KeyError):
                invalid+=1;p=None
        if p is not None:
            if p["second"]<=last_seen:
                nonmonotonic+=1;p=None
            else:last_seen=p["second"]
        if p is None:
            if current:segments.append(current);current=[]
            continue
        if current:
            dt=p["second"]-current[-1]["second"];delta=hypot(p["x_m"]-current[-1]["x_m"],p["y_m"]-current[-1]["y_m"])
            if not 0<dt<=max_gap or delta/dt>max_speed:
                segments.append(current);current=[];rejected+=1
        current.append(p)
    if current:segments.append(current)
    short=sum(len(s) for s in segments if len(s)<5)
    segments=[s for s in segments if len(s)>=5]
    fallback=0;raw_distance=0.;distance=0.;seconds=0.
    for s in segments:
        xy=np.array([[p["x_m"],p["y_m"]] for p in s]);sm=xy.copy()
        for i in range(2,len(s)-2):sm[i]=np.median(xy[i-2:i+3],axis=0)
        dt=np.diff([p["second"] for p in s])
        raw_distance+=float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum())
        if np.any(np.linalg.norm(np.diff(sm,axis=0),axis=1)>max_speed*dt+1e-9):
            sm=xy;fallback+=1
        for p,v in zip(s,sm):p["x_m"],p["y_m"]=map(float,v)
        distance+=float(np.linalg.norm(np.diff(sm,axis=0),axis=1).sum())
        seconds+=s[-1]["second"]-s[0]["second"]
    return dict(segments=segments,observed_seconds=round(seconds,3),distance_m=round(distance,2) if seconds>=.5 else None,raw_distance_m=round(raw_distance,2) if seconds>=.5 else None,rejected_jumps=rejected,invalid_points=invalid,nonmonotonic_points=nonmonotonic,short_segment_points=short,smoothing_fallback_segments=fallback)

def build_map(path,tracking,anchors,polygon,width=20.,length=25.,reference_second=0.,shots=()):
    cal=calibrate(anchors,width,length);cap=cv2.VideoCapture(str(path));cache={};quality=[]
    def frame(t):
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,f=cap.read()
        return cv2.resize(f,(960,540)) if ok else None
    try:
        ref=frame(reference_second)
        if ref is None:raise ValueError("Image de référence indisponible.")
        aligner=CameraAligner(ref,polygon)
        def project_at(t,x,y):
            if not isfinite(t) or t<0 or not 0<=x<=1 or not 0<=y<=1:return None
            if t not in cache:
                f=frame(t);a=aligner.align(f) if f is not None else None;cache[t]=a
                if a is not None:quality.append(a[1])
            a=cache[t]
            if a is None:return None
            return project(cal,*aligner.point(a[0],x,y))
        tracks=[]
        for tr in tracking.get("tracks",[]):
            pts=[]
            for p in tr.get("points",[]):
                t=float(p["second"]);xy=project_at(t,float(p["x"]),float(p["y"]))
                pts.append({"second":t,"x_m":xy[0],"y_m":xy[1]} if xy is not None else None)
            tracks.append({"id":tr["id"],"colour":tr.get("colour","unknown"),"cap_number":None,"team":None,**measure(pts)})
        mapped=[]
        for s in shots:
            t=float(s["second"]);xy=project_at(t,float(s["x"]),float(s["y"]))
            if xy is None:continue
            x,y=xy;mapped.append({"second":t,"x_m":round(x,2),"y_m":round(y,2),"range_m":round(hypot(x,y),2),"outcome":s.get("outcome","unknown") if s.get("outcome") in ("unknown","goal","save","off_target","blocked","post") else "unknown","provenance":"manual_review_candidate"})
        return {"status":"estimated","width_m":cal["width"],"length_m":cal["length"],"goal_relative":True,"reference_second":reference_second,"tracks":tracks,"shots":mapped,"aligned_frames":len(quality),"requested_frames":len(cache),"rejected_alignment_frames":len(cache)-len(quality),"source_track_count":len(tracking.get("tracks",[])),"median_alignment_error_px":round(float(np.median(quality)),2) if quality else None,"fit_error_normalized":cal["fit_error_normalized"],"note":"Projection estimative sur le plan de l’eau; largeur saisie, repères manuels et tête au-dessus de l’eau. Distances partielles de pistes, pas des distances exactes par joueuse."}
    finally:cap.release()
