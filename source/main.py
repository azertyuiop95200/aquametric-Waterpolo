import os
import re
import uuid
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select

from db import Base, engine, get_db, SessionLocal
from models import (User, Club, Team, Player, Match, Event, AnalysisJob, MediaArtifact, EventContext,
                    OfficialDataSource, OfficialFixture, OfficialStanding, OfficialTeamStat, DataRefreshRun, VisionAnalysis, VisionSample, AutonomousAnalysis, AutonomousEventCandidate, TrainingSession, TeamSeasonSummary, MatchLibraryItem, LibraryPlayerMatchStat, ScoutingTeam, ScoutingPlayer, RosterUpdateRequest, SourceWatch, TransferSignal, MatchResearchTarget, PlayerIntelligenceProfile, PlayerSourceRecord, PlayerMatchMetric, FranceSquadMembership, PlayerShotObservation)
from auth import hash_password, verify_password
from services.ratings import calculate_player_rating
from services.video import youtube_embed, is_http_url, timestamped_video_url
from services.analysis_stub import baseline_analysis_message
from services.media import create_screenshot, create_clip, MediaGenerationError, ffmpeg_available
from services.waterpolo_knowledge import OFFICIAL_REFERENCES, TACTICAL_PHASES, ANALYSIS_DIMENSIONS
from services.research_knowledge import RESEARCH_REFERENCES, TACTICAL_LIBRARY
from services.tactical_engine import analyze_match_tactics
from services.official_data import seed_official_sources, refresh_due_sources, recurring_refresh_loop
from services.benchmark_matches import BENCHMARK_MATCHES
from services.vision_baseline import scan_local_video, VisionBaselineError
from services.scoreboard_ocr import sample_scoreboard_observations, tesseract_available
from services.autonomous_engine import infer_periods, infer_candidates, build_auto_summary
from services.reporting import build_match_report
from services.audio_whistle import detect_whistle_candidates, ffmpeg_available as audio_ffmpeg_available
from services.club_data import ensure_granville_team, seed_library
from services.scouting_data import seed_scouting
from services.transfer_watch import seed_transfer_watch
from services.player_intelligence import seed_player_intelligence, profile_snapshot
from services.france_intelligence import seed_france_intelligence, france_dashboard
from services.advanced_metrics import METRIC_GROUPS, event_metric_summary, shot_map_summary
from services.tactical_chess import DEFENCE_PLAYBOOK, recommend_counter_plan
from services.simulation import simulate_matchup, SIM_TEAMS
from extensions import install_extensions
from security import install_security

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", BASE_DIR / "evidence"))
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
APP_NAME = os.getenv("APP_NAME", "AquaMetric")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
AUTO_REFRESH_OFFICIAL_DATA = os.getenv("AUTO_REFRESH_OFFICIAL_DATA", "0") == "1"
WEB_DEMO_MODE = os.getenv("WEB_DEMO_MODE", "0") == "1"
OFFICIAL_REFRESH_LOOP_MINUTES = int(os.getenv("OFFICIAL_REFRESH_LOOP_MINUTES", "30"))
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".ogv", ".ogg"}
EVENT_TYPES = (
    "goal", "assist", "key_pass", "action_created", "touch", "centre_touch", "duel_won", "duel_lost", "pass_complete", "shot_on_target", "shot_off_target", "shot_blocked",
    "block", "interception", "recovery", "save", "bad_pass", "turnover", "foul",
    "exclusion", "exclusion_earned", "exclusion_committed", "penalty_earned", "penalty_committed",
    "whistle", "power_play_start", "penalty_kill_start", "counterattack_start",
    "defensive_recovery_start", "fast_recovery", "late_recovery"
)
PHASE_TAGS = ("auto", "even_attack", "even_defence", "power_play", "penalty_kill", "counterattack", "defensive_recovery", "centre_play", "restart")
PERSPECTIVES = ("for", "against", "neutral")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if AUTO_REFRESH_OFFICIAL_DATA:
        task = asyncio.create_task(recurring_refresh_loop(SessionLocal, OFFICIAL_REFRESH_LOOP_MINUTES))
    try:
        yield
    finally:
        if task:
            task.cancel()

app = FastAPI(title=APP_NAME, lifespan=lifespan)
install_security(app)
SESSION_SECRET = os.getenv("SECRET_KEY", "").strip()
if not SESSION_SECRET:
    if WEB_DEMO_MODE or os.getenv("COOKIE_SECURE", "0") == "1":
        raise RuntimeError("SECRET_KEY is required for secured web deployments")
    SESSION_SECRET = "dev-only-local-secret-change-me"
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "0") == "1",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

Base.metadata.create_all(engine)
install_extensions(app)


def seed():
    db = SessionLocal()
    try:
        exists = db.scalar(select(Club).where(Club.name == "Granville Water Polo", Club.country == "France"))
        if not exists:
            db.add(Club(
                name="Granville Water Polo",
                country="France",
                division="Elite Division 1",
                category="Women",
                is_demo=True,
            ))
            db.commit()
    finally:
        db.close()


seed()

_db_seed = SessionLocal()
try:
    seed_official_sources(_db_seed)
    seed_library(_db_seed)
    seed_scouting(_db_seed)
    seed_transfer_watch(_db_seed)
    seed_player_intelligence(_db_seed)
    seed_france_intelligence(_db_seed)
finally:
    _db_seed.close()

def current_user(request: Request, db: Session):
    uid = request.session.get("user_id")
    return db.get(User, uid) if uid else None


def require_user(request: Request, db: Session):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def ctx(**kwargs):
    return {"app_name": APP_NAME, "web_demo_mode": WEB_DEMO_MODE, **kwargs}


def render(request: Request, template_name: str, status_code: int = 200, **kwargs):
    return templates.TemplateResponse(request, template_name, ctx(**kwargs), status_code=status_code)


def clean_text(value: str, max_len: int = 160) -> str:
    return (value or "").strip()[:max_len]


def save_video_upload(video_file: UploadFile, user_id: int, team_id: int) -> str:
    original = Path(video_file.filename or "video").name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(400, detail=f"Unsupported video format. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}")
    if video_file.content_type and not (video_file.content_type.startswith("video/") or video_file.content_type == "application/octet-stream"):
        raise HTTPException(400, detail="The uploaded file is not recognized as a video.")

    safe_name = f"u{user_id}_t{team_id}_{uuid.uuid4().hex}{suffix}"
    target = UPLOAD_DIR / safe_name
    total = 0
    try:
        with target.open("wb") as out:
            while True:
                chunk = video_file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, detail=f"Video exceeds the configured {MAX_UPLOAD_MB} MB local limit.")
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        video_file.file.close()

    if total == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(400, detail="Uploaded video is empty.")
    return safe_name


