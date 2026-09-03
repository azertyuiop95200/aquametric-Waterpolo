from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db import get_db
from models import Match, User
from services.analysis_product import (
    analysis_snapshot,
    build_analysis_zip,
    build_exact_evidence_pack,
    run_product_analysis,
)
from services.rapid_match_analysis import RapidAnalysisError

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", BASE_DIR / "evidence"))
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _owned_match(match_id: int, request: Request, db: Session):
    user = _user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Match not found")
    return user, match


@router.post("/matches/{match_id}/analysis/start")
def start_real_analysis(
    match_id: int,
    request: Request,
    include_audio: str = Form(""),
    db: Session = Depends(get_db),
):
    """Run the actual available analysis pipeline, never the historical placeholder."""
    _, match = _owned_match(match_id, request, db)
    try:
        run_product_analysis(
            db,
            match,
            UPLOAD_DIR,
            EVIDENCE_DIR,
            include_audio=include_audio.lower() in {"1", "true", "on", "yes"},
        )
    except RapidAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RedirectResponse(f"/matches/{match_id}/analysis/result", status_code=303)


@router.get("/matches/{match_id}/analysis/result", response_class=HTMLResponse)
def analysis_result(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    snapshot = analysis_snapshot(db, match)
    return TEMPLATES.TemplateResponse(
        request,
        "analysis_result.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "match": match,
            "snapshot": snapshot,
            "ultimate": snapshot["ultimate"],
            "team_report": snapshot["ultimate"]["team"],
            "opponent_report": snapshot["ultimate"]["opponent"],
            "automatic": snapshot["automatic"],
            "vision": snapshot["vision"],
            "reference": snapshot["reference"],
            "artifacts": snapshot["artifacts"],
            "verified_events": snapshot["verified_events"],
        },
    )


@router.post("/matches/{match_id}/analysis/evidence-pack")
def regenerate_exact_evidence(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    build_exact_evidence_pack(db, match, UPLOAD_DIR, EVIDENCE_DIR)
    return RedirectResponse(f"/matches/{match_id}/analysis/result#evidence", status_code=303)


@router.get("/matches/{match_id}/analysis/export.zip")
def export_complete_analysis(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    archive = build_analysis_zip(db, match, EVIDENCE_DIR)
    filename = f"AquaMetric_match_{match.id}_analysis.zip"
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
