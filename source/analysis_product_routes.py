from __future__ import annotations

import os
import re
import secrets
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
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
    if request.session.get("web_demo") and request.method == "POST":
        # Guests can mark observed events and retrieve honest reports, not
        # start CPU-heavy capture, research, inference or media regeneration.
        blocked_paths = (
            "/analysis/browser-capture/", "/analysis/start",
            "/url-analysis/start", "/analysis/actions/start",
            "/analysis/youtube/direct", "/analysis/evidence-pack",
        )
        from services.guest_ultimate import full_guest
        if full_guest(request):
            blocked_paths = ("/analysis/actions/start", "/analysis/youtube/direct")
        if any(part in request.url.path for part in blocked_paths):
            raise HTTPException(403,"Ce traitement automatique n'est pas disponible en invité. Utilise le marquage manuel.")
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
    background_tasks: BackgroundTasks,
    include_audio: str = Form("1"),
    db: Session = Depends(get_db),
):
    _, match = _owned_match(match_id, request, db)
    if _is_owned_upload(match):
        from services.guest_ultimate import full_guest
        if full_guest(request):
            from services.guest_local_analysis import queue_guest_local
            queue_guest_local(db, match, background_tasks)
            return RedirectResponse(f"/matches/{match_id}/analysis/result", status_code=303)
        from models import AnalysisJob
        from video_action_routes import upload_analysis_background, workflow_active
        if not workflow_active(db, match.id):
            job = AnalysisJob(match_id=match.id, stage="video_workflow", status="queued", progress=0,
                              message="Analyse en attente : lecture du fichier vidéo.")
            db.add(job)
            db.commit()
            background_tasks.add_task(upload_analysis_background, match.id, job.id,
                                      include_audio.lower() in {"1", "true", "on", "yes"})
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
    from services.capture_chunks import append_capture_chunk
    result = append_capture_chunk(root, int(index), chunk, _write_capture_chunk)
    return JSONResponse(result)


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


# Explicit, owner-only calibration of a local recording; no hard-coded geometry
# from a different venue. One bounded calibration job per worker.
from threading import BoundedSemaphore
_METRIC_SLOT = BoundedSemaphore(1)

@router.post("/matches/{match_id}/analysis/metric-calibration")
def metric_calibration(match_id: int, request: Request, payload: dict, db: Session = Depends(get_db)):
    import json
    import math
    from models import AutonomousAnalysis
    from services.metric_field import build_map
    _, match = _owned_match(match_id, request, db)
    if not _is_owned_upload(match):
        raise HTTPException(400, "Calibration disponible pour un fichier vidéo local.")
    source = UPLOAD_DIR / Path(match.video_path).name
    if not source.is_file():
        raise HTTPException(404, "Vidéo locale absente.")
    auto = db.scalar(select(AutonomousAnalysis).where(AutonomousAnalysis.match_id == match.id)
                     .order_by(AutonomousAnalysis.id.desc()).limit(1))
    if not auto:
        raise HTTPException(409, "Lance d'abord la pré-analyse vidéo.")
    try:
        summary = json.loads(auto.summary_json or "{}")
        tracking = summary.get("player_candidate_tracking", {})
        anchors, polygon = payload["anchors"], payload["polygon"]
        width, length = float(payload["width"]), float(payload.get("length",25))
        reference = float(payload["reference_second"])
        if not math.isfinite(reference) or not 0<=reference<=28800:
            raise ValueError("Instant de référence invalide.")
        shots = payload.get("shots",[])
        if not isinstance(shots,list) or len(shots)>30 or not isinstance(polygon,list) or len(polygon)>16 or not isinstance(anchors,list) or len(anchors)!=5:
            raise ValueError("Nombre de repères invalide.")
        for shot in shots:
            if not isinstance(shot,dict) or not all(math.isfinite(float(shot[k])) for k in ("second","x","y")) or not 0<=float(shot["second"])<=28800:
                raise ValueError("Position de tir invalide.")
    except (ValueError,TypeError,KeyError):
        raise HTTPException(400,"Paramètres de calibration invalides.") from None
    if not _METRIC_SLOT.acquire(blocking=False):
        raise HTTPException(429,"Une calibration est déjà en cours sur le serveur.")
    try:
        result=build_map(source,tracking,anchors,polygon,width,length,reference,shots)
        result["calibration_provenance"]="manual_reviewed_anchors"
        from services.shot_context_review import source_key
        result["source_key"]=source_key(match.video_path)
        if not result["aligned_frames"]:
            raise HTTPException(422,"Aucun raccord caméra accepté. Revoir les repères du décor.")
        # Preserve existing candidates and confirmed events; metric positions
        # never become confirmed sporting events.
        db.refresh(auto)
        latest=json.loads(auto.summary_json or "{}")
        result["revision"]=secrets.token_hex(16)
        latest["metric_field_map"]=result
        # Track/shot indexes belong to one calibration only. Preserve event reviews.
        old_reviews=latest.get("identity_reviews",{})
        latest["identity_reviews"]={"tracks":{},"shots":{},"events":old_reviews.get("events",{})}
        auto.summary_json=json.dumps(latest,ensure_ascii=False)
        db.commit()
        return {"ok":True,"aligned_frames":result["aligned_frames"],"requested_frames":result["requested_frames"],"mapped_shots":len(result["shots"])}
    except HTTPException:
        raise
    except (ValueError,TypeError,KeyError):
        raise HTTPException(422,"Calibration impossible : vérifier les cinq repères et le décor fixe.") from None
    finally:
        _METRIC_SLOT.release()


