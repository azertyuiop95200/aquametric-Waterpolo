"""Private R2/S3 gigabyte video -> bounded 60-second MP4 clips by signed HTTP range.

Never copy an entire multi-GB video into Render, never expose signing keys,
and never use the public dashboard's browser to ask for AI API credentials.
Video duration is probed by FFprobe; AI-generated actions remain provisional.
S3-compatible storage must support HTTP Range for efficient remote seeks.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from sqlalchemy import select

from models import LargeVideoUpload, Match, VideoActionAnalysis
from services import large_video_storage as store
from services.media import _run_ffmpeg
from services.browser_capture_media import ffprobe_video
from services.video_action_provider import VideoActionError, provider_configuration, analyze_video_segment
from services.video_action_runner import normalize_observations, segment_plan

BUDGET_SECONDS=330
MAX_VIDEO_SECONDS=4*3600


def _probe_remote_mp4(key: str) -> dict:
    """FFprobe uses byte ranges; if provider cannot seek, fail closed."""
    command=shutil.which("ffprobe")
    if not command:
        raise VideoActionError("ffprobe_missing",
            "Traitement cloud suspendu : FFprobe doit être installé sur le worker.")
    url=store.signed_video_url(key)
    try:
        proc=subprocess.run([
            command,"-hide_banner","-v","error","-rw_timeout","12000000",
            "-select_streams","v:0",
            "-show_entries","stream=width,height:format=duration",
            "-of","json",url],capture_output=True,text=True,timeout=35,
        )
        if proc.returncode!=0 or len(proc.stdout)>64000:
            raise ValueError("probe_failed")
        raw=json.loads(proc.stdout)
        stream=(raw.get("streams") or [{}])[0]
        seconds=float((raw.get("format") or {}).get("duration") or 0)
        if not(math.isfinite(seconds) and 0<seconds<=MAX_VIDEO_SECONDS
               and int(stream.get("width") or 0)>0 and int(stream.get("height") or 0)>0):
            raise ValueError("duration/geometry")
    except (ValueError,TypeError,KeyError,subprocess.SubprocessError):
        raise VideoActionError("cloud_unreadable",
            "Vidéo cloud non décodable en lecture distante (durée, format ou accès HTTP Range).") from None
    return {"duration":seconds,"width":int(stream["width"]),"height":int(stream["height"])}


def _encode_remote_segment(key: str, segment: dict, path:Path):
    """Bounded output; ffmpeg requests only the needed segment of the private object."""
    duration=segment["clip_end"]-segment["clip_start"]
    if not 0<duration<=62:
        raise VideoActionError("clip_range","Intervalle vidéo cloud invalide.")
    url=store.signed_video_url(key)
    try:
        _run_ffmpeg([
            "-rw_timeout","12000000",
            "-ss",f"{segment['clip_start']:.3f}",
            "-i",url,
            "-t",f"{duration:.3f}",
            "-map","0:v:0","-an",
            "-vf","scale=w='trunc(min(960,iw)/2)*2':h=-2,fps=8",
            "-c:v","libx264","-threads","1",
            "-preset","veryfast","-crf","25",
            "-maxrate","900k","-bufsize","1800k",
            "-pix_fmt","yuv420p","-movflags","+faststart",
            str(path)],timeout=75,
        )
        metadata=ffprobe_video(path)
        if not metadata.get("ok") or metadata["duration"]<duration-max(0.9,duration*0.04):
            raise ValueError("short remote clip")
        if path.stat().st_size>14*1024*1024:
            raise ValueError("cloud clip too large")
    except Exception:
        # subprocess stderr could contain a signed URL; NEVER surface it.
        raise VideoActionError("cloud_clip",
            "Impossible de décoder ce segment distant. Le fournisseur doit autoriser les requêtes Range.") from None


def _checkpoint(db,run,plan):
    run.segments_json=json.dumps(plan,ensure_ascii=False)
    run.updated_at=time.time()
    db.commit()


def cloud_fingerprint(match, key:str, model:str) -> str:
    identity=["cloud-s3-actions-v1",match.id,match.owner_id,key,model,match.team.name,match.opponent]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def run_cloud_video_actions(match_id:int, object_key:str) -> None:
    from db import SessionLocal
    from services.video_action_runner import _WORK_LOCK
    with _WORK_LOCK:
        with SessionLocal() as db:
            match=db.get(Match,match_id)
            if not match or not object_key:
                return
            # Bound object access to one completed, owner-owned multipart upload.
            row=db.scalar(select(LargeVideoUpload).where(
                LargeVideoUpload.match_id==match.id,
                LargeVideoUpload.owner_id==match.owner_id,
                LargeVideoUpload.object_key==object_key,
                LargeVideoUpload.status=="complete"))
            if not row:
                return
            config=provider_configuration()
            if not config["configured"] or not store.configured():
                return
            identity=cloud_fingerprint(match,object_key,config["model"])
            run=db.scalar(select(VideoActionAnalysis).where(
                VideoActionAnalysis.fingerprint==identity))
            if not run:
                run=VideoActionAnalysis(match_id=match.id,fingerprint=identity,
                    source_kind="cloud",source_path=object_key,model=config["model"],
                    status="queued",message="Fichier privé en attente de détection vidéo.")
                db.add(run);db.commit();db.refresh(run)
            if run.status=="complete":
                return
            if run.status=="running" and time.time()-float(run.updated_at or 0)<BUDGET_SECONDS+60:
                return
            plan=json.loads(run.segments_json or "[]")
            try:
                if not plan:
                    metadata=_probe_remote_mp4(object_key)
                    plan,duration=segment_plan(metadata["duration"])
                    run.duration_seconds=duration
                    _checkpoint(db,run,plan)
                for entry in plan:
                    if entry["status"]=="running":
                        entry["status"]="pending"
                run.status="running"
                run.message="Traitement cloud par intervalles ; aucune copie du gros fichier sur Render."
                _checkpoint(db,run,plan)
                deadline=time.monotonic()+BUDGET_SECONDS
                for segment in plan:
                    if segment["status"]=="complete":
                        continue
                    if deadline-time.monotonic()<35:
                        break
                    segment["status"]="running"
                    _checkpoint(db,run,plan)
                    try:
                        with tempfile.TemporaryDirectory(prefix="cloud-video-clip-") as temp:
                            clip=Path(temp)/"clip.mp4"
                            _encode_remote_segment(object_key,segment,clip)
                            remaining=deadline-time.monotonic()
                            if remaining<12:
                                raise VideoActionError("budget","Temps de traitement atteint.")
                            observations=analyze_video_segment(
                                clip,team=match.team.name,opponent=match.opponent,
                                timeout=min(75,remaining-4))
                        segment["result"]=normalize_observations(observations,segment)
                        segment["status"]="complete"
                        segment.pop("error",None)
                        segment.pop("error_code",None)
                    except VideoActionError as exc:
                        segment["status"]="failed"
                        segment["error_code"]=exc.code
                        segment["error"]=str(exc)
                        if exc.code in {"budget","quota","credentials","cloud_clip","cloud_unreadable"}:
                            break
                    except Exception:
                        segment["status"]="failed"
                        segment["error_code"]="processing"
                        segment["error"]="Impossible d'analyser ce passage ; les autres preuves restent conservées."
                    finally:
                        _checkpoint(db,run,plan)
                completed=sum(item["status"]=="complete" for item in plan)
                run.status="complete" if completed==len(plan) and plan else "partial" if completed else "failed"
                run.message=f"{completed}/{len(plan)} passages vidéo cloud analysés ; résultats provisoires à vérifier."
            except VideoActionError as exc:
                run.status="partial" if any(s["status"]=="complete" for s in plan) else "failed"
                run.message=str(exc)
            except Exception:
                db.rollback()
                run.status="partial" if any(s.get("status")=="complete" for s in plan) else "failed"
                run.message="Le worker cloud a été interrompu ; la vidéo privée est conservée."
            _checkpoint(db,run,plan)
