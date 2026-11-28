"""Bounded local native scan batch, adapted from the specialist implementation.
Candidate evidence only; no full-match, identity, PTS or metric validation.
"""
from pathlib import Path
from hashlib import sha256
from time import monotonic
import logging
import json
import cv2
from services.local_clip_scan import scan_clip
from services.vision_scan_evidence import save_scan,report,export_scans,source_binding

MODES=("baseline","head_flow")
POLICY="bounded-local-scan-r7-v2"

def fingerprint(path):
    path=Path(path);before=path.stat()
    if before.st_size>1200*1024*1024:raise ValueError("Source trop volumineuse.")
    h=sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError("Source modifiée.")
    return h.hexdigest(),(after.st_size,after.st_mtime_ns)

def plan(total,count=4,frame_count=75):
    if type(total) is not int or total<1 or type(count) is not int or not 1<=count<=12 or type(frame_count) is not int or not 1<=frame_count<=75:
        raise ValueError("Plan de scan invalide.")
    length=min(frame_count,total)
    return [(s,length) for s in sorted({round((i+.5)*(total-length)/count) for i in range(count)})]

def run(db,match,path,*,window_count=4,frame_count=25,budget_s=35):
    path=Path(path)
    if match.video_source!="upload" or not match.video_path or path.name!=Path(match.video_path).name:raise ValueError("Source locale principale requise.")
    if type(budget_s) not in (int,float) or not 0<budget_s<=120:raise ValueError("Budget invalide.")
    start_clock=monotonic();sha,stat=fingerprint(path)
    cap=cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():raise ValueError("Vidéo illisible.")
        total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:cap.release()
    windows=plan(total,window_count,frame_count)
    existing={}
    for row in export_scans(db,match,report(db,match)):
        r=row["result"]
        if row["segment_id"] is None and r.get("source_sha256_at_creation")==sha and r.get("batch_policy")==POLICY and r.get("scan_status")=="completed" and (r.get("source_file_size"),r.get("source_file_mtime_ns"))==stat:
            existing[(r.get("first_frame"),r.get("end_frame_exclusive"),r.get("tracking_mode"))]=row
    ids=[];failed=[];reused=0;sampled=set();completed=set()
    for start,n in windows:
        for mode in MODES:
            key=(start,start+n,mode)
            try:
                now=path.stat()
                if (now.st_size,now.st_mtime_ns)!=stat:raise ValueError("Source modifiée.")
                if key in existing:
                    row=existing[key];r=row["result"];ident=row["id"];reused+=1
                else:
                    if monotonic()-start_clock>=budget_s:
                        failed.append(dict(first_frame=start,mode=mode,reason="budget"));continue
                    r=scan_clip(path,start,n,tracking_mode=mode)
                    if r.get("source_sha256_at_creation")!=sha or r.get("source_frame_count_reported")!=total:
                        raise ValueError("Source modifiée.")
                    r.update(batch_policy=POLICY,scan_status="completed")
                    ident=save_scan(db,match,None,"tracklets",r,path).id
                ids.append(ident);completed.add((start,start+n))
                sampled.update(f["source_frame_index"] for f in r["frames"])
            except (OSError,ValueError,cv2.error) as exc:
                failed.append(dict(first_frame=start,mode=mode,reason=type(exc).__name__))
    return dict(status="experimental_partial" if ids else "unavailable",policy=POLICY,
        source_binding=source_binding(match,None),source_sha256_at_execution=sha,source_frames_reported=total,
        planned_windows=len(windows),completed_windows=len(completed),planned_runs=len(windows)*len(MODES),
        persisted_ids=ids,reused_runs=reused,failed=failed,unique_sampled_frames=len(sampled),
        sampled_frame_pct=round(100*len(sampled)/total,4),statistical_use_allowed=False,
        scope="primary_source_sampled_windows_only",pts_validated=False)

def attach(db,match,path,result):
    """Run after rapid analysis on both native entry points. Preserve earlier result on failure."""
    try:batch=run(db,match,path)
    except Exception:
        db.rollback()
        logging.getLogger(__name__).exception("Native local scan batch failed")
        batch=dict(status="unavailable",policy=POLICY,reason="local_source_or_scan_unavailable",statistical_use_allowed=False)
    result["local_scan_batch"]=batch
    auto=result.get("autonomy")
    if auto is not None:
        try:
            db.refresh(auto)
            summary=json.loads(auto.summary_json or "{}")
            summary["local_scan_batch"]=batch
            auto.summary_json=json.dumps(summary,ensure_ascii=False,allow_nan=False)
            result.setdefault("summary",{})["local_scan_batch"]=batch
            db.commit()
        except Exception:
            db.rollback()
            logging.getLogger(__name__).exception("Native scan batch summary could not be saved")
    return batch

def snapshot_summary(match,summary,vision_report):
    b=summary.get("local_scan_batch")
    if not isinstance(b,dict) or b.get("policy")!=POLICY:return None
    if b.get("status")=="unavailable" and not b.get("persisted_ids"):return dict(status="unavailable",policy=POLICY)
    if b.get("source_binding")!=source_binding(match,None):return None
    ids=b.get("persisted_ids",[])
    current={r["id"] for r in vision_report.get("rows",[]) if r.get("scan_status")=="completed"}
    if not ids or not all(i in current for i in ids):return None
    return dict(b,source_bytes_verified_on_read=False)
