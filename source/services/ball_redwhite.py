"""Red/white ball proposals; not a certified ball or player detector."""
import cv2
import numpy as np

def redwhite_candidates(frame):
    h,w=frame.shape[:2]; hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
    red=cv2.bitwise_or(cv2.inRange(hsv,(0,65,65),(9,255,255)),cv2.inRange(hsv,(160,65,65),(179,255,255)))
    white=cv2.inRange(hsv,(0,0,145),(179,70,255)); water=cv2.inRange(hsv,(65,35,40),(135,255,255))
    contours,_=cv2.findContours(red,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE); results=[]
    for c in contours:
        a=cv2.contourArea(c); (x,y),r=cv2.minEnclosingCircle(c)
        if a<5 or r<2 or r>min(h,w)*.025 or not (.04*w<x<.96*w and .12*h<y<.94*h):continue
        R=max(4,int(r*1.6)); B=max(8,int(r*4)); ix,iy=round(x),round(y)
        y0,y1=max(0,iy-R),min(h,iy+R+1); x0,x1=max(0,ix-R),min(w,ix+R+1)
        ys,xs=np.ogrid[y0:y1,x0:x1]; disc=(xs-x)**2+(ys-y)**2<=R**2
        wr=np.count_nonzero((white[y0:y1,x0:x1]>0)&disc)/max(1,disc.sum())
        rr=np.count_nonzero((red[y0:y1,x0:x1]>0)&disc)/max(1,disc.sum())
        pool=water[max(0,iy-B):min(h,iy+B+1),max(0,ix-B):min(w,ix+B+1)]
        if .12<=wr<=.65 and .10<=rr<=.55 and np.count_nonzero(pool)/pool.size>=.40:
            results.append((float(x),float(y)))
    return results
