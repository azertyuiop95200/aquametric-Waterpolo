"""Private, event-linked 3D review routes. No pixels or tracks are fabricated."""
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Column, Integer, Text, ForeignKey, select
from sqlalchemy.orm import Session
from db import Base, get_db
from models import Match, User, Event
from services.event_evidence import verified_events
from services.video import youtube_embed
from services.spatial_replay import review

router=APIRouter()
templates=Jinja2Templates(directory=Path(__file__).parent/"templates")
KINDS={"goal","shot_on_target","shot_off_target","shot_blocked","bad_pass","turnover","pass_complete","key_pass","assist"}

class SpatialReview(Base):
    __tablename__="spatial_reviews_v1"
    event_id=Column(Integer,ForeignKey("events.id",ondelete="CASCADE"),primary_key=True)
    owner_id=Column(Integer,nullable=False,index=True)
    match_id=Column(Integer,nullable=False,index=True)
    payload=Column(Text,nullable=False)

def owned(request,db,match_id):
    uid=request.session.get("user_id")
    user=db.get(User,uid) if uid else None
    if not user: raise HTTPException(401,"Login required")
    match=db.get(Match,match_id)
    if not match or match.owner_id!=user.id: raise HTTPException(404,"Match not found")
    return user,match

def eligible(match):
    return sorted((e for e in verified_events(match.events) if e.event_type in KINDS),key=lambda e:(e.second,e.id))

def saved_reviews(db,match):
    valid={e.id for e in eligible(match)}
    rows=db.scalars(select(SpatialReview).where(SpatialReview.match_id==match.id,SpatialReview.owner_id==match.owner_id)).all()
    result={}
    for row in rows:
        if row.event_id in valid:
            try: result[row.event_id]=json.loads(row.payload)
            except ValueError: continue
    return result

@router.get("/matches/{match_id}/spatial",response_class=HTMLResponse)
def spatial_page(match_id:int,request:Request,db:Session=Depends(get_db)):
    user,match=owned(request,db,match_id)
    events=[dict(id=e.id,second=e.second,kind=e.event_type,player=e.player.name if e.player else None) for e in eligible(match)]
    return templates.TemplateResponse(request,"spatial_review.html",dict(request=request,user=user,app_name="AquaMetric",
        match=match,events=events,reviews=saved_reviews(db,match),embed=youtube_embed(match.video_url)))

@router.post("/matches/{match_id}/spatial/{event_id}")
async def spatial_save(match_id:int,event_id:int,request:Request,db:Session=Depends(get_db)):
    user,match=owned(request,db,match_id)
    event=next((e for e in eligible(match) if e.id==event_id),None)
    if event is None: raise HTTPException(404,"Verified eligible event required")
    # Bound incoming payload even when the caller omits Content-Length.
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>32768: raise HTTPException(413,"Observation too large")
    try:
        data=json.loads(body)
        result=review(data)
        if not max(0,event.second-10)<=result["decision_second"]<=event.second:
            raise ValueError("Decision must be at or within 10 seconds before the event")
        payload=json.dumps(dict(observations=data,result=result),allow_nan=False)
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
    return JSONResponse({"match_id":match.id,"eligible_count":len(eligible(match)),"reviews":saved_reviews(db,match)},
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
