from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from db import get_db
from models import User
from services.premium_national_intel import build_national_dashboard

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


@router.get("/national-teams", response_class=HTMLResponse)
def premium_national_teams(request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    dashboard = build_national_dashboard(db)
    return TEMPLATES.TemplateResponse(
        request,
        "premium_national_teams.html",
        {"request": request, "user": user, "app_name": "AquaMetric", "dashboard": dashboard},
    )
