"""URL analysis input V3: full-match scope by default.

A YouTube ``t=``/``start=`` marker is only a viewing cursor. Automatic analysis
must scan the whole source from 0:00 so early goals are never dropped. Trimming
is allowed only when the user explicitly chooses manual scope.
"""
from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db import get_db
from models import Match
from analysis_product_routes import _user
from analysis_input_routes_v2 import _free_team
from services.video import is_http_url, youtube_embed


def _scope_query(scope_mode: str, scope_start_second: float, scope_end_second: float) -> str:
    mode = (scope_mode or "auto").strip().lower()
    if mode not in {"auto", "single", "manual", "multiple"}:
        mode = "auto"

    if mode == "manual":
        start = max(0.0, float(scope_start_second or 0.0))
        end = max(0.0, float(scope_end_second or 0.0))
        if end and end <= start:
            end = 0.0
    else:
        # Auto/single/multiple always see the complete video. URL timestamps are
        # never interpreted as proof of a match boundary.
        start = 0.0
        end = 0.0

    return urlencode({"scope_mode": mode, "scope_start": f"{start:.3f}", "scope_end": f"{end:.3f}"})


def create_flexible_url_analysis(
    request: Request,
    team_name: str = Form(""),
    opponent: str = Form(...),
    category: str = Form("Women"),
    competition: str = Form(""),
    match_date: str = Form(""),
    video_url: str = Form(...),
    input_device: str = Form("desktop"),
    scope_mode: str = Form("auto"),
    scope_start_second: float = Form(0.0),
    scope_end_second: float = Form(0.0),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    url = (video_url or "").strip()
    if not url or not is_http_url(url):
        raise HTTPException(status_code=400, detail="Un lien vidéo http/https valide est obligatoire.")
    opponent = (opponent or "").strip()[:160]
    if not opponent:
        raise HTTPException(status_code=400, detail="Le nom de l'adversaire est obligatoire.")

    if input_device not in {"desktop", "phone"}:
        raise HTTPException(status_code=400, detail="Mode d’appareil invalide.")

    team = _free_team(db, user, team_name, competition, category)
    match = Match(
        owner_id=user.id,
        team_id=team.id,
        opponent=opponent,
        competition=(competition or "")[:160],
        match_date=(match_date or "")[:32],
        video_source="youtube" if youtube_embed(url) else "url",
        video_url=url,
        video_path="",
        status="source_link_saved" if input_device == "phone" else "url_capture_required",
    )
    db.add(match)
    db.commit()
    db.refresh(match)

    if input_device == "phone":
        return RedirectResponse(f"/matches/{match.id}/analysis/result", status_code=303)

    query = _scope_query(scope_mode, scope_start_second, scope_end_second)
    return RedirectResponse(f"/matches/{match.id}/analysis/browser-capture?{query}", status_code=303)