@app.exception_handler(401)
def login_required_handler(request: Request, exc: HTTPException):
    return RedirectResponse(f"/login?next={request.url.path}", status_code=303)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    return render(request, "index.html", user=current_user(request, db))

@app.get("/benchmarks", response_class=HTMLResponse)
def benchmarks_page(request: Request, db: Session = Depends(get_db)):
    return render(
        request,
        "benchmarks.html",
        user=current_user(request, db),
        benchmarks=BENCHMARK_MATCHES,
    )


@app.get("/knowledge", response_class=HTMLResponse)
def knowledge_page(request: Request, db: Session = Depends(get_db)):
    return render(
        request,
        "knowledge.html",
        user=current_user(request, db),
        references=sorted(OFFICIAL_REFERENCES, key=lambda item: (item["priority"], item["region"], item["name"])),
        tactical_phases=TACTICAL_PHASES,
        analysis_dimensions=ANALYSIS_DIMENSIONS,
        research_references=sorted(RESEARCH_REFERENCES, key=lambda item: (-item["year"], item["kind"], item["title"])),
        tactical_library=TACTICAL_LIBRARY,
    )


@app.get("/demo-login")
def demo_login(request: Request, db: Session = Depends(get_db)):
    """Create an isolated temporary demo workspace for this browser session.

    Intended for free/ephemeral web deployments. No password is required and
    the data is allowed to disappear when the free host restarts.
    """
    if not WEB_DEMO_MODE:
        raise HTTPException(status_code=404)
    current = current_user(request, db)
    if current:
        return RedirectResponse("/dashboard", status_code=303)
    token = uuid.uuid4().hex[:12]
    user = User(
        email=f"webdemo-{token}@aquametric.local",
        password_hash=hash_password(uuid.uuid4().hex),
        name="Web Demo",
        country="Demo",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    ensure_granville_team(db, user.id)
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["web_demo"] = True
    return RedirectResponse("/my-team", status_code=303)

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return render(request, "register.html")


@app.post("/register")
def register(request: Request, email: str = Form(...), password: str = Form(...), name: str = Form(""), db: Session = Depends(get_db)):
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        return render(request, "register.html", error="Enter a valid email address.", status_code=400)
    if len(password) < 8:
        return render(request, "register.html", error="Password must contain at least 8 characters.", status_code=400)
    if db.scalar(select(User).where(User.email == email)):
        return render(request, "register.html", error="Email already registered.", status_code=400)
    user = User(email=email, password_hash=hash_password(password), name=clean_text(name, 120))
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html")


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not verify_password(password, user.password_hash):
        return render(request, "login.html", error="Invalid credentials.", status_code=400)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/guest", response_class=HTMLResponse)
def guest(request: Request):
    return render(request, "guest.html", demo=None)


@app.post("/guest", response_class=HTMLResponse)
def guest_analyze(request: Request, video_url: str = Form("")):
    video_url = video_url.strip()
    if video_url and not is_http_url(video_url):
        return render(request, "guest.html", demo=None, error="Only http/https video links are supported.", status_code=400)
    embed = youtube_embed(video_url)
    demo = {
        "video_url": video_url,
        "embed": embed,
        "message": "Guest mode is ephemeral. No sports statistics are invented without an AI model or verified tagging.",
    }
    return render(request, "guest.html", demo=demo)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    teams = db.scalars(select(Team).where(Team.owner_id == user.id).order_by(Team.id.desc())).all()
    matches = db.scalars(select(Match).where(Match.owner_id == user.id).order_by(Match.id.desc())).all()
    sources = db.scalars(select(OfficialDataSource).order_by(OfficialDataSource.id)).all()
    structured_records = sum(s.records_count for s in sources)
    return render(request, "dashboard.html", user=user, teams=teams, matches=matches, sources=sources, structured_records=structured_records)


@app.get("/teams", response_class=HTMLResponse)
def teams_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    teams = db.scalars(select(Team).where(Team.owner_id == user.id).order_by(Team.id.desc())).all()
    clubs = db.scalars(
        select(Club)
        .where(Club.owner_id.is_(None) | (Club.owner_id == user.id))
        .order_by(Club.country, Club.category, Club.name)
    ).all()
    return render(request, "teams.html", user=user, teams=teams, clubs=clubs)


@app.post("/clubs")
def create_club(
    request: Request,
    name: str = Form(...),
    country: str = Form(...),
    division: str = Form(""),
    category: str = Form("Women"),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    name = clean_text(name)
    country = clean_text(country, 80)
    division = clean_text(division, 120)
    category = category if category in {"Women", "Men", "Mixed/Other"} else "Mixed/Other"
    if not name or not country:
        raise HTTPException(400, detail="Club name and country are required.")
    existing = db.scalar(
        select(Club).where(
            Club.name == name,
            Club.country == country,
            Club.category == category,
            Club.owner_id.is_(None) | (Club.owner_id == user.id),
        )
    )
    if existing:
        return RedirectResponse(f"/teams?club_exists={existing.id}", status_code=303)
    db.add(Club(name=name, country=country, division=division, category=category, owner_id=user.id))
    db.commit()
    return RedirectResponse("/teams", status_code=303)


@app.post("/teams")
def create_team(request: Request, name: str = Form(...), club_id: int = Form(...), category: str = Form("Women"), db: Session = Depends(get_db)):
    user = require_user(request, db)
    club = db.get(Club, club_id)
    if not club or (club.owner_id is not None and club.owner_id != user.id):
        raise HTTPException(400, detail="Selected club does not exist or is not available.")
    name = clean_text(name)
    if not name:
        raise HTTPException(400, detail="Team name is required.")
    category = category if category in {"Women", "Men", "Mixed/Other"} else "Mixed/Other"
    db.add(Team(name=name, club_id=club_id, owner_id=user.id, category=category))
    db.commit()
    return RedirectResponse("/teams", status_code=303)


@app.get("/teams/{team_id}", response_class=HTMLResponse)
def team_detail(team_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    team = db.get(Team, team_id)
    if not team or team.owner_id != user.id:
        raise HTTPException(404)
    return render(request, "team_detail.html", user=user, team=team)


@app.post("/teams/{team_id}/players")
def add_player(team_id: int, request: Request, name: str = Form(...), cap_number: str = Form(""), db: Session = Depends(get_db)):
    user = require_user(request, db)
    team = db.get(Team, team_id)
    if not team or team.owner_id != user.id:
        raise HTTPException(404)
    name = clean_text(name)
    if not name:
        raise HTTPException(400, detail="Player name is required.")
    cap = None
    if cap_number.strip():
        if not cap_number.strip().isdigit():
            raise HTTPException(400, detail="Cap number must be numeric.")
        cap = int(cap_number)
        if cap < 0 or cap > 99:
            raise HTTPException(400, detail="Cap number must be between 0 and 99.")
    db.add(Player(team_id=team.id, name=name, cap_number=cap))
    db.commit()
    return RedirectResponse(f"/teams/{team_id}", status_code=303)


@app.get("/players", response_class=HTMLResponse)
def players_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    teams = db.scalars(select(Team).where(Team.owner_id == user.id).order_by(Team.name)).all()
    players = [player for team in teams for player in team.players]
    return render(request, "players.html", user=user, players=players)


@app.get("/players/{player_id}", response_class=HTMLResponse)
def player_detail(player_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    player = db.get(Player, player_id)
    if not player or player.team.owner_id != user.id:
        raise HTTPException(404)
    events = db.scalars(
        select(Event)
        .join(Match, Event.match_id == Match.id)
        .where(Event.player_id == player.id, Match.owner_id == user.id)
        .order_by(Event.id.desc())
    ).all()
    rating, confidence, evidence = calculate_player_rating(events, role=player.primary_role)
    return render(request, "player_detail.html", user=user, player=player, events=events, rating=rating, confidence=confidence, evidence=evidence)


@app.get("/matches", response_class=HTMLResponse)
def matches_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    matches = db.scalars(select(Match).where(Match.owner_id == user.id).order_by(Match.id.desc())).all()
    return render(request, "matches.html", user=user, matches=matches)


@app.get("/matches/new", response_class=HTMLResponse)
def new_match_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    teams = db.scalars(select(Team).where(Team.owner_id == user.id).order_by(Team.name)).all()
    return render(request, "match_new.html", user=user, teams=teams, max_upload_mb=MAX_UPLOAD_MB)


@app.post("/matches")
def create_match(
    request: Request,
    team_id: int = Form(...),
    opponent: str = Form(...),
    competition: str = Form(""),
    match_date: str = Form(""),
    video_url: str = Form(""),
    video_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    team = db.get(Team, team_id)
    if not team or team.owner_id != user.id:
        raise HTTPException(404)
    opponent = clean_text(opponent)
    if not opponent:
        raise HTTPException(400, detail="Opponent is required.")
    video_url = video_url.strip()
    if video_url and not is_http_url(video_url):
        raise HTTPException(400, detail="Only http/https video links are supported.")

    video_source, video_path = "none", ""
    if video_file and video_file.filename:
        video_path = save_video_upload(video_file, user.id, team_id)
        video_source = "upload"
    elif video_url:
        video_source = "youtube" if youtube_embed(video_url) else "url"

    match = Match(
        owner_id=user.id,
        team_id=team.id,
        opponent=opponent,
        competition=clean_text(competition),
        match_date=clean_text(match_date, 32),
        video_source=video_source,
        video_url=video_url,
        video_path=video_path,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return RedirectResponse(f"/matches/{match.id}", status_code=303)


@app.get("/matches/{match_id}/video")
def match_video(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id or not match.video_path:
        raise HTTPException(404)
    path = UPLOAD_DIR / Path(match.video_path).name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/matches/{match_id}", response_class=HTMLResponse)
def match_detail(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    players = match.team.players
    ratings = []
    for p in players:
        pevents = [e for e in match.events if e.player_id == p.id]
        rating, conf, evidence = calculate_player_rating(pevents, role=p.primary_role)
        ratings.append((p, rating, conf, evidence))
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.match_id == match.id).order_by(AnalysisJob.id.desc()))
    return render(
        request,
        "match_detail.html",
        user=user,
        match=match,
        players=players,
        ratings=ratings,
        embed=youtube_embed(match.video_url),
        job=job,
        event_types=EVENT_TYPES,
        media_artifacts=sorted(match.media_artifacts, key=lambda a: a.created_at, reverse=True),
        ffmpeg_ready=ffmpeg_available(),
        tactical_report=analyze_match_tactics(match),
        phase_tags=PHASE_TAGS,
        perspectives=PERSPECTIVES,
        latest_vision=db.scalar(select(VisionAnalysis).where(VisionAnalysis.match_id == match.id).order_by(VisionAnalysis.id.desc())),
    )


@app.get("/matches/{match_id}/vision", response_class=HTMLResponse)
def match_vision(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    analysis = db.scalar(select(VisionAnalysis).where(VisionAnalysis.match_id == match.id).order_by(VisionAnalysis.id.desc()))
    samples = []
    active_windows = []
    interesting_moments = []
    scoreboard_candidates = []
    limitations = []
    if analysis:
        samples = db.scalars(select(VisionSample).where(VisionSample.analysis_id == analysis.id).order_by(VisionSample.second)).all()
        try: active_windows = json.loads(analysis.active_windows_json or "[]")
        except Exception: active_windows = []
        try: interesting_moments = json.loads(analysis.interesting_moments_json or "[]")
        except Exception: interesting_moments = []
        try: scoreboard_candidates = json.loads(analysis.scoreboard_candidates_json or "[]")
        except Exception: scoreboard_candidates = []
        try: limitations = json.loads(analysis.limitations_json or "[]")
        except Exception: limitations = []
    return render(request, "vision.html", user=user, match=match, analysis=analysis, samples=samples,
                  active_windows=active_windows, interesting_moments=interesting_moments,
                  scoreboard_candidates=scoreboard_candidates, limitations=limitations)


@app.post("/matches/{match_id}/vision/scan")
def run_vision_scan(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    if match.video_source != "upload" or not match.video_path:
        # Third-party videos remain timestamp/reference-only. We intentionally do not download them.
        job = AnalysisJob(match_id=match.id, stage="visual_baseline", progress=0, status="local_video_required",
                          message="The baseline vision scan requires an owned/uploaded local video. Third-party URLs remain bookmark-only until a provider-authorized analysis path is connected.")
        db.add(job); db.commit()
        return RedirectResponse(f"/matches/{match_id}/vision", status_code=303)
    source_path = UPLOAD_DIR / Path(match.video_path).name
    if not source_path.exists():
        raise HTTPException(404, detail="Uploaded video file is missing.")
    try:
        result = scan_local_video(source_path, EVIDENCE_DIR)
    except VisionBaselineError as exc:
        raise HTTPException(422, detail=str(exc))
    analysis = VisionAnalysis(
        match_id=match.id, status="complete", engine_version="visual-baseline-v1", source_kind="upload",
        duration_seconds=result.duration_seconds, fps=result.fps, width=result.width, height=result.height,
        sample_interval_seconds=result.sample_interval_seconds, sample_count=len(result.samples),
        video_type=result.video_type, confidence=result.video_type_confidence,
        avg_pool_ratio=result.avg_pool_ratio, avg_motion_score=result.avg_motion_score,
        scene_cut_rate=result.scene_cut_rate, active_seconds_estimate=result.active_seconds_estimate,
        active_windows_json=json.dumps(result.active_windows),
        interesting_moments_json=json.dumps(result.interesting_moments),
        scoreboard_candidates_json=json.dumps([c.__dict__ for c in result.scoreboard_candidates]),
        contact_sheet_file=result.contact_sheet_file, limitations_json=json.dumps(result.limitations),
    )
    db.add(analysis); db.flush()
    for sample in result.samples:
        db.add(VisionSample(analysis_id=analysis.id, second=sample.second, pool_ratio=sample.pool_ratio,
                            motion_score=sample.motion_score, scene_change=sample.scene_change,
                            active_score=sample.active_score, action_score=sample.action_score))
    job = AnalysisJob(match_id=match.id, stage="visual_baseline", progress=100, status="baseline_complete",
                      message=f"Visual baseline completed on {len(result.samples)} sampled frames. This is pre-analysis, not event recognition.")
    match.status = "baseline_scanned"
    db.add(job); db.commit()
    return RedirectResponse(f"/matches/{match_id}/vision", status_code=303)


@app.get("/matches/{match_id}/vision/contact-sheet")
def vision_contact_sheet(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    analysis = db.scalar(select(VisionAnalysis).where(VisionAnalysis.match_id == match.id).order_by(VisionAnalysis.id.desc()))
    if not analysis or not analysis.contact_sheet_file:
        raise HTTPException(404)
    path = EVIDENCE_DIR / Path(analysis.contact_sheet_file).name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg")


@app.post("/matches/{match_id}/vision/review-pack")
def vision_review_pack(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    if match.video_source != "upload" or not match.video_path:
        raise HTTPException(400, detail="Review media can only be generated from an owned/uploaded video.")
    analysis = db.scalar(select(VisionAnalysis).where(VisionAnalysis.match_id == match.id).order_by(VisionAnalysis.id.desc()))
    if not analysis:
        raise HTTPException(400, detail="Run the visual baseline first.")
    try: moments = json.loads(analysis.interesting_moments_json or "[]")
    except Exception: moments = []
    source_path = UPLOAD_DIR / Path(match.video_path).name
    created = 0
    for item in moments[:8]:
        second = float(item.get("second", 0))
        if any(a.source == "vision_baseline_candidate" and abs(a.second - second) < 0.5 for a in match.media_artifacts):
            continue
        try:
            generated = create_clip(source_path, EVIDENCE_DIR, second, before=3, after=4)
        except MediaGenerationError:
            continue
        artifact = MediaArtifact(match_id=match.id, artifact_type="clip", analysis_type="action",
            title="Visual review candidate", note="Automatically selected for review from visual activity only. Not classified as a water-polo event.",
            second=second, start_second=generated.start_second, end_second=generated.end_second,
            file_path=generated.filename, mime_type=generated.mime_type, is_downloadable=False, source="vision_baseline_candidate")
        db.add(artifact); created += 1
    db.commit()
    return RedirectResponse(f"/matches/{match_id}/vision", status_code=303)


@app.post("/matches/{match_id}/evidence")
def create_evidence(
    match_id: int,
    request: Request,
    artifact_type: str = Form(...),
    analysis_type: str = Form("action"),
    second: float = Form(0),
    event_id: str = Form(""),
    title: str = Form("Study moment"),
    note: str = Form(""),
    before: float = Form(4),
    after: float = Form(6),
    downloadable: str = Form(""),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    if artifact_type not in {"screenshot", "clip", "bookmark"}:
        raise HTTPException(400, detail="Unsupported evidence type.")
    if analysis_type not in {"action", "tactic", "technique", "referee", "transition"}:
        raise HTTPException(400, detail="Unsupported analysis category.")
    if second < 0 or second > 12 * 60 * 60:
        raise HTTPException(400, detail="Evidence time is outside the supported range.")
    linked_event = None
    if event_id:
        if not event_id.isdigit():
            raise HTTPException(400, detail="Invalid linked event.")
        linked_event = db.get(Event, int(event_id))
        if not linked_event or linked_event.match_id != match.id:
            raise HTTPException(400, detail="Linked event does not belong to this match.")

    artifact = MediaArtifact(
        match_id=match.id,
        event_id=linked_event.id if linked_event else None,
        artifact_type=artifact_type,
        analysis_type=analysis_type,
        title=clean_text(title, 180) or "Study moment",
        note=clean_text(note, 1000),
        second=second,
        start_second=second,
        end_second=second,
        is_downloadable=downloadable in {"1", "true", "on", "yes"},
        source="manual",
    )

    if match.video_source == "upload" and match.video_path:
        video_path = UPLOAD_DIR / Path(match.video_path).name
        if not video_path.exists():
            raise HTTPException(404, detail="Source video file is missing.")
        try:
            if artifact_type == "screenshot":
                generated = create_screenshot(video_path, EVIDENCE_DIR, second)
            elif artifact_type == "clip":
                generated = create_clip(video_path, EVIDENCE_DIR, second, before=before, after=after)
            else:
                generated = None
        except MediaGenerationError as exc:
            raise HTTPException(422, detail=f"Media extraction failed: {exc}")
        if generated:
            artifact.file_path = generated.filename
            artifact.mime_type = generated.mime_type
            artifact.start_second = generated.start_second
            artifact.end_second = generated.end_second
        else:
            artifact.external_url = f"/matches/{match.id}#t={int(second)}"
            artifact.is_downloadable = False
    elif match.video_url:
        # For third-party/YouTube sources we create a timestamp bookmark only.
        # The server does not download or copy third-party video.
        artifact.artifact_type = "bookmark"
        artifact.external_url = timestamped_video_url(match.video_url, second)
        artifact.is_downloadable = False
    else:
        raise HTTPException(400, detail="This match has no video source.")

    db.add(artifact)
    db.commit()
    return RedirectResponse(f"/matches/{match_id}#evidence", status_code=303)


@app.post("/matches/{match_id}/evidence/auto")
def auto_create_evidence(match_id: int, request: Request, db: Session = Depends(get_db)):
    """Build a study pack from already verified/detected events.

    Today this operates on tagged events. Future CV/event workers can create the same
    Event rows and immediately reuse this evidence-generation layer.
    """
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    if not (match.video_path or match.video_url):
        raise HTTPException(400, detail="This match has no video source.")

    interesting = {
        "goal": ("action", "Goal sequence"),
        "shot_on_target": ("action", "Shot on target"),
        "save": ("action", "Goalkeeper save"),
        "block": ("tactic", "Defensive block"),
        "interception": ("transition", "Interception / transition"),
        "turnover": ("transition", "Turnover"),
        "exclusion": ("tactic", "Exclusion / numerical phase"),
        "fast_recovery": ("transition", "Fast defensive recovery"),
        "late_recovery": ("transition", "Late defensive recovery"),
    }
    created = 0
    existing_event_ids = {a.event_id for a in match.media_artifacts if a.event_id}
    for event in sorted(match.events, key=lambda e: e.second):
        if event.id in existing_event_ids or event.event_type not in interesting:
            continue
        analysis_type, title = interesting[event.event_type]
        artifact = MediaArtifact(
            match_id=match.id, event_id=event.id, artifact_type="bookmark",
            analysis_type=analysis_type, title=title, note=event.note or "",
            second=event.second, start_second=event.second, end_second=event.second,
            is_downloadable=False, source="auto_from_event",
        )
        if match.video_source == "upload" and match.video_path:
            source_path = UPLOAD_DIR / Path(match.video_path).name
            if not source_path.exists():
                continue
            try:
                generated = create_clip(source_path, EVIDENCE_DIR, event.second, before=4, after=6)
            except MediaGenerationError:
                continue
            artifact.artifact_type = "clip"
            artifact.file_path = generated.filename
            artifact.mime_type = generated.mime_type
            artifact.start_second = generated.start_second
            artifact.end_second = generated.end_second
        else:
            artifact.external_url = timestamped_video_url(match.video_url, event.second)
        db.add(artifact)
        created += 1
    db.commit()
    return RedirectResponse(f"/matches/{match_id}#evidence", status_code=303)


@app.get("/matches/{match_id}/evidence/{artifact_id}")
def view_evidence(match_id: int, artifact_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    artifact = db.get(MediaArtifact, artifact_id)
    if not match or match.owner_id != user.id or not artifact or artifact.match_id != match.id or not artifact.file_path:
        raise HTTPException(404)
    path = EVIDENCE_DIR / Path(artifact.file_path).name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type=artifact.mime_type or None)


@app.get("/matches/{match_id}/evidence/{artifact_id}/download")
def download_evidence(match_id: int, artifact_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    artifact = db.get(MediaArtifact, artifact_id)
    if not match or match.owner_id != user.id or not artifact or artifact.match_id != match.id:
        raise HTTPException(404)
    if not artifact.is_downloadable or not artifact.file_path:
        raise HTTPException(403, detail="Downloading is disabled for this study media.")
    path = EVIDENCE_DIR / Path(artifact.file_path).name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type=artifact.mime_type or None, filename=path.name)


@app.post("/matches/{match_id}/events")
def add_event(
    match_id: int,
    request: Request,
    event_type: str = Form(...),
    second: float = Form(0),
    player_id: str = Form(""),
    note: str = Form(""),
    perspective: str = Form("for"),
    phase_tag: str = Form("auto"),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    if event_type not in EVENT_TYPES:
        raise HTTPException(400, detail="Unsupported event type.")
    if second < 0 or second > 12 * 60 * 60:
        raise HTTPException(400, detail="Event time is outside the supported range.")

    pid = None
    if player_id:
        if not player_id.isdigit():
            raise HTTPException(400, detail="Invalid player.")
        player = db.get(Player, int(player_id))
        if not player or player.team_id != match.team_id:
            raise HTTPException(400, detail="Player does not belong to this match team.")
        pid = player.id

    if perspective not in PERSPECTIVES:
        perspective = "neutral"
    if phase_tag not in PHASE_TAGS:
        phase_tag = "auto"
    event = Event(
        match_id=match.id,
        player_id=pid,
        second=second,
        event_type=event_type,
        note=clean_text(note, 500),
        confidence="CONFIRMED",
        source="manual",
    )
    db.add(event)
    db.flush()
    db.add(EventContext(event_id=event.id, perspective=perspective, phase_tag=phase_tag))
    db.commit()
    return RedirectResponse(f"/matches/{match_id}", status_code=303)


@app.post("/matches/{match_id}/analysis/start")
def start_analysis(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    msg = baseline_analysis_message(match)
    status = "ai_worker_not_connected" if (match.video_url or match.video_path) else "no_video"
    job = AnalysisJob(match_id=match.id, stage="waiting_for_ai", progress=0, status=status, message=msg)
    match.status = status
    db.add(job)
    db.commit()
    return RedirectResponse(f"/matches/{match_id}", status_code=303)



@app.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    own_matches = db.scalars(select(Match).where(Match.owner_id == user.id).order_by(Match.match_date, Match.id)).all()
    fixtures = db.scalars(select(OfficialFixture).order_by(OfficialFixture.start_text.desc()).limit(250)).all()
    sources = db.scalars(select(OfficialDataSource).order_by(OfficialDataSource.region, OfficialDataSource.name)).all()
    return render(request, "calendar.html", user=user, own_matches=own_matches, fixtures=fixtures, sources=sources, auto_refresh=AUTO_REFRESH_OFFICIAL_DATA)


@app.get("/competitions", response_class=HTMLResponse)
def competitions_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    standings = db.scalars(select(OfficialStanding).order_by(OfficialStanding.competition, OfficialStanding.position).limit(500)).all()
    team_stats = db.scalars(select(OfficialTeamStat).order_by(OfficialTeamStat.competition, OfficialTeamStat.team_name, OfficialTeamStat.metric).limit(5000)).all()
    sources = db.scalars(select(OfficialDataSource).order_by(OfficialDataSource.region, OfficialDataSource.name)).all()
    competitions = {}
    for row in standings:
        competitions.setdefault((row.competition, row.season, row.category), []).append(row)
    stats_by_competition = {}
    for row in team_stats:
        stats_by_competition.setdefault(row.competition, {}).setdefault(row.team_name, {})[row.metric] = row.value
    return render(request, "competitions.html", user=user, competitions=competitions, stats_by_competition=stats_by_competition, sources=sources)


@app.post("/official-data/refresh")
def refresh_official_data(request: Request, force: str = Form(""), db: Session = Depends(get_db)):
    require_user(request, db)
    refresh_due_sources(db, force=force in {"1", "true", "on", "yes"}, max_sources=30)
    return RedirectResponse(request.headers.get("referer") or "/calendar", status_code=303)


@app.get("/matches/{match_id}/tactics", response_class=HTMLResponse)
def match_tactics(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    report = analyze_match_tactics(match)
    return render(request, "tactics.html", user=user, match=match, report=report, tactical_library=TACTICAL_LIBRARY)


@app.post("/matches/{match_id}/autonomy/run")
def run_autonomous_analysis(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    if match.video_source != "upload" or not match.video_path:
        raise HTTPException(400, detail="Autonomous frame analysis currently requires an owned/uploaded local video.")
    vision = db.scalar(select(VisionAnalysis).where(VisionAnalysis.match_id == match.id).order_by(VisionAnalysis.id.desc()))
    if not vision:
        raise HTTPException(400, detail="Run Vision Lab baseline scan first.")
    source_path = UPLOAD_DIR / Path(match.video_path).name
    if not source_path.exists():
        raise HTTPException(404, detail="Uploaded video file is missing.")
    try:
        rois = json.loads(vision.scoreboard_candidates_json or "[]")
        moments = json.loads(vision.interesting_moments_json or "[]")
    except Exception:
        rois, moments = [], []
    observations = [o.to_dict() for o in sample_scoreboard_observations(source_path, rois, vision.duration_seconds)]
    periods = infer_periods(observations, vision.duration_seconds)
    candidates = infer_candidates(observations, moments)
    whistles = detect_whistle_candidates(source_path) if audio_ffmpeg_available() else []
    for w in whistles:
        from services.autonomous_engine import AutoCandidate, confidence_label
        conf = min(0.78, max(0.35, w.score * 0.82))
        candidates.append(AutoCandidate(w.second, "whistle_candidate", conf, confidence_label(conf),
            f"Narrow-band referee-whistle-like audio burst near {w.peak_hz:.0f} Hz.",
            {"signal": "audio_spectrum", "peak_hz": w.peak_hz, "audio_score": w.score, "duration_hint": w.duration_hint}))
    candidates.sort(key=lambda c: c.second)
    summary = build_auto_summary(observations, periods, candidates)
    summary["whistle_candidates"] = len(whistles)
    summary["audio_scan"] = "ready" if audio_ffmpeg_available() else "ffmpeg unavailable"
    limitations = [
        "This autonomy layer does not yet identify players or the ball.",
        "Score changes are candidates derived from OCR and must remain separate from official truth until cross-validated.",
        "Pass, shot, foul, exclusion and tactical-shape classification require dedicated player/ball/audio models.",
    ]
    analysis = AutonomousAnalysis(match_id=match.id, status="complete", engine_version="autonomy-v0.1",
        ocr_available=tesseract_available(), observations_json=json.dumps(observations), periods_json=json.dumps(periods),
        summary_json=json.dumps(summary), limitations_json=json.dumps(limitations))
    db.add(analysis); db.flush()
    for c in candidates:
        db.add(AutonomousEventCandidate(analysis_id=analysis.id, match_id=match.id, second=c.second,
            event_type=c.event_type, confidence_score=c.confidence, confidence_label=c.confidence_label,
            summary=c.summary, evidence_json=json.dumps(c.evidence), source="autonomy-v0.1"))
    match.status = "autonomy_scanned"
    db.commit()
    return RedirectResponse(f"/matches/{match_id}/autonomy", status_code=303)


@app.get("/matches/{match_id}/autonomy", response_class=HTMLResponse)
def autonomy_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    analysis = db.scalar(select(AutonomousAnalysis).where(AutonomousAnalysis.match_id == match.id).order_by(AutonomousAnalysis.id.desc()))
    observations = []; periods = []; summary = {}; limitations = []; candidates = []
    if analysis:
        try: observations = json.loads(analysis.observations_json or "[]")
        except Exception: pass
        try: periods = json.loads(analysis.periods_json or "[]")
        except Exception: pass
        try: summary = json.loads(analysis.summary_json or "{}")
        except Exception: pass
        try: limitations = json.loads(analysis.limitations_json or "[]")
        except Exception: pass
        candidates = db.scalars(select(AutonomousEventCandidate).where(AutonomousEventCandidate.analysis_id == analysis.id).order_by(AutonomousEventCandidate.second)).all()
    return render(request, "autonomy.html", user=user, match=match, analysis=analysis, observations=observations,
                  periods=periods, summary=summary, limitations=limitations, candidates=candidates, ocr_ready=tesseract_available())


@app.get("/matches/{match_id}/report", response_class=HTMLResponse)
def report_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    auto = db.scalar(select(AutonomousAnalysis).where(AutonomousAnalysis.match_id == match.id).order_by(AutonomousAnalysis.id.desc()))
    auto_candidates = []
    if auto:
        auto_candidates = db.scalars(select(AutonomousEventCandidate).where(AutonomousEventCandidate.analysis_id == auto.id).order_by(AutonomousEventCandidate.second)).all()
    report = build_match_report(match, auto, auto_candidates)
    return render(request, "report.html", user=user, match=match, report=report)


@app.get("/matches/{match_id}/report.json")
def report_json(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)
    auto = db.scalar(select(AutonomousAnalysis).where(AutonomousAnalysis.match_id == match.id).order_by(AutonomousAnalysis.id.desc()))
    candidates = db.scalars(
        select(AutonomousEventCandidate)
        .where(AutonomousEventCandidate.analysis_id == auto.id)
        .order_by(AutonomousEventCandidate.second)
    ).all() if auto else []
    report = build_match_report(match, auto, candidates)
    return {
        "match": {"team": match.team.name, "opponent": match.opponent, "competition": match.competition, "date": match.match_date},
        "executive_summary": report["executive_summary"],
        "headline": report["headline"],
        "data_quality": report["data_quality"],
        "auto_summary": report["auto_summary"],
        "auto_candidates": [{"second": c.second, "event_type": c.event_type, "confidence": c.confidence_label, "summary": c.summary} for c in candidates],
    }


@app.get("/my-team", response_class=HTMLResponse)
def my_team_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    team = ensure_granville_team(db, user.id)
    training = db.scalars(select(TrainingSession).where(TrainingSession.team_id == team.id).order_by(TrainingSession.id)).all()
    summary = db.scalar(select(TeamSeasonSummary).where(TeamSeasonSummary.team_id == team.id, TeamSeasonSummary.season == "2025-2026"))
    current_fixtures = db.scalars(select(OfficialFixture).where(OfficialFixture.season == "2026-2027", OfficialFixture.competition == "Elite Féminine", ((OfficialFixture.home_team.contains("Granville")) | (OfficialFixture.away_team.contains("Granville")))).order_by(OfficialFixture.start_text.asc())).all()
    results = db.scalars(select(OfficialFixture).where(OfficialFixture.season == "2025-2026", OfficialFixture.status == "finished", ((OfficialFixture.home_team.contains("Granville")) | (OfficialFixture.away_team.contains("Granville")))).order_by(OfficialFixture.start_text.desc())).all()
    scout_teams = db.scalars(select(ScoutingTeam).where(ScoutingTeam.team_type == "club").order_by(ScoutingTeam.priority.desc())).all()
    scout_by_name = {x.name.lower(): x for x in scout_teams}
    def scout_for(name):
        n=(name or "").lower()
        for key, value in scout_by_name.items():
            if key in n or n in key:
                return value
        return None
    next_opponents=[]
    for fixture in current_fixtures[:5]:
        opp = fixture.away_team if "granville" in fixture.home_team.lower() else fixture.home_team
        next_opponents.append({"fixture":fixture,"opponent":opp,"scout":scout_for(opp)})
    granville_scout = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == "club-fr-granville-w-elite"))
    granville_players = db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id == granville_scout.id).order_by(ScoutingPlayer.cap_number.nullslast(), ScoutingPlayer.name)).all() if granville_scout else []
    return render(request, "my_team.html", user=user, team=team, training=training, summary=summary, upcoming=current_fixtures, results=results, next_opponents=next_opponents, granville_scout=granville_scout, granville_players=granville_players)

@app.get("/scouting", response_class=HTMLResponse)
def scouting_page(request: Request, kind: str = "club", db: Session = Depends(get_db)):
    user = require_user(request, db)
    q = select(ScoutingTeam).order_by(ScoutingTeam.priority.desc(), ScoutingTeam.name.asc())
    if kind in ("club", "national_team"):
        q=q.where(ScoutingTeam.team_type == kind)
    teams=db.scalars(q).all()
    return render(request, "scouting.html", user=user, teams=teams, selected_kind=kind)

@app.get("/scouting/{team_id}", response_class=HTMLResponse)
def scouting_detail(team_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    team=db.get(ScoutingTeam, team_id)
    if not team: raise HTTPException(404, detail="Scouting team not found")
    players=db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id==team.id).order_by(ScoutingPlayer.cap_number.nullslast(), ScoutingPlayer.name)).all()
    fixtures=[]
    if team.team_type == "club":
        fixtures=db.scalars(select(OfficialFixture).where(OfficialFixture.season=="2026-2027", OfficialFixture.competition=="Elite Féminine", ((OfficialFixture.home_team.contains(team.name.split(' — ')[0])) | (OfficialFixture.away_team.contains(team.name.split(' — ')[0])))).order_by(OfficialFixture.start_text)).all()
    return render(request, "scouting_detail.html", user=user, scout_team=team, players=players, fixtures=fixtures)

@app.post("/scouting/request")
def scouting_request(request: Request, request_type: str = Form(...), query: str = Form(...), source_hint: str = Form(""), db: Session = Depends(get_db)):
    user=require_user(request, db)
    query=query.strip()
    if not query: raise HTTPException(400, detail="A player/team name is required")
    db.add(RosterUpdateRequest(requested_by_user_id=user.id, request_type=request_type[:40], query=query[:220], source_hint=source_hint[:2000], status="queued"))
    db.commit()
    return RedirectResponse('/scouting?requested=1', status_code=303)

@app.get("/national-teams", response_class=HTMLResponse)
def national_teams_page(request: Request, db: Session = Depends(get_db)):
    user=require_user(request, db)
    teams=db.scalars(select(ScoutingTeam).where(ScoutingTeam.team_type=="national_team").order_by(ScoutingTeam.age_group, ScoutingTeam.priority.desc())).all()
    seniors=[x for x in teams if x.age_group=="Senior"]
    u20=[x for x in teams if x.age_group=="U20"]
    return render(request, "national_teams.html", user=user, seniors=seniors, u20=u20)

@app.get("/analysis-library", response_class=HTMLResponse)
def analysis_library_page(request: Request, competition: str = "", team: str = "", db: Session = Depends(get_db)):
    user = require_user(request, db)
    q = select(MatchLibraryItem).order_by(MatchLibraryItem.season.desc(), MatchLibraryItem.id.desc())
    if competition:
        q = q.where(MatchLibraryItem.competition.contains(competition))
    if team:
        q = q.where((MatchLibraryItem.team_a.contains(team)) | (MatchLibraryItem.team_b.contains(team)))
    items = db.scalars(q).all()
    competitions = sorted({x.competition for x in db.scalars(select(MatchLibraryItem)).all()})
    return render(request, "analysis_library.html", user=user, items=items, competitions=competitions, selected_competition=competition, selected_team=team)

@app.get("/analysis-library/{item_id}", response_class=HTMLResponse)
def analysis_library_detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    item = db.get(MatchLibraryItem, item_id)
    if not item:
        raise HTTPException(404, detail="Library match not found")
    stats = db.scalars(select(LibraryPlayerMatchStat).where(LibraryPlayerMatchStat.library_match_id == item.id).order_by(LibraryPlayerMatchStat.team_name, LibraryPlayerMatchStat.goals.desc().nullslast(), LibraryPlayerMatchStat.player_name)).all()
    import json as _json
    try: team_stats = _json.loads(item.team_stats_json or '{}')
    except Exception: team_stats = {}
    try: quarters = _json.loads(item.quarter_scores_json or '[]')
    except Exception: quarters = []
    teams = {}
    for st in stats:
        teams.setdefault(st.team_name, []).append(st)
    return render(request, "analysis_library_detail.html", user=user, item=item, stats=stats, teams=teams, team_stats=team_stats, quarters=quarters)

@app.get("/transfer-watch", response_class=HTMLResponse)
def transfer_watch_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    transfers = db.scalars(select(TransferSignal).order_by(TransferSignal.published_date.desc(), TransferSignal.id.desc())).all()
    sources = db.scalars(select(SourceWatch).where(SourceWatch.enabled == True).order_by(SourceWatch.trust_level, SourceWatch.name)).all()
    targets = db.scalars(select(MatchResearchTarget).order_by(MatchResearchTarget.priority.desc(), MatchResearchTarget.event_date.desc())).all()
    profile_by_name={p.canonical_name:p.id for p in db.scalars(select(PlayerIntelligenceProfile)).all()}
    return render(request, "transfer_watch.html", user=user, transfers=transfers, sources=sources, targets=targets, profile_by_name=profile_by_name, confirmed=sum(x.signal_type=="confirmed" for x in transfers), rumours=sum(x.signal_type=="rumour" for x in transfers))

@app.get("/player-data", response_class=HTMLResponse)
def player_data_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    scout_players = db.scalars(select(ScoutingPlayer).order_by(ScoutingPlayer.name)).all()
    library_stats = db.scalars(select(LibraryPlayerMatchStat)).all()
    by_name = {}
    for s in library_stats:
        d=by_name.setdefault(s.player_name,{"matches":0,"goals":0,"saves":0}); d["matches"]+=1; d["goals"]+=int(s.goals or 0); d["saves"]+=int(s.saves or 0)
    rows=[]; seen=set()
    for p in scout_players:
        if p.name in seen: continue
        seen.add(p.name); d=by_name.get(p.name,{"matches":0,"goals":0,"saves":0})
        rows.append({"name":p.name,"nationality":p.nationality,"role":p.role,"matches":d["matches"],"goals":d["goals"],"saves":d["saves"],"coverage":"official match stats" if d["matches"] else "roster only — match stats queued"})
    for name,d in by_name.items():
        if name not in seen: rows.append({"name":name,"nationality":"","role":"","matches":d["matches"],"goals":d["goals"],"saves":d["saves"],"coverage":"official match stats"})
    rows.sort(key=lambda r:(-r["matches"],r["name"]))
    return render(request,"player_data.html",user=user,rows=rows,total_players=len(rows),covered=sum(r["matches"]>0 for r in rows))


@app.get("/player-intelligence", response_class=HTMLResponse)
def player_intelligence_page(request: Request, q: str = "", db: Session = Depends(get_db)):
    user = require_user(request, db)
    stmt = select(PlayerIntelligenceProfile).order_by(PlayerIntelligenceProfile.confidence_score.desc(), PlayerIntelligenceProfile.canonical_name.asc())
    if q.strip():
        term=q.strip()
        stmt=stmt.where((PlayerIntelligenceProfile.canonical_name.contains(term)) | (PlayerIntelligenceProfile.current_club.contains(term)) | (PlayerIntelligenceProfile.current_national_team.contains(term)))
    profiles=db.scalars(stmt).all()
    rows=[]
    for p in profiles:
        snap=profile_snapshot(db,p)
        rows.append({"profile":p,"snapshot":snap})
    requests=db.scalars(select(RosterUpdateRequest).where(RosterUpdateRequest.requested_by_user_id==user.id).order_by(RosterUpdateRequest.created_at.desc()).limit(8)).all()
    return render(request,"player_intelligence.html",user=user,rows=rows,query=q,requests=requests,covered=sum(r["snapshot"]["matches"]>0 for r in rows))

@app.get("/player-intelligence/{profile_id}", response_class=HTMLResponse)
def player_intelligence_detail(profile_id: int, request: Request, db: Session = Depends(get_db)):
    user=require_user(request,db)
    profile=db.get(PlayerIntelligenceProfile,profile_id)
    if not profile: raise HTTPException(404,detail="Player intelligence profile not found")
    sources=db.scalars(select(PlayerSourceRecord).where(PlayerSourceRecord.profile_id==profile.id).order_by(PlayerSourceRecord.observed_at.desc())).all()
    metrics=db.scalars(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id==profile.id).order_by(PlayerMatchMetric.library_match_id.desc().nullslast(),PlayerMatchMetric.metric)).all()
    match_ids=sorted({m.library_match_id for m in metrics if m.library_match_id}, reverse=True)
    matches={mid:db.get(MatchLibraryItem,mid) for mid in match_ids}
    grouped=[]
    for mid in match_ids:
        grouped.append({"match":matches[mid],"metrics":[m for m in metrics if m.library_match_id==mid]})
    standalone=[m for m in metrics if not m.library_match_id]
    transfers=db.scalars(select(TransferSignal).where(TransferSignal.player_name==profile.canonical_name).order_by(TransferSignal.published_date.desc())).all()
    snap=profile_snapshot(db,profile)
    shot_map=shot_map_summary(db, profile.id)
    memberships=db.scalars(select(FranceSquadMembership).where(FranceSquadMembership.profile_id==profile.id).order_by(FranceSquadMembership.year.desc())).all()
    coverage={"identity":bool(profile.nationality),"roster":profile.roster_status not in ("research_required","roster_refresh_required"),"match_stats":snap["matches"]>0,"video":any(g["match"] and g["match"].video_url for g in grouped),"advanced_ai":shot_map["count"]>0}
    return render(request,"player_intelligence_detail.html",user=user,profile=profile,sources=sources,grouped=grouped,standalone=standalone,transfers=transfers,snapshot=snap,coverage=coverage,shot_map=shot_map,metric_groups=METRIC_GROUPS,memberships=memberships)

@app.post("/player-intelligence/request")
def player_intelligence_request(request: Request, query: str = Form(...), source_hint: str = Form(""), db: Session = Depends(get_db)):
    user=require_user(request,db)
    query=clean_text(query,220)
    if not query: raise HTTPException(400,detail="A player or team name is required")
    db.add(RosterUpdateRequest(requested_by_user_id=user.id,request_type="player_intelligence",query=query,source_hint=source_hint[:2000],status="queued"))
    db.commit()
    return RedirectResponse('/player-intelligence?requested=1',status_code=303)


@app.get("/france-intelligence", response_class=HTMLResponse)
def france_intelligence_page(request: Request, db: Session = Depends(get_db)):
    user=require_user(request,db)
    data=france_dashboard(db)
    return render(request,"france_intelligence.html",user=user,**data,metric_groups=METRIC_GROUPS)

@app.get("/tactical-chess", response_class=HTMLResponse)
def tactical_chess_page(request: Request, defence: str = "press", db: Session = Depends(get_db)):
    user=require_user(request,db)
    if defence not in DEFENCE_PLAYBOOK: defence="press"
    plan=recommend_counter_plan(defence,{})
    return render(request,"tactical_chess.html",user=user,playbook=DEFENCE_PLAYBOOK,selected=defence,plan=plan)

@app.get("/simulation", response_class=HTMLResponse)
def simulation_page(request: Request, team_a: str = "Granville Water Polo", team_b: str = "Lille UC Métropole Water-Polo", tactic_a: str = "balanced", tactic_b: str = "balanced", availability_a: int = 100, availability_b: int = 100, form_a: int = 50, form_b: int = 50, rest_a: int = 3, rest_b: int = 3, venue: str = "neutral", db: Session = Depends(get_db)):
    user=require_user(request,db)
    if team_a not in SIM_TEAMS: team_a="Granville Water Polo"
    if team_b not in SIM_TEAMS: team_b="Lille UC Métropole Water-Polo"
    allowed={"balanced","transition","centre_pressure","zone_plus_focus","defence_first"}
    if tactic_a not in allowed: tactic_a="balanced"
    if tactic_b not in allowed: tactic_b="balanced"
    if venue not in {"neutral","team_a_home","team_b_home"}: venue="neutral"
    availability_a=max(50,min(100,availability_a)); availability_b=max(50,min(100,availability_b))
    form_a=max(30,min(70,form_a)); form_b=max(30,min(70,form_b))
    rest_a=max(0,min(7,rest_a)); rest_b=max(0,min(7,rest_b))
    result=simulate_matchup(team_a,team_b,tactic_a,tactic_b,n=5000,availability_a=availability_a,availability_b=availability_b,form_a=form_a,form_b=form_b,rest_a=rest_a,rest_b=rest_b,venue=venue)
    return render(request,"match_simulation.html",user=user,teams=SIM_TEAMS,result=result,tactic_a=tactic_a,tactic_b=tactic_b,availability_a=availability_a,availability_b=availability_b,form_a=form_a,form_b=form_b,rest_a=rest_a,rest_b=rest_b,venue=venue)

@app.get("/health")
def health():
    return {"ok": True, "app": APP_NAME}
