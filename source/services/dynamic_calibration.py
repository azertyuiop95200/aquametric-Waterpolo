"""Multi-reference image-to-pool calibration audit. No athlete identity inferred.
The input anchors are reviewed, not automatic. Geometry quality is not metric truth.
Global coordinates: x from left goal, y from near to far side, in metres.
"""
from math import hypot, isfinite
import cv2
import numpy as np

def transform(H, p):
    z=H@np.array([*p,1.],dtype=float)
    if not np.isfinite(z).all() or abs(z[2])<1e-10:return None
    return tuple(map(float,z[:2]/z[2]))

def fit_reference(image, world, max_fit_px=12.):
    image=np.asarray(image,dtype=float);world=np.asarray(world,dtype=float)
    if image.shape!=world.shape or image.ndim!=2 or image.shape[1]!=2 or len(image)<5 or not np.isfinite(image).all() or not np.isfinite(world).all():raise ValueError('Invalid anchors')
    H,_=cv2.findHomography(world,image,0)
    if H is None or not np.isfinite(H).all() or abs(np.linalg.det(H))<1e-10:raise ValueError('Degenerate anchors')
    pred=cv2.perspectiveTransform(world[None],H)[0]
    err=float(np.max(np.linalg.norm(pred-image,axis=1)))
    if err>max_fit_px:raise ValueError('Anchor residual too large')
    return np.linalg.inv(H),err

def choose_projection(options, tolerance_m=.75):
    if not options:return None
    for i,a in enumerate(options):
        if any(hypot(a['x_m']-b['x_m'],a['y_m']-b['y_m'])>tolerance_m for b in options[i+1:]):return None
    return min(options,key=lambda a:a['alignment_error_px'])

class MultiReference:
    def __init__(self, references, *, width_m, length_m=25., image_width=640, image_height=360):
        if not (12.5<=width_m<=20 and 15<=length_m<=30):raise ValueError('Invalid dimensions')
        self.width_m=width_m;self.length_m=length_m;self.w=image_width;self.h=image_height
        self.sift=cv2.SIFT_create(nfeatures=650);self.matcher=cv2.BFMatcher();self.refs=[]
        for r in references:
            frame=cv2.resize(r['frame'],(self.w,self.h)); mask=np.zeros((self.h,self.w),np.uint8)
            poly=np.asarray(r['decor_polygon'],float)
            if poly.ndim!=2 or poly.shape[1]!=2 or len(poly)<3 or not np.isfinite(poly).all() or (poly<0).any() or (poly>1).any():raise ValueError('Invalid decor mask')
            cv2.fillPoly(mask,[np.round(poly*[self.w,self.h]).astype(np.int32)],255)
            k,d=self.sift.detectAndCompute(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),mask)
            if d is None or len(k)<25:continue
            G,err=fit_reference(np.asarray(r['image_anchors'])*[self.w,self.h],r['world_anchors'],max_fit_px=8.)
            self.refs.append((r['id'],k,d,G,err))
        if not self.refs:raise ValueError('No usable reference')
    def align(self,frame):
        g=cv2.cvtColor(cv2.resize(frame,(self.w,self.h)),cv2.COLOR_BGR2GRAY)
        k,d=self.sift.detectAndCompute(g,None)
        if d is None:return []
        out=[]
        for rid,rk,rd,G,fit in self.refs:
            matches=self.matcher.knnMatch(rd,d,k=2)
            good=[m for pair in matches if len(pair)==2 for m,n in [pair] if m.distance<.72*n.distance]
            used=set();unique=[]
            for m in sorted(good,key=lambda m:m.distance):
                if m.trainIdx not in used:unique.append(m);used.add(m.trainIdx)
            if len(unique)<25:continue
            a=np.float32([k[m.trainIdx].pt for m in unique]);b=np.float32([rk[m.queryIdx].pt for m in unique]);test=np.arange(len(a))%5==0
            H,ins=cv2.findHomography(a[~test],b[~test],cv2.RANSAC,1.5)
            if H is None or ins is None or ins.sum()<16 or ins.mean()<.6:continue
            err=np.linalg.norm(cv2.perspectiveTransform(a[test][None],H)[0]-b[test],axis=1)
            if not np.isfinite(err).all() or np.median(err)>1.5 or np.mean(err<2.5)<.7:continue
            aa=a[~test][ins.ravel().astype(bool)]
            if np.ptp(aa[:,0])<self.w*.2 or np.ptp(aa[:,1])<self.h*.04:continue
            corners=np.float32([[[0,0],[self.w,0],[self.w,self.h],[0,self.h]]]); warped=cv2.perspectiveTransform(corners,H)[0]
            if not np.isfinite(warped).all() or not cv2.isContourConvex(warped.astype(np.float32)) or not .3<abs(cv2.contourArea(warped))/(self.w*self.h)<3.:continue
            out.append({'reference':rid,'matrix':G@H,'alignment_error_px':float(np.median(err)),'anchor_fit_px':fit,'inliers':int(ins.sum())})
        return out
    def project(self, aligned, x, y, tolerance_m=.75):
        if not (isfinite(x) and isfinite(y) and 0<=x<=1 and 0<=y<=1):return None
        options=[]
        for a in aligned:
            p=transform(a['matrix'],(x*self.w,y*self.h))
            if p is None:continue
            X,Y=p
            options.append({'x_m':X,'y_m':Y,'reference':a['reference'],'alignment_error_px':a['alignment_error_px']})
        p=choose_projection(options,tolerance_m)
        if p is None or not 0<=p['x_m']<=self.length_m or not abs(p['y_m'])<=self.width_m/2:return None
        return p|{'support':len(options),'scope':'candidate_projection_not_verified_position'}
