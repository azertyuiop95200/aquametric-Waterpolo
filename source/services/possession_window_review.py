"""Adapter of specialist possession evidence into the shared report.
Independent, reviewed windows, never insert a sporting Event or a match total.
"""
import json
from pathlib import Path
from math import isfinite
from sqlalchemy import select
from models import MatchVideoSegment
from services.vision_scan_evidence import source_binding
from services.possession_evidence import build_note,report,CAUSES
from services.r7_review_pipeline import file_hash

KEY="possession_window_reviews"
LIMIT=64
FLAGS=("cause_verified","decision_verified","exact","prior_shot","restart_verified")

def sources(db,match):
    segments=list(db.scalars(select(MatchVideoSegment).where(MatchVideoSegment.match_id==match.id).order_by(MatchVideoSegment.id)))
    valid=[s for s in segments if s.source_type=="upload" and s.video_path and type(s.period) is int and 1<=s.period<=8]
    # One physical source cannot be counted under several aliases.
    counts={}
    for s in segments:
        if s.source_type=="upload" and s.video_path:
            name=Path(s.video_path).name;counts[name]=counts.get(name,0)+1
    out={str(s.id):s for s in valid if counts[Path(s.video_path).name]==1}
    if match.video_source=="upload" and match.video_path and Path(match.video_path).name not in counts:
        out["match"]=None
    return out

def clean(raw,segment):
    if not isinstance(raw,dict):raise ValueError("Revue invalide.")
    for key in FLAGS:
        if type(raw.get(key)) is not bool:raise ValueError("Drapeau de preuve invalide.")
    q=raw.get("period")
    if type(q) is not int or not 1<=q<=8 or (segment is not None and q!=segment.period):
        raise ValueError("Période incompatible avec la source.")
    if raw.get("source_reviewed") is not True:raise ValueError("Confirmer la source et les bornes vidéo.")
    note=raw.get("evidence")
    if not isinstance(note,str) or not 3<=len(note.strip())<=180:raise ValueError("Justification visuelle de 3 à 180 caractères requise.")
    a,b=raw.get("start"),raw.get("end")
    if not all(type(v) in (float,int) and isfinite(v) for v in (a,b)) or not 0<=a<b<=43200:
        raise ValueError("Intervalle invalide.")
    if b-a>30:raise ValueError("Fenêtre de contrôle limitée à 30 secondes.")
    vals={k:raw.get(k) for k in ("start","end","before","after","before_state","after_state","cause","restart_award",*FLAGS)}
    vals["evidence"]=note.strip()
    # Do not let note text inject tags. Preserve microsecond precision separately
    # because the original formatter uses :g.
    machine=build_note(**vals,period=q,segment=segment.id if segment else None)
    if not machine:raise ValueError("Preuve invalide.")
    return dict(vals,period=q,source_reviewed=True)

def read_report(db,match,auto):
    out=report([])
    available=sources(db,match)
    out.update(status="unavailable",scope="reviewed_windows_not_match_totals",source_bytes_verified_on_read=False,
        analysis_id=auto.id if auto else None,sources=[dict(key=k,period=s.period if s else None,label=s.label or f"Partie {s.id}" if s else "Source principale") for k,s in available.items()])
    if auto is None:return out
    summary=json.loads(auto.summary_json or "{}")
    records=summary.get(KEY,[])
    if not isinstance(records,list) or len(records)>LIMIT:return dict(out,status="invalid")
    events=[];rejected=[]
    for r in records:
        try:
            k=r["source"];seg=available[k]
            if r["binding"]!=source_binding(match,seg) or r["analysis_id"]!=auto.id:raise ValueError("Source ou analyse modifiée.")
            v=clean(r["review"],seg)
            # Original module consumes event-shaped note records, but these
            # are transient adapters, not official Event records.
            note=build_note(**{x:y for x,y in v.items() if x not in ("period","source_reviewed")},period=v["period"],segment=seg.id if seg else None)
            events.append(dict(id=r["id"],event_type="possession_transition",confidence="CONFIRMED",second=v["end"],note=note))
        except (ValueError,TypeError,KeyError,AttributeError):rejected.append(dict(id=r.get("id","?") if isinstance(r,dict) else "?",reason="Revue invalide ou source périmée."))
    calculated=report(events)
    calculated["rejected"].extend(rejected)
    return dict(out,**calculated,status="experimental_partial" if calculated["rows"] else "unavailable")

def append(db,match,auto,raw,upload_dir):
    available=sources(db,match);key=raw.get("source")
    if key not in available:raise ValueError("Source non enregistrée ou ambiguë.")
    if raw.get("analysis_id")!=auto.id:raise ValueError("Analyse périmée.")
    seg=available[key];v=clean(raw,seg)
    path=Path(upload_dir)/Path(seg.video_path if seg else match.video_path).name
    if not path.is_file():raise ValueError("Vidéo locale indisponible.")
    stat=path.stat()
    if stat.st_size>1200*1024*1024:raise ValueError("Vidéo trop volumineuse pour cette revue.")
    sha=file_hash(path)
    # Require source duration if registered, otherwise obtain nominal bounds
    # from the real decoder. This does not certify the game clock or PTS.
    import cv2
    cap=cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():raise ValueError("Vidéo illisible.")
        fps=float(cap.get(cv2.CAP_PROP_FPS));n=float(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not isfinite(fps) or not isfinite(n) or fps<=0 or n<=0 or v["end"]>n/fps+1e-6:raise ValueError("Fenêtre hors vidéo.")
    finally:cap.release()
    end=path.stat()
    if (stat.st_size,stat.st_mtime_ns)!=(end.st_size,end.st_mtime_ns):raise ValueError("Source modifiée.")
    summary=json.loads(auto.summary_json or "{}")
    rows=summary.get(KEY,[])
    if not isinstance(rows,list) or len(rows)>=LIMIT:raise ValueError("Limite de 64 fenêtres par analyse.")
    binding=source_binding(match,seg)
    same=[r for r in rows if r.get("binding")==binding]
    if any(r.get("source_sha256")!=sha for r in same):raise ValueError("Octets source modifiés ; nouvelle analyse nécessaire.")
    # Exclude duplicate or overlapping reviewed windows from new submissions.
    if any(r["review"]["period"]==v["period"] and r["review"]["start"]<v["end"] and v["start"]<r["review"]["end"] for r in same):
        raise ValueError("Fenêtre déjà revue ou chevauchante.")
    # Precision of the specialist note contract: fail instead of rounding silently.
    if float(format(v["start"],"g"))!=v["start"]:raise ValueError("Borne de début trop précise pour le contrat de preuve.")
    rows.append(dict(id=f"P{len(rows)+1}",source=key,binding=binding,analysis_id=auto.id,source_sha256=sha,review=v))
    summary[KEY]=rows
    auto.summary_json=json.dumps(summary,ensure_ascii=False,allow_nan=False)
    return rows[-1]
