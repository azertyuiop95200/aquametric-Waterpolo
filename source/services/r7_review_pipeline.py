"""R7 bounded local review; never a player identity or sports statistic."""
import hashlib
import json
from pathlib import Path
import cv2
from services.local_object_tracking import detect
from services.learned_head import detect_heads
from services.temporal_review import prioritize
from services.candidate_review import make_packet

def file_hash(path):
    with open(path,'rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def packet_from_video(path, index, weights_path, *, budget=3):
    if type(index) is not int or index<1:raise ValueError("Indice intérieur de vidéo requis.")
    if type(budget) is not int or not 1<=budget<=6:raise ValueError("Budget de 1 à 6 requis.")
    model_path=Path(weights_path)
    if not model_path.is_file() or model_path.stat().st_size>100000:
        raise ValueError("Modèle privé R7 non configuré ou invalide.")
    model=json.loads(model_path.read_text())
    stat=path.stat();sha=file_hash(path)
    c=cv2.VideoCapture(str(path))
    try:
        if not c.isOpened() or index+1>=int(c.get(cv2.CAP_PROP_FRAME_COUNT)):raise ValueError("Fenêtre vidéo indisponible.")
        if not c.set(cv2.CAP_PROP_POS_FRAMES,index-1):raise ValueError("Recherche vidéo impossible.")
        frames=[]
        for i in range(index-1,index+2):
            ok,f=c.read()
            if not ok or f is None or round(c.get(cv2.CAP_PROP_POS_FRAMES))!=i+1:raise ValueError("Image non vérifiable.")
            frames.append(f)
    finally:c.release()
    end=path.stat()
    if (stat.st_size,stat.st_mtime_ns)!=(end.st_size,end.st_mtime_ns):raise ValueError("Source modifiée pendant la lecture.")
    p,f,n=frames;h,w=f.shape[:2]
    base=lambda a:[d for d in detect(a) if d['kind']=='head']
    b=base(f);learned=detect_heads(f,model['weights'],model['bias'])
    ranked=prioritize(p,f,n,b,learned,base(p),base(n),limit=budget)
    packet=make_packet(sha,index,hashlib.sha256(f.tobytes()).hexdigest(),w,h,b,ranked['additional_review_candidates'],budget=budget)
    return dict(engine=ranked['engine'],packet=packet,frame_index=index,
        identity_verified=False,metrics_validated=False,statistical_use_allowed=False,
        pts_validated=False,scope="review_priority_only",source_sha256_at_creation=sha)
