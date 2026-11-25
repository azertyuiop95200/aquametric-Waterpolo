"""Owner-scoped, resumable 5 GiB direct-to-R2/S3 video ingestion.

Only small JSON messages cross Render. An object is attached to a match only
after all contiguous S3 parts and the final ContentLength are independently
verified on the provider. The actual sports analysis remains a separate stage.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from math import ceil
from pathlib import Path
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_db
from models import LargeVideoUpload, Match, User
from services import large_video_storage as storage

router = APIRouter(tags=["Large video upload"])


class StartUpload(BaseModel):
    filename: str
    size_bytes: int = Field(gt=0)
    team_name: str = Field(min_length=1, max_length=160)
    opponent: str = Field(min_length=1, max_length=160)
    competition: str = Field(default="", max_length=160)
    category: str = Field(default="Women", max_length=30)
    match_date: str = Field(default="", max_length=32)
    match_id: int | None = Field(default=None, ge=1)
    period: int = Field(default=1, ge=1, le=8)
    segment_label: str = Field(default="", max_length=100)


class PartNumber(BaseModel):
    number: int = Field(ge=1, le=10000)


def _owner(request: Request, db: Session) -> User:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(401, "Connecte-toi pour envoyer une vidéo.")
    if request.session.get("web_demo"):
        raise HTTPException(403, "Les comptes de démonstration ne peuvent pas stocker plusieurs Go. Utilise un compte personnel.")
    return user


def _owned_upload(upload_id: str, request: Request, db: Session) -> LargeVideoUpload:
    user = _owner(request, db)
    row = db.get(LargeVideoUpload, upload_id)
    if row is None or row.owner_id != user.id:
        raise HTTPException(404, "Transfert introuvable.")
    return row


def _uploading(row: LargeVideoUpload):
    if row.status != "uploading":
        raise HTTPException(409, "Ce transfert a déjà été terminé ou annulé.")
    if row.created_at and datetime.now(timezone.utc) - row.created_at.replace(tzinfo=timezone.utc) > timedelta(days=7):
        raise HTTPException(410, "Ce transfert a expiré. Recommence un nouvel envoi.")


def _safe_meta(value: StartUpload) -> dict:
    team = value.team_name.strip()
    opponent = value.opponent.strip()
    if not team or not opponent:
        raise HTTPException(400, "Les deux équipes sont obligatoires.")
    if value.category not in {"Women", "Men", "Mixed/Other"}:
        raise HTTPException(400, "Catégorie non reconnue.")
    return {
        "team_name": team, "opponent": opponent,
        "competition": value.competition.strip(), "category": value.category,
        "match_date": value.match_date.strip(),
        "target_match_id": value.match_id,
        "period": value.period,
        "segment_label": value.segment_label.strip(),
    }


@router.get("/api/large-upload/capabilities")
def large_upload_capabilities():
    return storage.capabilities()


@router.post("/api/large-upload/start")
def start_large_upload(value: StartUpload, request: Request, db: Session = Depends(get_db)):
    user = _owner(request, db)
    name, mime_type = storage.allowed_video(value.filename)
    if value.match_id is not None:
        target=db.get(Match,value.match_id)
        if target is None or target.owner_id != user.id:
            raise HTTPException(404, "Match cible introuvable.")
        if target.team.name != value.team_name.strip() or target.opponent != value.opponent.strip():
            raise HTTPException(400, "Les équipes fournies ne correspondent pas au match cible.")
    if value.size_bytes > storage.MAX_BYTES:
        raise HTTPException(413, f"Fichier trop volumineux : limite {storage.MAX_GB} Go.")
    api = storage.client()
    metadata = _safe_meta(value)

    total_reserved = db.scalar(select(func.coalesce(func.sum(LargeVideoUpload.total_bytes), 0)).where(
        LargeVideoUpload.owner_id == user.id,
        LargeVideoUpload.status.in_(("uploading", "complete")),
    )) or 0
    if total_reserved + value.size_bytes > storage.OWNER_QUOTA_BYTES:
        raise HTTPException(413, "Quota personnel de stockage atteint. Annule un transfert incomplet ou contacte l'administrateur.")
    active = db.scalar(select(func.count()).select_from(LargeVideoUpload).where(
        LargeVideoUpload.owner_id == user.id,
        LargeVideoUpload.status == "uploading",
    )) or 0
    if active >= 2:
        raise HTTPException(429, "Deux transferts sont déjà ouverts. Reprends-en un ou annule-le.")

    session = str(uuid.uuid4())
    suffix = Path(name).suffix.lower()
    key_prefix = "videos"
    key = f"{key_prefix}/user-{user.id}/{session}{suffix}"
    try:
        created = api.create_multipart_upload(
            Bucket=storage.bucket(), Key=key, ContentType=mime_type,
            Metadata={"aquametric_owner":str(user.id), "aquametric_upload":session},
        )
    except Exception:
        raise HTTPException(502, "Impossible de démarrer l'envoi vers le stockage vidéo.") from None

    row = LargeVideoUpload(
        id=session, owner_id=user.id, object_key=key,
        upload_id=created["UploadId"], filename=name, mime_type=mime_type,
        total_bytes=value.size_bytes, part_bytes=storage.PART_BYTES,
        metadata_json=json.dumps(metadata, ensure_ascii=False), status="uploading",
    )
    try:
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        try:
            api.abort_multipart_upload(Bucket=storage.bucket(), Key=key, UploadId=created["UploadId"])
        except Exception:
            pass
        raise HTTPException(500, "Impossible d'enregistrer ce transfert.") from None
    return {
        "upload_id": row.id,
        "part_bytes":row.part_bytes,
        "total_parts":ceil(value.size_bytes / row.part_bytes),
        "total_bytes":row.total_bytes,
        "filename":row.filename,
    }


@router.get("/api/large-upload/{upload_id}/status")
def large_upload_status(upload_id: str, request: Request, db: Session = Depends(get_db)):
    row = _owned_upload(upload_id, request, db)
    if row.status == "complete":
        return {"status":"complete", "match_url":f"/matches/{row.match_id}/analysis/result",
                "completed_parts":[], "uploaded_bytes":row.total_bytes,
                "total_bytes":row.total_bytes}
    _uploading(row)
    try:
        pieces = storage.list_uploaded_parts(storage.client(), key=row.object_key, upload_id=row.upload_id)
    except Exception:
        raise HTTPException(502, "Impossible de récupérer l'avancement du transfert.") from None
    return {"status": row.status, "total_bytes":row.total_bytes, "part_bytes":row.part_bytes,
            "completed_parts":[p["PartNumber"] for p in pieces],
            "uploaded_bytes":sum(p["Size"] for p in pieces)}


@router.post("/api/large-upload/{upload_id}/sign")
def sign_large_part(upload_id: str, payload: PartNumber, request: Request, db: Session = Depends(get_db)):
    row = _owned_upload(upload_id, request, db)
    _uploading(row)
    if payload.number > ceil(row.total_bytes / row.part_bytes):
        raise HTTPException(400, "Numéro de morceau invalide.")
    try:
        url = storage.client().generate_presigned_url(
            "upload_part",
            Params={"Bucket":storage.bucket(),"Key":row.object_key,
                    "UploadId":row.upload_id,"PartNumber":payload.number},
            ExpiresIn=900,
        )
    except Exception:
        raise HTTPException(502, "Impossible de préparer ce morceau.") from None
    return {"url":url, "part_number":payload.number, "expires_seconds":900}


def _link_finished_object(row: LargeVideoUpload, db: Session) -> str:
    from analysis_input_routes_v2 import _free_team
    metadata = json.loads(row.metadata_json)
    user = db.get(User, row.owner_id)
    if not user:
        raise HTTPException(404, "Compte de transfert introuvable.")
    target_match_id=metadata.get("target_match_id")
    if target_match_id is not None:
        match=db.get(Match,int(target_match_id))
        if match is None or match.owner_id != row.owner_id:
            raise HTTPException(404, "Match cible introuvable.")
        from match_video_segments_routes import append_segment
        append_segment(db,match,period=int(metadata.get("period",1)),
            label=metadata.get("segment_label",""),source_type="cloud",
            video_path=row.object_key)
    else:
        team = _free_team(db, user, metadata["team_name"], metadata["competition"], metadata["category"])
        match = Match(
            owner_id=row.owner_id, team_id=team.id,
            opponent=metadata["opponent"], competition=metadata["competition"],
            match_date=metadata["match_date"], video_source="cloud",
            video_path=row.object_key, video_url="", status="cloud_video_received",
        )
        db.add(match)
        db.flush()
    row.status = "complete"
    row.match_id = match.id
    db.commit()
    return f"/matches/{match.id}/analysis/result"


@router.post("/api/large-upload/{upload_id}/complete")
def complete_large_upload(upload_id: str, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    row = _owned_upload(upload_id, request, db)
    if row.status == "complete" and row.match_id:
        return {"status":"complete","match_url":f"/matches/{row.match_id}/analysis/result"}
    _uploading(row)
    api = storage.client()

    # A storage commit can succeed while a database connection fails. Retry by
    # checking the completed object size before trying to finish the upload again.
    done = False
    try:
        head = api.head_object(Bucket=storage.bucket(), Key=row.object_key)
        done = int(head["ContentLength"]) == row.total_bytes
        if not done:
            raise HTTPException(409, "Le fichier distant ne correspond pas à la taille déclarée.")
    except HTTPException:
        raise
    except Exception as exc:
        if not storage.is_missing_object_error(exc):
            raise HTTPException(502, "Impossible de vérifier l'objet distant.") from None

    if not done:
        try:
            parts = storage.list_uploaded_parts(api, key=row.object_key, upload_id=row.upload_id)
        except Exception:
            raise HTTPException(502, "Impossible de vérifier les morceaux reçus.") from None
        expected_count = ceil(row.total_bytes / row.part_bytes)
        if len(parts) != expected_count:
            raise HTTPException(409, f"Transfert incomplet : {len(parts)}/{expected_count} morceaux reçus.")
        for index, part in enumerate(parts):
            expected_number = index + 1
            expected_size = min(row.part_bytes, row.total_bytes - index*row.part_bytes)
            if part["PartNumber"] != expected_number or part["Size"] != expected_size:
                raise HTTPException(409, "Morceaux manquants, désordonnés ou de taille incorrecte.")
        try:
            api.complete_multipart_upload(
                Bucket=storage.bucket(), Key=row.object_key, UploadId=row.upload_id,
                MultipartUpload={"Parts":[{"PartNumber":p["PartNumber"],"ETag":p["ETag"]} for p in parts]},
            )
            head = api.head_object(Bucket=storage.bucket(), Key=row.object_key)
        except Exception:
            raise HTTPException(502, "Le stockage n'a pas confirmé l'assemblage de la vidéo.") from None
        if int(head.get("ContentLength", -1)) != row.total_bytes:
            raise HTTPException(502, "La taille finale ne correspond pas au fichier sélectionné.")

    match_url = _link_finished_object(row, db)
    # Only after the provider confirms every part and final size do we begin
    # AI inference. The worker streams small seekable ranges of this private
    # object; it never downloads the 5 GiB body into the Render web process.
    from services.video_action_provider import provider_configuration
    if provider_configuration()["configured"]:
        from services.cloud_video_actions import run_cloud_video_actions
        background_tasks.add_task(run_cloud_video_actions,row.match_id,row.object_key)
    return {"status":"complete", "match_url":match_url, "total_bytes":row.total_bytes,
            "analysis_queued":provider_configuration()["configured"]}


@router.delete("/api/large-upload/{upload_id}")
def cancel_large_upload(upload_id: str, request: Request, db: Session = Depends(get_db)):
    row = _owned_upload(upload_id, request, db)
    _uploading(row)
    try:
        storage.client().abort_multipart_upload(
            Bucket=storage.bucket(),Key=row.object_key,UploadId=row.upload_id)
    except Exception:
        raise HTTPException(502, "Annulation non confirmée par le stockage.") from None
    row.status="aborted"
    db.commit()
    return {"status":"aborted"}


def cloud_video_redirect(match: Match) -> RedirectResponse:
    if match.video_source != "cloud" or not match.video_path:
        raise HTTPException(404)
    try:
        destination=storage.signed_video_url(match.video_path)
    except Exception:
        raise HTTPException(503, "La lecture du fichier cloud n'est pas disponible.") from None
    return RedirectResponse(destination, status_code=307)
