"""Several real source videos in one match, preserving quarter/part provenance.

The video file itself is not an event detector. It becomes an evidence source for
timestamped human annotation and for separately configured analysis workers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import get_db
from models import Match, MatchVideoSegment, User
from services.video import is_http_url, youtube_embed
from services.large_video_storage import signed_video_url
from fastapi.responses import RedirectResponse as Redirect

router=APIRouter(tags=["match video segments"])

def _owned(match_id:int, request:Request, db:Session):
    owner_id = request.session.get("user_id")
    user = db.get(User,owner_id) if owner_id else None
    if not user:
        raise HTTPException(401,"Connecte-toi pour accéder au match.")
    match = db.get(Match,match_id)
    if not match or match.owner_id!=user.id:
        raise HTTPException(404,"Match introuvable.")
    return user,match


def _segment_kind(match):
    return match.video_source if match.video_source in {"cloud","upload","youtube","url"} else ""


def segment_rows(db:Session, match:Match) -> list[dict]:
    """Include historical single-video matches without altering old records."""
    rows = list(db.scalars(select(MatchVideoSegment).where(
        MatchVideoSegment.match_id==match.id).order_by(
        MatchVideoSegment.part_index,MatchVideoSegment.id)).all())
    result = []
    primary_type = _segment_kind(match)
    is_registered=any(
        s.source_type==primary_type and s.video_url==(match.video_url or "")
        and s.video_path==(match.video_path or "") for s in rows
    )
    if primary_type and not is_registered:
        result.append({
            "id":None,"period":1,"part_index":1,"label":"Partie 1 · vidéo initiale",
            "source_type":primary_type,"video_url":match.video_url or "",
            "video_path":match.video_path or "","match_id":match.id,
            "play_url":f"/matches/{match.id}/video" if primary_type in {"upload","cloud"} else "",
            "embed":youtube_embed(match.video_url or "") or "",
        })
    for row in rows:
        result.append({
            "id":row.id,"period":row.period,"part_index":row.part_index,
            "label":row.label or f"Partie {row.part_index}",
            "source_type":row.source_type,"video_url":row.video_url,
            "video_path":row.video_path,"match_id":match.id,
            "play_url":f"/matches/{match.id}/segments/{row.id}/video"
                if row.source_type in {"cloud","upload"} else "",
            "embed":youtube_embed(row.video_url or "") or "",
        })
    return sorted(result,key=lambda x:(x["part_index"],x["id"] or 0))


def _validate_period(period:int):
    if period<1 or period>8:
        raise HTTPException(400,"Quart-temps / période hors de 1 à 8.")


def append_segment(db:Session, match:Match, *, period:int, label:str, source_type:str,
                   video_path:str="", video_url:str="") -> MatchVideoSegment:
    _validate_period(period)
    if source_type not in {"cloud","upload","youtube","url"}:
        raise HTTPException(400,"Source vidéo non prise en charge.")
    existing=segment_rows(db,match)
    if len(existing)>=24:
        raise HTTPException(413,"Nombre maximal de 24 parties vidéo atteint.")
    if any(item["video_url"]==video_url and item["video_path"]==video_path
           and item["source_type"]==source_type for item in existing):
        raise HTTPException(409,"Cette vidéo figure déjà dans le match.")
    index = max((int(s["part_index"]) for s in existing),default=0)+1
    row=MatchVideoSegment(
        match_id=match.id,period=period,part_index=index,
        label=(label or f"Q{period} · partie {index}").strip()[:100],
        source_type=source_type,video_path=video_path,video_url=video_url,
    )
    db.add(row)
    if not _segment_kind(match):
        # Historical readers get a primary player without special-casing the
        # first split-video match. The display helper de-duplicates it.
        match.video_source=source_type
        match.video_url=video_url
        match.video_path=video_path
        match.status="video_received_not_analyzed"
    db.flush()
    return row


@router.post("/matches/{match_id}/segments")
def add_video_segment(match_id:int, request:Request, background_tasks:BackgroundTasks,
                      period:int=Form(1),label:str=Form(""),video_url:str=Form(""),
                      youtube_duration_minutes:float=Form(0.0,ge=0,le=240),
                      video_file:Optional[UploadFile]=File(None),
                      db:Session=Depends(get_db)):
    user,match=_owned(match_id,request,db)
    _validate_period(period)
    url=(video_url or "").strip()
    file_provided=bool(video_file and video_file.filename)
    if file_provided==bool(url):
        raise HTTPException(400,"Choisis soit un fichier, soit une URL vidéo.")
    if file_provided:
        from analysis_input_routes_v2 import _save_upload
        source="upload"
        path = _save_upload(video_file,user.id,match.team_id)
        url=""
    else:
        if not is_http_url(url):
            raise HTTPException(400,"Seuls les liens HTTP/HTTPS sont acceptés.")
        path=""
        source="youtube" if youtube_embed(url) else "url"
    try:
        segment=append_segment(db,match,period=period,label=label,source_type=source,
                       video_path=path,video_url=url)
        db.commit()
        if source in {"upload","youtube"}:
            from services.video_action_provider import provider_configuration
            if provider_configuration()["configured"]:
                if source=="upload":
                    from video_action_routes import run_segment_actions
                    background_tasks.add_task(run_segment_actions, match_id, segment.id)
                elif youtube_duration_minutes>0:
                    from services.youtube_direct_actions import (
                        prepare_run, run_direct_youtube_actions,
                    )
                    try:
                        run,scheduled=prepare_run(db,match,round(youtube_duration_minutes*60,3),
                                                  video_url=url)
                        if scheduled:
                            background_tasks.add_task(run_direct_youtube_actions,match_id,run.id)
                    except ValueError:
                        # URL saved for manual replay: no false inference if it
                        # is not a canonical public YouTube video.
                        pass
    except Exception:
        db.rollback()
        if file_provided:
            from analysis_input_routes_v2 import UPLOAD_DIR
            (UPLOAD_DIR/Path(path).name).unlink(missing_ok=True)
        raise
    return RedirectResponse(f"/matches/{match_id}/analysis/result#sources",status_code=303)


@router.get("/matches/{match_id}/segments/{segment_id}/video")
def open_video_segment(match_id:int,segment_id:int,request:Request,db:Session=Depends(get_db)):
    _owned(match_id,request,db)
    segment=db.get(MatchVideoSegment,segment_id)
    if not segment or segment.match_id!=match_id:
        raise HTTPException(404)
    if segment.source_type=="cloud":
        return Redirect(status_code=307,url=signed_video_url(segment.video_path))
    if segment.source_type=="upload":
        from analysis_input_routes_v2 import UPLOAD_DIR
        path=UPLOAD_DIR/Path(segment.video_path).name
        if path.is_file():
            return FileResponse(path)
        raise HTTPException(404,"Le fichier local n'est plus disponible. Utilise un stockage persistant.")
    raise HTTPException(404,"Ce segment n'est pas un fichier vidéo local.")


@router.get("/api/matches/{match_id}/segments")
def segments_api(match_id:int,request:Request,db:Session=Depends(get_db)):
    _,match=_owned(match_id,request,db)
    return {"match_id":match.id,"segments":segment_rows(db,match)}

@router.get("/api/matches/{match_id}/shot-map")
def shot_map_api(match_id:int,request:Request,db:Session=Depends(get_db)):
    """Owner-scoped verified coordinates with an explicit coverage denominator."""
    _,match=_owned(match_id,request,db)
    from services.spatial_match_analysis import spatial_match_dashboard
    return spatial_match_dashboard(db,match,segment_rows(db,match))

@router.post("/matches/{match_id}/segments/{segment_id}/youtube/direct")
def analyze_youtube_quarter(
    match_id:int, segment_id:int, request:Request, background_tasks:BackgroundTasks,
    duration_minutes:float=Form(...,gt=0,le=240),
    db:Session=Depends(get_db),
):
    _,match=_owned(match_id,request,db)
    segment=db.get(MatchVideoSegment,segment_id)
    if not segment or segment.match_id!=match.id or segment.source_type!="youtube":
        raise HTTPException(404,"Extrait YouTube introuvable.")
    from services.youtube_direct_actions import (
        canonical_public_youtube, prepare_run, run_direct_youtube_actions,
    )
    from services.video_action_provider import VideoActionError
    try:
        canonical_public_youtube(segment.video_url)
        run,scheduled=prepare_run(db,match,round(duration_minutes*60,3),
                                  video_url=segment.video_url)
    except (ValueError,VideoActionError) as exc:
        raise HTTPException(400 if isinstance(exc,ValueError) else 503,str(exc)) from None
    if scheduled:
        background_tasks.add_task(run_direct_youtube_actions,match.id,run.id)
    return RedirectResponse(f"/matches/{match.id}/analysis/result#liveAutomaticStats",status_code=303)