@router.post("/matches/{match_id}/analysis/identity-review")
def save_identity_review(match_id:int,request:Request,payload:dict,db:Session=Depends(get_db)):
    import json
    from models import AutonomousAnalysis
    from services.identity_aggregation import validate_reviews
    _,match=_owned_match(match_id,request,db)
    auto=db.scalar(select(AutonomousAnalysis).where(AutonomousAnalysis.match_id==match.id).order_by(AutonomousAnalysis.id.desc()).limit(1))
    if not auto:raise HTTPException(409,"Lance une pré-analyse avant l'attribution.")
    # Serialize against calibration in this worker; reject obsolete form revisions.
    if not _METRIC_SLOT.acquire(blocking=False):raise HTTPException(429,"Un calcul est déjà en cours.")
    try:
        db.refresh(auto)
        summary=json.loads(auto.summary_json or "{}");metric=summary.get("metric_field_map",{})
        if payload.get("analysis_id")!=auto.id or payload.get("calibration_revision","")!=metric.get("revision",""):
            raise HTTPException(409,"La calibration a changé. Actualise le rapport.")
        tracks={str(t["id"]) for t in metric.get("tracks",[])}
        shots={str(i) for i,_ in enumerate(metric.get("shots",[]))}
        events={}
        for e in match.events:
            if str(e.confidence or "").upper() not in {"CONFIRMED","VERIFIED"}:continue
            side=getattr(getattr(e,"context_meta",None),"perspective","for")
            if side in ("for","against") and not (side=="for" and e.player_id):events[str(e.id)]=side
        reviewed=validate_reviews(payload.get("reviews"),tracks,events,shots)
        from collections import Counter
        counts=Counter(p.cap_number for p in match.team.players if p.cap_number)
        if any(a["side"]=="for" and counts[a["cap_number"]]>1 for group in reviewed.values() for a in group.values()):
            raise ValueError("Ce numéro est partagé par plusieurs joueuses de la feuille : corriger la feuille avant attribution.")
        summary["identity_reviews"]=reviewed
        auto.summary_json=json.dumps(summary,ensure_ascii=False);db.commit()
        return {"ok":True}
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    finally:_METRIC_SLOT.release()


