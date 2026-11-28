"""Bounded local clip scanner, source frame indices, not PTS certification."""
from math import isfinite
from pathlib import Path
import hashlib
import cv2
from services.local_object_tracking import scan
from services.head_flow_tracking import scan_head_flow

MODES={'baseline':scan,'head_flow':scan_head_flow}

def scan_clip(path,start_frame=0,frame_count=75,*,tracking_mode='baseline'):
    if not isinstance(tracking_mode,str) or tracking_mode not in MODES:
        raise ValueError('Mode de suivi inconnu.')
    if type(start_frame) is not int or start_frame<0 or type(frame_count) is not int or not 1<=frame_count<=75:
        raise ValueError("Fenêtre de 1 à 75 images requise.")
    path=Path(path)
    stat=path.stat()
    if stat.st_size>1200*1024*1024:raise ValueError('Fichier trop volumineux pour ce scan local.')
    with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
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
        result=MODES[tracking_mode](frames())
        indices=list(range(start_frame,end,stride))
        if len(result['frames'])!=len(indices):raise ValueError('Nombre d’images traitées incohérent.')
        for row,i in zip(result["frames"],indices):
            if abs(row['second']-i/fps)>1e-5:raise ValueError('Temps d’image incohérent.')
            row["source_frame_index"]=i
        # All tracks remain experimental: this endpoint must never assert metric or roster validity.
        result.update(source_fps_reported=fps,source_frame_count_reported=total,first_frame=start_frame,
                      end_frame_exclusive=end,sample_stride=stride,time_basis="nominal_frame_index_divided_by_reported_fps",
                      pts_validated=False,tracking_mode=tracking_mode,object_scope='heads_only' if tracking_mode=='head_flow' else 'heads_and_ball_candidates',
                      statistical_use_allowed=False,identity_verified=False,metrics_validated=False)
        end_stat=path.stat()
        if (stat.st_size,stat.st_mtime_ns)!=(end_stat.st_size,end_stat.st_mtime_ns):raise ValueError('Source modifiée pendant le scan.')
        result.update(source_sha256_at_creation=sha,source_file_size=stat.st_size,source_file_mtime_ns=stat.st_mtime_ns)
        return result
    finally:c.release()
