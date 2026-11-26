"""Bounded, isolated no-password AquaMetric Ultimate guest workspace.

The guest session is a real user_id (so every existing ownership check still
applies), but an explicit web_demo flag prohibits costly remote inference and
R2/S3 uploads. No raw provider credentials are exposed to the browser.
"""
from __future__ import annotations

import os
from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Match, User

MAX_GUEST_MATCHES = 3
MAX_GUEST_VIDEO_BYTES = 30 * 1024 * 1024
MAX_GUEST_PARTS = 4


def guest_session(request: Request) -> bool:
    return request.session.get("web_demo") is True


def full_guest_enabled():
    return os.getenv("AQUAMETRIC_GUEST_FULL", "0") == "1"

def full_guest(request):
    return guest_session(request) and full_guest_enabled()

def guest_match_limit():
    return max(0, int(os.getenv("AQUAMETRIC_GUEST_MATCH_LIMIT", "0"))) if full_guest_enabled() else MAX_GUEST_MATCHES

def guest_local_mb():
    return max(30,min(1024,int(os.getenv("AQUAMETRIC_GUEST_UPLOAD_MB","250")))) if full_guest_enabled() else 30

def enforce_new_match_limit(request: Request, db: Session, user: User) -> None:
    if not guest_session(request):
        return
    limit = guest_match_limit()
    if not limit:
        return
    count = db.scalar(select(func.count(Match.id)).where(Match.owner_id == user.id)) or 0
    if count >= limit:
        raise HTTPException(
            429,
            f"Le mode invité permet {limit} matchs maximum par session.",
        )


def upload_byte_limit(request: Request, regular_limit: int) -> int:
    return min(int(regular_limit), guest_local_mb()*1024*1024) if guest_session(request) else int(regular_limit)


def prohibit_paid_analysis(request: Request) -> None:
    if guest_session(request):
        raise HTTPException(
            403,
            "L’analyse IA payante est désactivée pour les invités. Utilise le lecteur et le marquage manuel des actions.",
        )
