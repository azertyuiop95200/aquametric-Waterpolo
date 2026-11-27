"""Private, event-linked 3D review routes. No pixels or tracks are fabricated."""
import json
from hashlib import sha256
from math import isfinite
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Column, Integer, Text, ForeignKey, select
from sqlalchemy.orm import Session
from db import Base, get_db
from models import Match, User, Event, SpatialReview, MatchVideoSegment, EventPosition
from services.event_evidence import verified_events
from services.video import youtube_embed
from services.spatial_replay import review

router=APIRouter()
templates=Jinja2Templates(directory=Path(__file__).parent/"templates")
KINDS={"goal","shot_on_target","shot_off_target","shot_blocked","bad_pass","turnover","pass_complete","key_pass","assist"}

def owned(request,db,match_id):
    uid=request.session.get("user_id")
    user=db.get(User,uid) if uid else None
    if not user: raise HTTPException(401,"Login required")
    match=db.get(Match,match_id)
    if not match or match.owner_id!=user.id: raise HTTPException(404,"Match not found")
    return user,match

def has_segments(db, match):
    return db.scalar(select(MatchVideoSegment.id).where(MatchVideoSegment.match_id == match.id).limit(1)) is not None

def event_sources(db, match):
    """Bind verified actions to declared source metadata; no inference from period alone."""
    segments={s.id:s for s in db.scalars(select(MatchVideoSegment).where(MatchVideoSegment.match_id==match.id)).all()}
    positions={p.event_id:p for p in db.scalars(select(EventPosition).join(Event,Event.id==EventPosition.event_id).where(Event.match_id==match.id)).all()}
    result={}
    for e in verified_events(match.events):
        if e.event_type not in KINDS: continue
        p=positions.get(e.id)
        seg=segments.get(p.segment_id) if p and p.segment_id is not None else None
        if p and p.segment_id is not None and not seg: continue
        if segments and not seg: continue  # ambiguous legacy event, never guess a segment
        if seg and (p.provenance!="manual_verified" or p.period!=seg.period or p.segment_second is None): continue
        second=p.segment_second if p and p.segment_second is not None else e.second
        if not isinstance(second,(int,float)) or not isfinite(second) or not 0<=second<=86400: continue
        if seg and seg.duration_seconds and second>seg.duration_seconds: continue
        kind,path,url=(seg.source_type,seg.video_path,seg.video_url) if seg else (match.video_source,match.video_path,match.video_url)
        embed=youtube_embed(url)
        play=(f"/matches/{match.id}/segments/{seg.id}/video" if seg else f"/matches/{match.id}/video") if kind in {"upload","cloud"} and path else ""
        if not play and not embed: continue
        binding=sha256(json.dumps([match.id,e.id,e.event_type,e.second,seg.id if seg else None,seg.period if seg else (p.period if p else None),second,kind,path,url],ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        result[e.id]={"id":e.id,"second":float(second),"kind":e.event_type,"player":e.player.name if e.player else None,
            "segment_id":seg.id if seg else None,"period":seg.period if seg else (p.period if p else None),
            "label":seg.label or f"Partie {seg.part_index}" if seg else "Vidéo principale",
            "play_url":play,"embed":embed or "","binding":binding}
    return result

def eligible(db, match):
    ids=event_sources(db,match)
    return sorted((e for e in verified_events(match.events) if e.id in ids),key=lambda e:(ids[e.id]["period"] or 99,ids[e.id]["segment_id"] or 0,ids[e.id]["second"],e.id))

def saved_reviews(db,match):
    sources=event_sources(db,match)
    if not sources: return {}
    rows=db.scalars(select(SpatialReview).where(SpatialReview.match_id==match.id,SpatialReview.owner_id==match.owner_id)).all()
    result={}
    for row in rows:
        source=sources.get(row.event_id)
        if not source: continue
        try:
            payload=json.loads(row.payload)
            if not isinstance(payload,dict) or payload.get("binding")!=source["binding"]: continue
            result[row.event_id]=payload
        except (ValueError,TypeError): continue
    return result

@router.get("/matches/{match_id}/spatial",response_class=HTMLResponse)
def spatial_page(match_id:int,request:Request,db:Session=Depends(get_db)):
    user,match=owned(request,db,match_id)
    sources=event_sources(db,match)
    events=[sources[e.id] for e in eligible(db,match)]
    return templates.TemplateResponse(request,"spatial_review.html",dict(request=request,user=user,app_name="AquaMetric",
        match=match,events=events,reviews=saved_reviews(db,match),embed=youtube_embed(match.video_url)))

@router.post("/matches/{match_id}/spatial/{event_id}")
async def spatial_save(match_id:int,event_id:int,request:Request,db:Session=Depends(get_db)):
    user,match=owned(request,db,match_id)
    source=event_sources(db,match).get(event_id)
    if source is None: raise HTTPException(404,"Verified eligible event and source required")
    # Bound incoming payload even when the caller omits Content-Length.
    body=bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk)>32768: raise HTTPException(413,"Observation too large")
        body.extend(chunk)
    try:
        data=json.loads(body)
        if not isinstance(data,dict): raise ValueError('Observation invalide')
        if data.get('source_binding')!=source['binding']: raise ValueError('Source modifiée ou non confirmée : recharger la scène.')
        from starlette.concurrency import run_in_threadpool
        result=await run_in_threadpool(review,data)
        second=source["second"]
        if not max(0,second-10)<=result["decision_second"]<=second:
            raise ValueError("Décision hors de la fenêtre vidéo locale précédant l'action.")
        payload=json.dumps(dict(observations=data,result=result,binding=source["binding"],
            video_source={k:source[k] for k in ("segment_id","period","second","label")}),allow_nan=False)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as exc:
        raise HTTPException(422,"Invalid spatial observation: "+str(exc)[:200]) from exc
    row=db.get(SpatialReview,event_id)
    if row and (row.owner_id!=user.id or row.match_id!=match.id):
        raise HTTPException(409,"Review ownership conflict")
    if row: row.payload=payload
    else: db.add(SpatialReview(event_id=event_id,owner_id=user.id,match_id=match.id,payload=payload))
    db.commit()
    return JSONResponse(result,headers={"Cache-Control":"private, no-store"})

@router.get("/matches/{match_id}/spatial.json")
def spatial_export(match_id:int,request:Request,db:Session=Depends(get_db)):
    _,match=owned(request,db,match_id)
    return JSONResponse({"match_id":match.id,"eligible_count":len(eligible(db,match)),"reviews":saved_reviews(db,match)},
        headers={"Cache-Control":"private, no-store","Content-Disposition":f'attachment; filename="spatial-{match_id}.json"'})


def sandbox_baseline(request,db,match_id,event_id):
    user,match=owned(request,db,match_id)
    row=saved_reviews(db,match).get(event_id)
    if row is None: raise HTTPException(404,"Saved verified spatial review required")
    return user,match,row

@router.get("/matches/{match_id}/spatial/{event_id}/sandbox",response_class=HTMLResponse)
def sandbox_page(match_id:int,event_id:int,request:Request,db:Session=Depends(get_db)):
    user,match,row=sandbox_baseline(request,db,match_id,event_id)
    return templates.TemplateResponse(request,"spatial_sandbox.html",dict(request=request,user=user,app_name="AquaMetric",
        match=match,event_id=event_id,baseline=row))

@router.post("/matches/{match_id}/spatial/{event_id}/sandbox")
async def sandbox_calculate(match_id:int,event_id:int,request:Request,db:Session=Depends(get_db)):
    from starlette.concurrency import run_in_threadpool
    from services.spatial_sandbox import sandbox
    _,_,row=sandbox_baseline(request,db,match_id,event_id)
    body=bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk)>32768: raise HTTPException(413,"Scenario too large")
        body.extend(chunk)
    try:
        edits=json.loads(body)
        if not isinstance(edits,dict): raise ValueError("Invalid scenario")
        trials=160 if edits.get("refine") is True else 32
        result=await run_in_threadpool(sandbox,row["observations"],edits,trials)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as exc:
        raise HTTPException(422,"Invalid scenario: "+str(exc)[:200]) from exc
    return JSONResponse(result,headers={"Cache-Control":"private, no-store"})


@router.post("/matches/{match_id}/spatial/{event_id}/sandbox/search")
async def sandbox_search(match_id:int,event_id:int,request:Request,db:Session=Depends(get_db)):
    from starlette.concurrency import run_in_threadpool
    from services.spatial_scenario_search import search_scenarios
    _,_,row=sandbox_baseline(request,db,match_id,event_id)
    body=bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk)>32768: raise HTTPException(413,"Scenario too large")
        body.extend(chunk)
    try:
        edits=json.loads(body)
        result=await run_in_threadpool(search_scenarios,row["observations"],edits)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as exc:
        raise HTTPException(422,"Invalid search: "+str(exc)[:200]) from exc
    return JSONResponse(result,headers={"Cache-Control":"private, no-store"})


def report_snapshot(db,match):
    sources=event_sources(db,match)
    total=sum(e.event_type in KINDS for e in verified_events(match.events))
    return {"status":"available" if sources else "no_bound_actions","eligible_count":len(sources),
            "unbound_count":total-len(sources),"reviews":saved_reviews(db,match),
            "scope":"segment_local_manual_geometry_not_sport_probability"}
