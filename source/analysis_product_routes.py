from __future__ import annotations

import os
import re
import secrets
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_db
from models import Club, Match, Team, User
from services.analysis_product import (
    analysis_snapshot,
    build_analysis_zip,
    build_exact_evidence_pack,
    run_product_analysis,
)
from services.analysis_research_context import build_research_context, append_research_to_zip
from services.complete_analysis_runner import run_complete_analysis
from services.deep_analysis_sequences import (
    append_sequence_manifest,
    materialize_deep_sequence_pack,
    sequence_gallery,
    sequence_summary,
)
from services.reference_match_rosters import roster_payload
from services.team_scoring_patterns import build_team_scoring_patterns, append_scoring_patterns_to_zip
from services.rapid_match_analysis import RapidAnalysisError, run_rapid_analysis
from services.video import is_http_url, youtube_embed
from analysis_library_product_routes import router as analysis_library_product_router

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", BASE_DIR / "evidence"))
MAX_BROWSER_CAPTURE_MB = int(os.getenv("MAX_BROWSER_CAPTURE_MB", "1200"))
MAX_BROWSER_CAPTURE_BYTES = MAX_BROWSER_CAPTURE_MB * 1024 * 1024
CAPTURE_SESSION_ROOT = UPLOAD_DIR / ".browser_capture_sessions"
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()
router.include_router(analysis_library_product_router)


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


def _url_team(db: Session, user: User, team_name: str, competition: str) -> Team:
    name = (team_name or "").strip()[:160]
    if not name:
        raise HTTPException(status_code=400, detail="Team is required.")
    team = db.scalar(select(Team).where(Team.owner_id == user.id, func.lower(Team.name) == name.lower()))
    if team:
        return team
    club = db.scalar(select(Club).where(Club.owner_id == user.id, func.lower(Club.name) == name.lower()))
    if not club:
        club = Club(name=name, country="Analysis", division=(competition or "Video analysis")[:120], category="Women", owner_id=user.id)
        db.add(club)
        db.flush()
    team = Team(name=name, club_id=club.id, owner_id=user.id, category="Women")
    db.add(team)
    db.flush()
    return team


def _template_side(report: dict) -> dict:
    view = dict(report)
    view["phases"] = {"rows": list(report.get("phases", []) or [])}
    possessions = dict(report.get("possessions", {}) or {})
    if not possessions.get("available"):
        possessions["reason"] = possessions.get("note") or "Les identifiants de possession manquent encore."
    view["possessions"] = possessions
    return view


def _zip_root(match: Match) -> str:
    def slug(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("_")
        return value[:80] or "match"
    return f"AquaMetric_{slug(match.team.name)}_vs_{slug(match.opponent)}_{match.id}"


def _is_owned_upload(match: Match) -> bool:
    return match.video_source == "upload" and bool(match.video_path)


def _run_reference_only(db: Session, match: Match):
    """Build a third-party URL dossier when the user has not supplied pixels yet."""
    result = run_product_analysis(db, match, UPLOAD_DIR, EVIDENCE_DIR, include_audio=False)
    materialize_deep_sequence_pack(
        db,
        match,
        UPLOAD_DIR,
        EVIDENCE_DIR,
        max_targets=72,
        max_clips=0,
        max_image_targets=0,
    )
    match.status = "url_reference_ready"
    db.commit()
    return result


def _parse_time_token(value: str | None) -> float:
    raw = (value or "").strip().lower()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw.rstrip("s")))
    except ValueError:
        pass
    total = 0.0
    matched = False
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)(h|m|s)", raw):
        matched = True
        scale = {"h": 3600.0, "m": 60.0, "s": 1.0}[unit]
        total += float(number) * scale
    return max(0.0, total) if matched else 0.0


def _source_start_second(url: str | None) -> float:
    try:
        parsed = urlparse((url or "").strip())
        query = parse_qs(parsed.query)
        for key in ("t", "start"):
            values = query.get(key) or []
            if values:
                return _parse_time_token(values[0])
        fragment = parse_qs(parsed.fragment)
        for key in ("t", "start"):
            values = fragment.get(key) or []
            if values:
                return _parse_time_token(values[0])
    except Exception:
        return 0.0
    return 0.0


def _safe_session_id(value: str) -> str:
    token = (value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise HTTPException(status_code=400, detail="Invalid capture session.")
    return token


def _capture_session_dir(user: User, match: Match, session_id: str) -> Path:
    token = _safe_session_id(session_id)
    return CAPTURE_SESSION_ROOT / f"u{int(user.id)}_m{int(match.id)}_{token}"


def _write_capture_chunk(upload: UploadFile, target: Path, *, current_size: int) -> int:
    if upload.content_type and not upload.content_type.startswith(("video/", "application/octet-stream")):
        raise HTTPException(status_code=400, detail="The shared-tab capture is not recognized as video data.")
    written = 0
    with target.open("ab") as out:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if current_size + written > MAX_BROWSER_CAPTURE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Browser capture exceeds the configured {MAX_BROWSER_CAPTURE_MB} MB limit.",
                )
            out.write(chunk)
    return written