@router.post("/matches/{match_id}/analysis/collective-review")
def save_collective_review(
    match_id:int, request:Request, binding:str=Form(...), action:str=Form("add"),
    start_s:float|None=Form(None), end_s:float|None=Form(None), period:int|None=Form(None),
    attacking_side:str=Form("for"), attackers:list[str]=Form([]), defenders:list[str]=Form([]),
    carrier:str=Form(""), goal_x:float|None=Form(None), control_reviewed:bool=Form(False),
    roster_reviewed:bool=Form(False), evidence:str=Form(""),
    center:str=Form(""), marker:str=Form(""), keeper:str=Form(""),
    goal_width_m:str=Form(""), assumed_lateral_span_m:str=Form(""),
    before_s:float|None=Form(None), after_s:float|None=Form(None), losing_side:str=Form(""),
    unique_change_reviewed:bool=Form(False), continuous_play_reviewed:bool=Form(False),
    field_players_only:bool=Form(False),
    shot_index:int|None=Form(None), event_id:int|None=Form(None),
    save_event_id:str=Form(""), shot_link_reviewed:bool=Form(False),
    release_height_m:float|None=Form(None), defender_height_m:float|None=Form(None),
    radius_m:float|None=Form(None), horizontal_speed_mps:float|None=Form(None),
    sigma_m:float|None=Form(None), receiver_height_m:float|None=Form(None),
    receivers:list[str]=Form([]), hypotheses_reviewed:bool=Form(False),
    reach_json:str=Form(""), reception_s:str=Form(""), budget_s:str=Form(""),
    motion_mode:str=Form("stationary_hypothesis"),
    db:Session=Depends(get_db),
):
    import json
    from models import AutonomousAnalysis
    from services.collective_review import append,context
    _,match=_owned_match(match_id,request,db)
    if not _is_owned_upload(match):raise HTTPException(400,"Une vidéo locale calibrée est nécessaire.")
    if not _METRIC_SLOT.acquire(blocking=False):raise HTTPException(429,"Un calcul est déjà en cours.")
    try:
        if len(binding)>12000 or action not in ("add","clear","add_recovery","clear_recovery","add_shot","clear_shot","add_3d","clear_3d"):raise ValueError("Requête invalide.")
        snap=analysis_snapshot(db,match);ctx=context(snap)
        if ctx is None or json.loads(binding)!=ctx:raise ValueError("Calibration ou identités modifiées. Actualiser le rapport.")
        auto=db.scalar(select(AutonomousAnalysis).where(AutonomousAnalysis.match_id==match.id).order_by(AutonomousAnalysis.id.desc()).limit(1))
        if not auto or auto.id!=ctx["analysis_id"]:raise ValueError("Analyse périmée.")
        db.refresh(auto)
        summary=json.loads(auto.summary_json or "{}")
        if summary.get("metric_field_map",{}).get("revision")!=ctx["revision"]:raise ValueError("Calibration périmée.")
        if summary.get("identity_reviews",{})!=snap["automatic"]["summary"].get("identity_reviews",{}):raise ValueError("Identités modifiées.")
        if action=="clear":
            summary.pop("collective_reviews",None)
        elif action=="clear_recovery":
            summary.pop("recovery_reviews",None)
        elif action=="clear_shot":
            summary.pop("shot_context_reviews",None)
        elif action=="clear_3d":
            summary.pop("spatial_3d_reviews",None)
        elif action=="add_3d":
            from services.spatial_context_3d import append as append_3d
            if len(reach_json)>10000:raise ValueError("Postures trop volumineuses.")
            raw=dict(binding=ctx,event_id=event_id,release_height_m=release_height_m,defender_height_m=defender_height_m,radius_m=radius_m,horizontal_speed_mps=horizontal_speed_mps,sigma_m=sigma_m,receiver_height_m=receiver_height_m,receivers=receivers,hypotheses_reviewed=hypotheses_reviewed,motion_mode=motion_mode,reach_segments=json.loads(reach_json) if reach_json else {},reception_s=float(reception_s) if reception_s else None,budget_s=float(budget_s) if budget_s else None,evidence=evidence)
            summary["spatial_3d_reviews"]=append_3d(snap,raw)
        elif action=="add_shot":
            from services.shot_context_review import append as append_shot
            raw=dict(binding=ctx,shot_index=shot_index,event_id=event_id,save_event_id=int(save_event_id) if save_event_id else None,goal_x=goal_x,goal_width_m=float(goal_width_m) if goal_width_m else None,defenders=defenders,keeper=keeper,assumed_lateral_span_m=float(assumed_lateral_span_m) if assumed_lateral_span_m else None,evidence=evidence,shot_link_reviewed=shot_link_reviewed,roster_reviewed=roster_reviewed)
            summary["shot_context_reviews"]=append_shot(snap,raw)
        elif action=="add_recovery":
            from services.recovery_review import append as append_recovery
            raw=dict(binding=ctx,start_s=start_s,end_s=end_s,before_s=before_s,after_s=after_s,period=period,losing_side=losing_side,own_goal_x=goal_x,defenders=defenders,evidence=evidence,unique_change_reviewed=unique_change_reviewed,continuous_play_reviewed=continuous_play_reviewed,roster_reviewed=roster_reviewed,field_players_only=field_players_only)
            summary["recovery_reviews"]=append_recovery(snap,raw)
        else:
            raw=dict(binding=ctx,start_s=start_s,end_s=end_s,period=period,attacking_side=attacking_side,attackers=attackers,defenders=defenders,carrier=carrier,goal_x=goal_x,control_reviewed=control_reviewed,roster_reviewed=roster_reviewed,evidence=evidence,center=center,marker=marker,keeper=keeper,goal_width_m=float(goal_width_m) if goal_width_m else None,assumed_lateral_span_m=float(assumed_lateral_span_m) if assumed_lateral_span_m else None)
            summary["collective_reviews"]=append(snap,raw)
        auto.summary_json=json.dumps(summary,ensure_ascii=False);db.commit()
        anchor="spatial3d" if action in ("add_3d","clear_3d") else "shotContext" if action in ("add_shot","clear_shot") else "recoveryReview" if action in ("add_recovery","clear_recovery") else "collectiveReview"
        return RedirectResponse(f"/matches/{match_id}/analysis/result#{anchor}",status_code=303)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as exc:
        raise HTTPException(422,str(exc) if isinstance(exc,ValueError) else "Revue collective invalide.") from None
    finally:
        _METRIC_SLOT.release()


