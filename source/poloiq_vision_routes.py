"""Readiness and one-frame candidate inference from a separately deployed PoloIQ model."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from db import get_db
from models import Match, User
from services.poloiq_vision import MAX_FRAME_BYTES, infer_one_frame, readiness

router=APIRouter(tags=["PoloIQ object detection"])

@router.get("/api/poloiq/readiness")
def poloiq_readiness():
    return readiness()

@router.post("/api/matches/{match_id}/poloiq/frame")
async def poloiq_one_image(
    match_id:int, request:Request,
    image:UploadFile=File(...), db:Session=Depends(get_db),
):
    user_id=request.session.get("user_id")
    user=db.get(User,user_id) if user_id else None
    match=db.get(Match,match_id) if user else None
    if not user or not match or match.owner_id!=user.id:
        raise HTTPException(404,"Match introuvable.")
    if request.session.get("web_demo"):
        raise HTTPException(403,"Inférence IA désactivée pour les comptes de démonstration.")
    if image.content_type not in {"image/jpeg","image/png","image/webp"}:
        raise HTTPException(415,"Envoyer une image JPEG, PNG ou WebP.")
    data=await image.read(MAX_FRAME_BYTES+1)
    if len(data)>MAX_FRAME_BYTES:
        raise HTTPException(413,"Image supérieure à 6 Mo.")
    return infer_one_frame(data)