@router.post("/analysis/url/create")
def create_real_url_analysis(
    request: Request,
    team_name: str = Form(""),
    opponent: str = Form(...),
    competition: str = Form(""),
    match_date: str = Form(""),
    video_url: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    video_url = (video_url or "").strip()
    if not video_url or not is_http_url(video_url):
        raise HTTPException(status_code=400, detail="A valid http/https video URL is required.")
    opponent = (opponent or "").strip()[:160]
    if not opponent:
        raise HTTPException(status_code=400, detail="Opponent is required.")
    team = _url_team(db, user, team_name, competition)
    match = Match(
        owner_id=user.id,
        team_id=team.id,
        opponent=opponent,
        competition=(competition or "")[:160],
        match_date=(match_date or "")[:32],
        video_source="youtube" if youtube_embed(video_url) else "url",
        video_url=video_url,
        video_path="",
        status="url_capture_required",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return RedirectResponse(f"/matches/{match.id}/analysis/browser-capture", status_code=303)


@router.post("/matches/{match_id}/analysis/start")
def start_real_analysis(
    match_id: int,
    request: Request,
    include_audio: str = Form("1"),
    db: Session = Depends(get_db),
):
    _, match = _owned_match(match_id, request, db)
    if _is_owned_upload(match):
        try:
            run_complete_analysis(
                db,
                match,
                UPLOAD_DIR,
                EVIDENCE_DIR,
                include_audio=include_audio.lower() in {"1", "true", "on", "yes"},
            )
            materialize_deep_sequence_pack(
                db,
                match,
                UPLOAD_DIR,
                EVIDENCE_DIR,
                max_targets=72,
                max_clips=48,
                max_image_targets=72,
                triple_frames=48,
            )
        except RapidAnalysisError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return RedirectResponse(f"/matches/{match_id}/analysis/result", status_code=303)
    if match.video_url:
        match.status = "url_capture_required"
        db.commit()
        return RedirectResponse(f"/matches/{match_id}/analysis/browser-capture", status_code=303)
    raise HTTPException(status_code=400, detail="Aucune vidéo exploitable n'est associée à ce match.")


@router.post("/matches/{match_id}/url-analysis/start")
def start_real_url_analysis(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    if not match.video_url:
        raise HTTPException(status_code=400, detail="This analysis mode requires a video URL.")
    match.status = "url_capture_required"
    db.commit()
    return RedirectResponse(f"/matches/{match_id}/analysis/browser-capture", status_code=303)


@router.get("/matches/{match_id}/analysis/browser-capture", response_class=HTMLResponse)
def browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    if not match.video_url:
        raise HTTPException(status_code=400, detail="This capture mode requires a video URL.")
    return TEMPLATES.TemplateResponse(
        request,
        "browser_capture.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "match": match,
            "source_start_second": _source_start_second(match.video_url),
            "roster": roster_payload(match.video_url),
        },
    )


@router.post("/matches/{match_id}/analysis/browser-capture/session")
def create_browser_capture_session(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    if not match.video_url:
        raise HTTPException(status_code=400, detail="This capture mode requires a video URL.")
    session_id = secrets.token_hex(16)
    root = _capture_session_dir(user, match, session_id)
    root.mkdir(parents=True, exist_ok=False)
    (root / "next_index.txt").write_text("0", encoding="utf-8")
    match.status = "browser_capture_running"
    db.commit()
    return JSONResponse({"ok": True, "session_id": session_id})


@router.post("/matches/{match_id}/analysis/browser-capture/chunk")
def append_browser_capture_chunk(
    match_id: int,
    request: Request,
    session_id: str = Form(...),
    index: int = Form(...),
    chunk: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    state_file = root / "next_index.txt"
    if not root.is_dir() or not state_file.exists():
        raise HTTPException(status_code=404, detail="Capture session expired or not found.")
    try:
        expected = int(state_file.read_text(encoding="utf-8").strip() or "0")
    except ValueError:
        raise HTTPException(status_code=409, detail="Capture session state is invalid.")
    if int(index) != expected:
        raise HTTPException(status_code=409, detail=f"Capture chunk out of order: expected {expected}, got {index}.")
    target = root / "capture.webm"
    current_size = target.stat().st_size if target.exists() else 0
    try:
        written = _write_capture_chunk(chunk, target, current_size=current_size)
    finally:
        chunk.file.close()
    if written <= 0:
        raise HTTPException(status_code=400, detail="Empty capture chunk.")
    state_file.write_text(str(expected + 1), encoding="utf-8")
    return JSONResponse({"ok": True, "next_index": expected + 1, "bytes": current_size + written})


@router.post("/matches/{match_id}/analysis/browser-capture/finish")
def finish_browser_capture(
    match_id: int,
    request: Request,
    session_id: str = Form(...),
    source_start_second: float = Form(0.0),
    db: Session = Depends(get_db),
):
    user, match = _owned_match(match_id, request, db)
    root = _capture_session_dir(user, match, session_id)
    source_path = root / "capture.webm"
    if not root.is_dir() or not source_path.exists():
        raise HTTPException(status_code=404, detail="Capture session expired or not found.")
    if source_path.stat().st_size < 64 * 1024:
        shutil.rmtree(root, ignore_errors=True)
        match.status = "browser_capture_failed"
        db.commit()
        raise HTTPException(status_code=422, detail="Capture too short: no usable video frames were received.")

    derived_dir = root / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = run_rapid_analysis(
            db,
            match,
            source_path,
            derived_dir,
            include_audio=False,
            visual_samples=300,
            ocr_samples=96,
            source_kind="browser_capture",
            persist_visual_artifacts=False,
            time_offset_seconds=max(0.0, float(source_start_second or 0.0)),
        )
        materialize_deep_sequence_pack(
            db,
            match,
            UPLOAD_DIR,
            EVIDENCE_DIR,
            max_targets=72,
            max_clips=0,
            max_image_targets=0,
        )
        match.status = "browser_capture_analyzed"
        db.commit()
        summary = result.get("summary", {}) or {}
        return JSONResponse({
            "ok": True,
            "visual_samples": int(summary.get("visual_samples") or 0),
            "scoreboard_observations": int(summary.get("scoreboard_observations") or 0),
            "candidates": len(result.get("candidates", []) or []),
            "source_time_offset_seconds": float(summary.get("source_time_offset_seconds") or 0.0),
            "redirect": f"/matches/{match.id}/analysis/result",
        })
    except RapidAnalysisError as exc:
        match.status = "browser_capture_failed"
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        shutil.rmtree(root, ignore_errors=True)


@router.get("/matches/{match_id}/analysis/result", response_class=HTMLResponse)
def analysis_result(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    snapshot = analysis_snapshot(db, match)
    team_report = _template_side(snapshot["ultimate"]["team"])
    opponent_report = _template_side(snapshot["ultimate"]["opponent"])
    sequences = sequence_gallery(db, match, max_total=72)
    summary = sequence_summary(sequences)
    research = build_research_context(db, match)
    scoring_patterns = build_team_scoring_patterns(db, match)
    source_embed = youtube_embed(match.video_url) if match.video_url else ""
    if not source_embed and snapshot.get("reference") and snapshot["reference"].get("video_url"):
        source_embed = youtube_embed(snapshot["reference"]["video_url"]) or ""
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
            "team_report": team_report,
            "opponent_report": opponent_report,
            "automatic": snapshot["automatic"],
            "vision": snapshot["vision"],
            "reference": snapshot["reference"],
            "artifacts": snapshot["artifacts"],
            "verified_events": snapshot["verified_events"],
            "sequences": sequences,
            "sequence_summary": summary,
            "source_embed": source_embed,
            "research": research,
            "scoring_patterns": scoring_patterns,
            "match_roster": roster_payload(match.video_url),
        },
    )


@router.post("/matches/{match_id}/analysis/evidence-pack")
def regenerate_exact_evidence(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    build_exact_evidence_pack(db, match, UPLOAD_DIR, EVIDENCE_DIR, max_verified_events=32, max_candidates=24)
    if _is_owned_upload(match):
        materialize_deep_sequence_pack(
            db,
            match,
            UPLOAD_DIR,
            EVIDENCE_DIR,
            max_targets=72,
            max_clips=48,
            max_image_targets=72,
            triple_frames=48,
        )
    else:
        materialize_deep_sequence_pack(
            db,
            match,
            UPLOAD_DIR,
            EVIDENCE_DIR,
            max_targets=72,
            max_clips=0,
            max_image_targets=0,
        )
    return RedirectResponse(f"/matches/{match_id}/analysis/result#sequences", status_code=303)


@router.get("/matches/{match_id}/analysis/export.zip")
def export_complete_analysis(match_id: int, request: Request, db: Session = Depends(get_db)):
    _, match = _owned_match(match_id, request, db)
    if _is_owned_upload(match):
        materialize_deep_sequence_pack(
            db,
            match,
            UPLOAD_DIR,
            EVIDENCE_DIR,
            max_targets=72, max_clips=72,
            max_image_targets=72, triple_frames=48,
        )
    else:
        materialize_deep_sequence_pack(
            db,
            match,
            UPLOAD_DIR,
            EVIDENCE_DIR,
            max_targets=72,
            max_clips=0,
            max_image_targets=0,
        )
    archive = build_analysis_zip(db, match, EVIDENCE_DIR)
    root = _zip_root(match)
    cards = sequence_gallery(db, match, max_total=72)
    append_sequence_manifest(archive, cards, root)
    append_research_to_zip(archive, build_research_context(db, match), root)
    append_scoring_patterns_to_zip(archive, build_team_scoring_patterns(db, match), root)
    filename = f"AquaMetric_match_{match.id}_analysis.zip"
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
