"""Persist detector outputs without promoting anonymous proposals into sports statistics."""
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from models import MatchVideoSegment, VisionScanEvidence

def canonical(obj):
    return json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)

def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()

def source_binding(match,segment):
    if segment is not None:
        if segment.match_id!=match.id: raise ValueError("Partie étrangère au match.")
        return digest([match.id,segment.id,segment.period,segment.source_type,segment.video_path,segment.video_url])
    return digest([match.id,None,match.video_source,match.video_path,match.video_url])

def save_scan(db,match,segment,kind,result,path):
    if kind not in {"tracklets","ball_motion"} or not isinstance(result,dict):
        raise ValueError("Type de proposition invalide.")
    # Reject unexpected promotion even when callers change in a later release.
    if any(result.get(key) is True for key in ("confirmed","identity_verified","metrics_validated","statistical_use_allowed","pts_validated")):
        raise ValueError("Un prototype ne peut pas certifier une mesure.")
    binding=source_binding(match,segment)
    stat=path.stat()
    payload={"schema":"vision-scan-v1","kind":kind,"source_binding":binding,
        "source_file_size":stat.st_size,"source_file_mtime_ns":stat.st_mtime_ns,
        "source_bytes_verified":False,"result":result}
    raw=canonical(payload)
    if len(raw.encode())>2*1024*1024: raise ValueError("Fenêtre de suivi trop volumineuse.")
    sha=digest(payload)
    stmt=select(VisionScanEvidence).where(VisionScanEvidence.match_id==match.id,VisionScanEvidence.digest==sha)
    row=db.scalar(stmt)
    if row:return row
    row=VisionScanEvidence(match_id=match.id,segment_id=segment.id if segment else None,
        kind=kind,source_binding=binding,digest=sha,payload_json=raw)
    try:
        with db.begin_nested():
            db.add(row);db.flush()
    except IntegrityError:
        row=db.scalar(stmt)
        if row is None:raise
    db.commit()
    return row

def read_scan(row):
    payload=json.loads(row.payload_json)
    if digest(payload)!=row.digest or payload.get("source_binding")!=row.source_binding or payload.get("kind")!=row.kind:
        raise ValueError("Empreinte de proposition incohérente.")
    return {"id":row.id,"digest":row.digest,"segment_id":row.segment_id,**payload}

def report(db,match):
    segments={s.id:s for s in db.scalars(select(MatchVideoSegment).where(MatchVideoSegment.match_id==match.id))}
    rows=[];stale=0
    for row in db.scalars(select(VisionScanEvidence).where(VisionScanEvidence.match_id==match.id).order_by(VisionScanEvidence.id)):
        segment=segments.get(row.segment_id)
        if (row.segment_id is not None and segment is None) or row.source_binding!=source_binding(match,segment):
            stale+=1;continue
        try:
            r=read_scan(row)["result"]
            frames=r.get("frames",[])
            rows.append({"id":row.id,"segment_id":row.segment_id,"period":segment.period if segment else None,
                "kind":row.kind,"engine":r.get("engine"),"mode":r.get("tracking_mode"),
                "first_frame":r.get("first_frame",r.get("frame_index")),
                "end_frame_exclusive":r.get("end_frame_exclusive"),
                "sampled_frames":len(frames) if row.kind=="tracklets" else None,
                "tracklets":r.get("tracklets_total"),"tracklets_at_least_3":r.get("tracklets_at_least_3"),
                "ball_candidates":len(r.get("candidates",[])) if row.kind=="ball_motion" else None,
                "digest":row.digest})
        except (ValueError,TypeError,KeyError,AttributeError):stale+=1
    return {"status":"experimental_partial" if rows else "unavailable","rows":rows,"stale_count":stale,
        "scope":"per_window_not_unique_athletes","source_binding":"metadata_only_not_video_hash",
        "identity_verified":False,"metrics_validated":False,"statistical_use_allowed":False}


def export_scans(db,match,summary):
    """Export the exact evidence rows cited by a canonical snapshot, never stale rows."""
    ids={r["id"]:r["digest"] for r in summary.get("rows",[])}
    if not ids:return []
    records=db.scalars(select(VisionScanEvidence).where(VisionScanEvidence.match_id==match.id,VisionScanEvidence.id.in_(ids))).all()
    result=[]
    for row in records:
        if ids[row.id]!=row.digest:continue
        try:result.append(read_scan(row))
        except (ValueError,TypeError,KeyError,AttributeError):continue
    return sorted(result,key=lambda r:r["id"])
