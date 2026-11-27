"""Bounded, isolated no-password AquaMetric Ultimate guest workspace.

The guest session is a real user_id (so every existing ownership check still
applies), but an explicit web_demo flag prohibits costly remote inference and
R2/S3 uploads. No raw provider credentials are exposed to the browser.
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Match, User

MAX_GUEST_MATCHES = 3
MAX_GUEST_VIDEO_BYTES = 30 * 1024 * 1024
MAX_GUEST_PARTS = 4


def guest_session(request: Request) -> bool:
    return request.session.get("web_demo") is True


def enforce_new_match_limit(request: Request, db: Session, user: User) -> None:
    if not guest_session(request):
        return
    count = db.scalar(select(func.count(Match.id)).where(Match.owner_id == user.id)) or 0
    if count >= MAX_GUEST_MATCHES:
        raise HTTPException(
            429,
            "Le mode invité permet 3 matchs maximum par session. Connecte-toi à un compte personnel pour continuer.",
        )


def upload_byte_limit(request: Request, regular_limit: int) -> int:
    return min(int(regular_limit), MAX_GUEST_VIDEO_BYTES) if guest_session(request) else int(regular_limit)


def prohibit_paid_analysis(request: Request) -> None:
    if guest_session(request):
        raise HTTPException(
            403,
            "L’analyse IA payante est désactivée pour les invités. Utilise le lecteur et le marquage manuel des actions.",
        )
