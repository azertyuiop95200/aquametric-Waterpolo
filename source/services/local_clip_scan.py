"""Bounded local clip scanner, source frame indices, not PTS certification."""
from math import isfinite
import cv2
from services.local_object_tracking import scan

def scan_clip(path,start_frame=0,frame_count=75):
    if type(start_frame) is not int or start_frame<0 or type(frame_count) is not int or not 1<=frame_count<=75:
        raise ValueError("Fenêtre de 1 à 75 images requise.")
    c=cv2.VideoCapture(str(path))
    try:
        if not c.isOpened():raise ValueError("Vidéo locale illisible.")
        fps=float(c.get(cv2.CAP_PROP_FPS))
        total=int(c.get(cv2.CAP_PROP_FRAME_COUNT))
        w=int(c.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not isfinite(fps) or not 10<=fps<=60 or not 128<=w<=3840 or not 128<=h<=2160 or not 0<=start_frame<total:
            raise ValueError("Source hors limites ou indice invalide.")
        end=min(total,start_frame+frame_count)
        if not c.set(cv2.CAP_PROP_POS_FRAMES,start_frame):
            raise ValueError("Recherche vidéo impossible.")
        stride=max(1,round(fps/12.5))
        def frames():
            for i in range(start_frame,end):
                if (i-start_frame)%stride:
                    if not c.grab():raise ValueError("Décodage interrompu.")
                    continue
                ok,f=c.read()
                if not ok or f is None or round(c.get(cv2.CAP_PROP_POS_FRAMES))!=i+1:
                    raise ValueError("Index d’image non vérifiable.")
                yield i/fps,f
        result=scan(frames())
        for row,i in zip(result["frames"],range(start_frame,end,stride)):
            row["source_frame_index"]=i
        result.update(source_fps_reported=fps,source_frame_count_reported=total,first_frame=start_frame,
                      end_frame_exclusive=end,sample_stride=stride,time_basis="nominal_frame_index_divided_by_reported_fps",
                      pts_validated=False)
        return result
    finally:c.release()