def _r7_local_source(db,match,segment_id):
    from models import MatchVideoSegment
    segment=db.get(MatchVideoSegment,segment_id) if segment_id is not None else None
    if segment_id is not None and (segment is None or segment.match_id!=match.id):
        raise HTTPException(404,"Partie introuvable.")
    kind=segment.source_type if segment else match.video_source
    name=segment.video_path if segment else match.video_path
    if kind!="upload" or not name:raise HTTPException(400,"Une vidéo locale est nécessaire.")
    path=UPLOAD_DIR / Path(name).name
    if not path.is_file():raise HTTPException(404,"Vidéo locale absente.")
    return segment,path

@router.post("/matches/{match_id}/analysis/r7-scan")
def r7_scan(match_id:int,request:Request,start_frame:int=Form(0),frame_count:int=Form(25),
            tracking_mode:str=Form("head_flow"),segment_id:int|None=Form(None),db:Session=Depends(get_db)):
    from services.local_clip_scan import scan_clip
    from services.vision_scan_evidence import save_scan
    _,match=_owned_match(match_id,request,db)
    if request.session.get("web_demo"):raise HTTPException(403,"Le scan expérimental est réservé au compte propriétaire connecté.")
    segment,path=_r7_local_source(db,match,segment_id)
    if not _METRIC_SLOT.acquire(blocking=False):raise HTTPException(429,"Un calcul est déjà en cours.")
    try:
        result=scan_clip(path,start_frame,frame_count,tracking_mode=tracking_mode)
        save_scan(db,match,segment,"tracklets",result,path)
    except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from exc
    finally:_METRIC_SLOT.release()
    return RedirectResponse(f"/matches/{match_id}/analysis/result#visionR7",status_code=303)

@router.post("/matches/{match_id}/analysis/r7-packet")
def r7_packet(match_id:int,request:Request,frame_index:int=Form(...),budget:int=Form(3),
              segment_id:int|None=Form(None),db:Session=Depends(get_db)):
    from services.r7_review_pipeline import packet_from_video
    from services.vision_scan_evidence import save_scan
    _,match=_owned_match(match_id,request,db)
    if request.session.get("web_demo"):raise HTTPException(403,"Compte propriétaire connecté requis.")
    segment,path=_r7_local_source(db,match,segment_id)
    weights=os.getenv("AQUAMETRIC_R7_PRIVATE_WEIGHTS","")
    if not weights:raise HTTPException(409,"Poids privés R7 non configurés sur ce serveur.")
    if not _METRIC_SLOT.acquire(blocking=False):raise HTTPException(429,"Un calcul est déjà en cours.")
    try:
        result=packet_from_video(path,frame_index,weights,budget=budget)
        row=save_scan(db,match,segment,"r7_review",result,path)
        return {"scan_id":row.id,"packet":result["packet"]}
    except (ValueError,OSError,KeyError,TypeError) as exc:raise HTTPException(422,"Impossible de créer le paquet R7 : vérifier source, fenêtre et modèle.") from exc
    finally:_METRIC_SLOT.release()

