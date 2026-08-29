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
from video_session_routes import router as video_session_router

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
app.include_router(video_session_router)

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
        raise HTTPException(400, detail="Uploaded video is empty")
    return str(target)
