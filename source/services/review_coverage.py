"""Frame-indexed review ledger. Sampled windows are never exhaustive annotation."""
from math import isfinite
import re

MAX_WINDOWS=1000
MAX_SAMPLES=250000

def require(ok,message):
    if not ok: raise ValueError(message)

def coverage(review,duration):
    ledger=review.get('review_windows')
    if ledger is None:return None
    require(isinstance(ledger,list) and len(ledger)<=MAX_WINDOWS,'Registre de couverture invalide.')
    fps=review.get('fps')
    require(type(fps) is int and 1<=fps<=240 and isinstance(duration,(int,float)) and not isinstance(duration,bool) and isfinite(duration) and duration>0,'Cadence/durée invalide.')
    n=round(duration*fps)
    require(abs(n-duration*fps)<1e-5,'Durée non alignée sur les images.')
    ids=set();paths={};spans=[];full=set();detail=set();total=0
    for w in ledger:
        require(isinstance(w,dict),'Fenêtre invalide.')
        uid=w.get('id');a=w.get('first_frame');b=w.get('last_frame');step=w.get('step_frames');view=w.get('view')
        require(isinstance(uid,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,60}',uid) and uid not in ids,'Identifiant fenêtre invalide ou dupliqué.');ids.add(uid)
        require(all(type(v) is int for v in (a,b,step)) and 0<=a<=b<n and 1<=step<=fps*2 and (b-a)%step==0,'Bornes ou pas de revue invalides.')
        require(view in {'full_frame','crop'},'Champ de revue invalide.')
        count=(b-a)//step+1
        require(type(w.get('sample_count')) is int and w['sample_count']==count,'Nombre de vues incohérent.')
        total+=count;require(total<=MAX_SAMPLES,'Trop de vues déclarées.')
        proof=w.get('sheets')
        require(isinstance(proof,list) and 1<=len(proof)<=100,'Planches de revue absentes.')
        seen=set()
        for p in proof:
            require(isinstance(p,dict),'Planche invalide.')
            path=p.get('path');sha=p.get('sha256');size=p.get('bytes')
            require(isinstance(path,str) and re.fullmatch(r'preuves/[A-Za-z0-9_.-]+\.jpg',path) and len(path)<=240 and path not in seen,'Chemin de planche invalide/dupliqué.');seen.add(path)
            require(isinstance(sha,str) and re.fullmatch(r'[a-f0-9]{64}',sha) and type(size) is int and 0<size<=100*1024*1024,'Empreinte de planche invalide.')
            require(path not in paths or paths[path]==(sha,size),'Empreintes contradictoires.');paths[path]=(sha,size)
        if view=='full_frame':
            full.update(range(a,b+1,step));spans.append((a,b+1))
        else:detail.update(range(a,b+1,step))
    merged=[]
    for a,b in sorted(spans):
        if merged and a<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],b)
        else:merged.append([a,b])
    gaps=[];cursor=0
    for a,b in merged:
        if a>cursor:gaps.append([cursor,a])
        cursor=b
    if cursor<n:gaps.append([cursor,n])
    span=sum(b-a for a,b in merged)
    def interval(x):return dict(first_frame=x[0],end_frame_exclusive=x[1],start_s=round(x[0]/fps,6),end_s=round(x[1]/fps,6),duration_s=round((x[1]-x[0])/fps,6))
    return dict(window_count=len(ledger),full_frame_windows=sum(w['view']=='full_frame' for w in ledger),crop_windows=sum(w['view']=='crop' for w in ledger),declared_samples=total,distinct_full_frame_samples=len(full),distinct_crop_samples=len(detail),distinct_any_samples=len(full|detail),total_source_frames=n,registered_full_frame_span_s=round(span/fps,6),registered_full_frame_span_pct=round(100*span/n,4),full_frame_sample_pct=round(100*len(full)/n,4),remaining_unregistered_span_s=round((n-span)/fps,6),gaps=[interval(x) for x in gaps],largest_gap=interval(max(gaps,key=lambda x:x[1]-x[0])) if gaps else None,distinct_sheets=len(paths),complete_annotation=False,files_verified_on_server=False,note='Couverture du registre déclaré uniquement. Une plage échantillonnée n’est pas une annotation exhaustive ; les recadrages ne couvrent pas toute la scène. Les anciennes revues non enregistrées ne sont pas incluses.')