@router.post("/matches/{match_id}/analysis/r7-review/{scan_id}")
def r7_review(match_id:int,scan_id:int,request:Request,payload:dict,db:Session=Depends(get_db)):
    from models import VisionScanEvidence
    from services.vision_scan_evidence import read_scan,save_scan,source_binding
    from services.candidate_review import validate_response
    from services.r7_review_pipeline import file_hash
    _,match=_owned_match(match_id,request,db)
    if request.session.get("web_demo"):raise HTTPException(403,"Compte propriétaire connecté requis.")
    row=db.get(VisionScanEvidence,scan_id)
    if not row or row.match_id!=match.id or row.kind!="r7_review":raise HTTPException(404,"Paquet introuvable.")
    segment,path=_r7_local_source(db,match,row.segment_id)
    if row.source_binding!=source_binding(match,segment):raise HTTPException(409,"Source modifiée.")
    if not _METRIC_SLOT.acquire(blocking=False):raise HTTPException(429,"Un calcul est déjà en cours.")
    try:
        packet=read_scan(row)["result"]["packet"]
        if file_hash(path)!=packet["source_sha256"]:raise HTTPException(409,"Empreinte vidéo modifiée.")
        reviewed=validate_response(packet,payload)
        # Session owner authenticated; labels still are not independently validated.
        result=dict(engine="head-candidate-review-v1",review=reviewed,packet_scan_id=scan_id,
                    frame_index=packet["source_frame_index"],statistical_use_allowed=False,
                    identity_verified=False,metrics_validated=False,pts_validated=False)
        saved=save_scan(db,match,segment,"r7_decision",result,path)
        return {"scan_id":saved.id,"review":reviewed}
    except (ValueError,OSError,KeyError,TypeError) as exc:raise HTTPException(422,"Revue R7 invalide.") from exc
    finally:_METRIC_SLOT.release()


@router.post("/matches/{match_id}/analysis/r7-metric/{scan_id}")
def r7_metric(match_id:int,scan_id:int,request:Request,payload:dict,db:Session=Depends(get_db)):
    from models import VisionScanEvidence
    from services.vision_scan_evidence import read_scan,save_scan,source_binding
    from services.r7_metric_review import analyze
    import cv2
    _,match=_owned_match(match_id,request,db)
    if request.session.get("web_demo"):raise HTTPException(403,"Compte propriétaire connecté requis.")
    row=db.get(VisionScanEvidence,scan_id)
    if row is None or row.match_id!=match.id or row.kind!="tracklets":raise HTTPException(404,"Scan introuvable.")
    segment,path=_r7_local_source(db,match,row.segment_id)
    if row.source_binding!=source_binding(match,segment):raise HTTPException(409,"Source modifiée.")
    if segment is not None and payload.get("period")!=segment.period:raise HTTPException(422,"Période incompatible avec la partie.")
    if segment is None:
        from models import MatchVideoSegment
        registered=list(db.scalars(select(MatchVideoSegment).where(MatchVideoSegment.match_id==match.id,MatchVideoSegment.source_type=="upload",MatchVideoSegment.video_path==match.video_path)))
        if len(registered)>1 or (registered and payload.get("period")!=registered[0].period):raise HTTPException(422,"Période de la source principale ambiguë ou incompatible.")
    if payload.get("scan_digest")!=row.digest:raise HTTPException(409,"Référence de scan périmée.")
    if not _METRIC_SLOT.acquire(blocking=False):raise HTTPException(429,"Un calcul est déjà en cours.")
    try:
        scan=read_scan(row)["result"]
        result=analyze(path,scan,payload,[p.cap_number for p in match.team.players])
        result.update(scan_id=scan_id,scan_digest=row.digest)
        saved=save_scan(db,match,segment,"r7_metric_review",result,path)
        return {"ok":True,"scan_id":saved.id,"status":result["status"],"players":result["players"]}
    except (ValueError,TypeError,KeyError,AttributeError,OSError,cv2.error) as exc:raise HTTPException(422,"Revue métrique impossible : vérifier source, pistes, identités et repères.") from exc
    finally:_METRIC_SLOT.release()


@router.get("/matches/{match_id}/analysis/r7-evidence/{scan_id}")
def r7_evidence(match_id:int,scan_id:int,request:Request,db:Session=Depends(get_db)):
    from models import VisionScanEvidence
    from services.vision_scan_evidence import read_scan,source_binding
    from models import MatchVideoSegment
    _,match=_owned_match(match_id,request,db)
    row=db.get(VisionScanEvidence,scan_id)
    if row is None or row.match_id!=match.id:raise HTTPException(404,"Preuve introuvable.")
    segment=db.get(MatchVideoSegment,row.segment_id) if row.segment_id is not None else None
    if row.segment_id is not None and (segment is None or segment.match_id!=match.id):raise HTTPException(409,"Partie périmée.")
    if row.source_binding!=source_binding(match,segment):raise HTTPException(409,"Source modifiée.")
    try:return JSONResponse(read_scan(row),headers={"Cache-Control":"private, no-store"})
    except (ValueError,TypeError,KeyError):raise HTTPException(409,"Preuve incohérente.") from None

@router.post("/matches/{match_id}/analysis/r7-metric-form")
def r7_metric_form(match_id:int,request:Request,scan_ref:str=Form(...),period:int=Form(...),
        reference_frame:int=Form(...),length_m:float=Form(...),width_m:float=Form(...),
        anchors_json:str=Form(...),polygon_json:str=Form(...),tracks_json:str=Form(...),
        all_points_reviewed:bool=Form(False),calibration_reviewed:bool=Form(False),
        nominal_time_acknowledged:bool=Form(False),db:Session=Depends(get_db)):
    import json
    _owned_match(match_id,request,db)
    try:
        if len(scan_ref)>90 or any(len(x)>12000 for x in (anchors_json,polygon_json,tracks_json)):raise ValueError()
        ident,digest=scan_ref.split(":",1)
        payload=dict(scan_digest=digest,period=period,reference_frame=reference_frame,length_m=length_m,width_m=width_m,
            anchors=json.loads(anchors_json),polygon=json.loads(polygon_json),tracks=json.loads(tracks_json),
            all_points_reviewed=all_points_reviewed,calibration_reviewed=calibration_reviewed,nominal_time_acknowledged=nominal_time_acknowledged)
        scan_id=int(ident)
    except (TypeError,ValueError):raise HTTPException(422,"Saisie JSON ou référence invalide.") from None
    r7_metric(match_id,scan_id,request,payload,db)
    return RedirectResponse(f"/matches/{match_id}/analysis/result#visionR7",status_code=303)


@router.post("/matches/{match_id}/analysis/possession-window")
def save_possession_window(match_id:int,request:Request,analysis_id:int=Form(...),
        source:str=Form(...),period:int=Form(...),start:float=Form(...),end:float=Form(...),
        before:str=Form(...),after:str=Form(...),before_state:str=Form(...),after_state:str=Form(...),
        cause:str=Form("unknown"),cause_verified:bool=Form(False),decision_verified:bool=Form(False),
        exact:bool=Form(False),prior_shot:bool=Form(False),restart_award:str=Form("unknown"),
        restart_verified:bool=Form(False),source_reviewed:bool=Form(False),evidence:str=Form(...),
        db:Session=Depends(get_db)):
    from models import AutonomousAnalysis
    from services.possession_window_review import append
    import cv2
    _,match=_owned_match(match_id,request,db)
    if request.session.get("web_demo"):raise HTTPException(403,"Compte propriétaire connecté requis.")
    if not _METRIC_SLOT.acquire(blocking=False):raise HTTPException(429,"Un calcul est déjà en cours.")
    try:
        auto=db.scalar(select(AutonomousAnalysis).where(AutonomousAnalysis.match_id==match.id).order_by(AutonomousAnalysis.id.desc()).limit(1))
        if auto is None or auto.id!=analysis_id:raise HTTPException(409,"Analyse périmée.")
        raw=dict(analysis_id=analysis_id,source=source,period=period,start=start,end=end,before=before,after=after,
                 before_state=before_state,after_state=after_state,cause=cause,cause_verified=cause_verified,
                 decision_verified=decision_verified,exact=exact,prior_shot=prior_shot,restart_award=restart_award,
                 restart_verified=restart_verified,source_reviewed=source_reviewed,evidence=evidence)
        append(db,match,auto,raw,UPLOAD_DIR);db.commit()
        return RedirectResponse(f"/matches/{match_id}/analysis/result#possessionEvidence",status_code=303)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError,cv2.error) as exc:
        db.rollback()
        raise HTTPException(422,str(exc) if isinstance(exc,ValueError) else "Revue de possession invalide.") from None
    finally:_METRIC_SLOT.release()
