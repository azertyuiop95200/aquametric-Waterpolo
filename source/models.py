from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class Club(Base):
    __tablename__ = "clubs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    country: Mapped[str] = mapped_column(String(80), default="")
    division: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(20), default="Women")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(30), default="Women")
    club = relationship("Club")
    players = relationship("Player", back_populates="team", cascade="all, delete-orphan")

class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(String(160))
    cap_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    primary_role: Mapped[str] = mapped_column(String(80), default="AI to infer")
    team = relationship("Team", back_populates="players")

class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    opponent: Mapped[str] = mapped_column(String(160))
    competition: Mapped[str] = mapped_column(String(160), default="")
    match_date: Mapped[str] = mapped_column(String(32), default="")
    video_source: Mapped[str] = mapped_column(String(30), default="none")
    video_url: Mapped[str] = mapped_column(Text, default="")
    video_path: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    team = relationship("Team")
    events = relationship("Event", back_populates="match", cascade="all, delete-orphan")
    media_artifacts = relationship("MediaArtifact", back_populates="match", cascade="all, delete-orphan")

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    second: Mapped[float] = mapped_column(Float, default=0)
    event_type: Mapped[str] = mapped_column(String(60))
    confidence: Mapped[str] = mapped_column(String(30), default="CONFIRMED")
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(30), default="manual")
    match = relationship("Match", back_populates="events")
    player = relationship("Player")
    media_artifacts = relationship("MediaArtifact", back_populates="event", cascade="all, delete-orphan")
    context_meta = relationship("EventContext", uselist=False, cascade="all, delete-orphan")

class MediaArtifact(Base):
    __tablename__ = "media_artifacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(30))  # screenshot, clip, bookmark
    analysis_type: Mapped[str] = mapped_column(String(30), default="action")  # action, tactic, technique
    title: Mapped[str] = mapped_column(String(180), default="Study moment")
    note: Mapped[str] = mapped_column(Text, default="")
    second: Mapped[float] = mapped_column(Float, default=0)
    start_second: Mapped[float] = mapped_column(Float, default=0)
    end_second: Mapped[float] = mapped_column(Float, default=0)
    file_path: Mapped[str] = mapped_column(Text, default="")
    mime_type: Mapped[str] = mapped_column(String(80), default="")
    external_url: Mapped[str] = mapped_column(Text, default="")
    is_downloadable: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(30), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    match = relationship("Match", back_populates="media_artifacts")
    event = relationship("Event", back_populates="media_artifacts")

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    stage: Mapped[str] = mapped_column(String(80), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="queued")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class OfficialDataSource(Base):
    __tablename__ = "official_data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), default="official")
    region: Mapped[str] = mapped_column(String(80), default="International")
    url: Mapped[str] = mapped_column(Text, default="")
    parser_kind: Mapped[str] = mapped_column(String(60), default="status_only")
    refresh_interval_hours: Mapped[int] = mapped_column(Integer, default=12)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    records_count: Mapped[int] = mapped_column(Integer, default=0)

class OfficialFixture(Base):
    __tablename__ = "official_fixtures"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("official_data_sources.id"), index=True)
    external_key: Mapped[str] = mapped_column(String(255), index=True)
    competition: Mapped[str] = mapped_column(String(180), default="")
    season: Mapped[str] = mapped_column(String(40), default="")
    category: Mapped[str] = mapped_column(String(40), default="")
    start_text: Mapped[str] = mapped_column(String(80), default="")
    home_team: Mapped[str] = mapped_column(String(180), default="")
    away_team: Mapped[str] = mapped_column(String(180), default="")
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    venue: Mapped[str] = mapped_column(String(180), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class OfficialStanding(Base):
    __tablename__ = "official_standings"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("official_data_sources.id"), index=True)
    competition: Mapped[str] = mapped_column(String(180), default="")
    season: Mapped[str] = mapped_column(String(40), default="")
    category: Mapped[str] = mapped_column(String(40), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    team_name: Mapped[str] = mapped_column(String(180), default="")
    points: Mapped[int] = mapped_column(Integer, default=0)
    played: Mapped[int] = mapped_column(Integer, default=0)
    won: Mapped[int] = mapped_column(Integer, default=0)
    lost: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    goal_diff: Mapped[int] = mapped_column(Integer, default=0)
    source_url: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class DataRefreshRun(Base):
    __tablename__ = "data_refresh_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("official_data_sources.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="started")
    message: Mapped[str] = mapped_column(Text, default="")
    records_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class EventContext(Base):
    __tablename__ = "event_contexts"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), unique=True, index=True)
    perspective: Mapped[str] = mapped_column(String(20), default="for")  # for, against, neutral
    phase_tag: Mapped[str] = mapped_column(String(40), default="auto")
    quality_tag: Mapped[str] = mapped_column(String(40), default="")

class OfficialTeamStat(Base):
    __tablename__ = "official_team_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("official_data_sources.id"), index=True)
    competition: Mapped[str] = mapped_column(String(180), default="")
    season: Mapped[str] = mapped_column(String(40), default="")
    category: Mapped[str] = mapped_column(String(40), default="")
    team_name: Mapped[str] = mapped_column(String(180), index=True)
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Float, default=0)
    source_url: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class VisionAnalysis(Base):
    __tablename__ = "vision_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="complete")
    engine_version: Mapped[str] = mapped_column(String(60), default="visual-baseline-v1")
    source_kind: Mapped[str] = mapped_column(String(30), default="upload")
    duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    sample_interval_seconds: Mapped[float] = mapped_column(Float, default=0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    video_type: Mapped[str] = mapped_column(String(60), default="unknown")
    confidence: Mapped[str] = mapped_column(String(30), default="LOW")
    avg_pool_ratio: Mapped[float] = mapped_column(Float, default=0)
    avg_motion_score: Mapped[float] = mapped_column(Float, default=0)
    scene_cut_rate: Mapped[float] = mapped_column(Float, default=0)
    active_seconds_estimate: Mapped[float] = mapped_column(Float, default=0)
    active_windows_json: Mapped[str] = mapped_column(Text, default="[]")
    interesting_moments_json: Mapped[str] = mapped_column(Text, default="[]")
    scoreboard_candidates_json: Mapped[str] = mapped_column(Text, default="[]")
    contact_sheet_file: Mapped[str] = mapped_column(Text, default="")
    limitations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class VisionSample(Base):
    __tablename__ = "vision_samples"
    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("vision_analyses.id"), index=True)
    second: Mapped[float] = mapped_column(Float, default=0)
    pool_ratio: Mapped[float] = mapped_column(Float, default=0)
    motion_score: Mapped[float] = mapped_column(Float, default=0)
    scene_change: Mapped[float] = mapped_column(Float, default=0)
    active_score: Mapped[float] = mapped_column(Float, default=0)
    action_score: Mapped[float] = mapped_column(Float, default=0)

class AutonomousAnalysis(Base):
    __tablename__ = "autonomous_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="complete")
    engine_version: Mapped[str] = mapped_column(String(60), default="autonomy-v0.1")
    ocr_available: Mapped[bool] = mapped_column(Boolean, default=False)
    observations_json: Mapped[str] = mapped_column(Text, default="[]")
    periods_json: Mapped[str] = mapped_column(Text, default="[]")
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    limitations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class AutonomousEventCandidate(Base):
    __tablename__ = "autonomous_event_candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("autonomous_analyses.id"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    second: Mapped[float] = mapped_column(Float, default=0)
    event_type: Mapped[str] = mapped_column(String(80))
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    confidence_label: Mapped[str] = mapped_column(String(30), default="LOW")
    summary: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    source: Mapped[str] = mapped_column(String(40), default="autonomy-v0.1")


class TrainingSession(Base):
    __tablename__ = "training_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    weekday: Mapped[str] = mapped_column(String(20), default="")
    start_time: Mapped[str] = mapped_column(String(10), default="")
    end_time: Mapped[str] = mapped_column(String(10), default="")
    session_type: Mapped[str] = mapped_column(String(80), default="Water polo")
    venue: Mapped[str] = mapped_column(String(180), default="")
    source_season: Mapped[str] = mapped_column(String(40), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)

class TeamSeasonSummary(Base):
    __tablename__ = "team_season_summaries"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    season: Mapped[str] = mapped_column(String(40), default="")
    competition: Mapped[str] = mapped_column(String(180), default="")
    final_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    played: Mapped[int] = mapped_column(Integer, default=0)
    won: Mapped[int] = mapped_column(Integer, default=0)
    drawn: Mapped[int] = mapped_column(Integer, default=0)
    lost: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_note: Mapped[str] = mapped_column(Text, default="")

class MatchLibraryItem(Base):
    __tablename__ = "match_library_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(220), default="")
    competition: Mapped[str] = mapped_column(String(180), default="")
    season: Mapped[str] = mapped_column(String(40), default="")
    entity_type: Mapped[str] = mapped_column(String(30), default="national_team")
    team_a: Mapped[str] = mapped_column(String(180), default="")
    team_b: Mapped[str] = mapped_column(String(180), default="")
    score_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quarter_scores_json: Mapped[str] = mapped_column(Text, default="[]")
    video_url: Mapped[str] = mapped_column(Text, default="")
    video_kind: Mapped[str] = mapped_column(String(30), default="unknown")
    official_source_url: Mapped[str] = mapped_column(Text, default="")
    analysis_status: Mapped[str] = mapped_column(String(40), default="catalogued")
    tactical_summary: Mapped[str] = mapped_column(Text, default="")
    team_stats_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class LibraryPlayerMatchStat(Base):
    __tablename__ = "library_player_match_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    library_match_id: Mapped[int] = mapped_column(ForeignKey("match_library_items.id"), index=True)
    team_name: Mapped[str] = mapped_column(String(180), default="")
    player_name: Mapped[str] = mapped_column(String(180), default="")
    goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exclusions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_quality: Mapped[str] = mapped_column(String(30), default="official_report")
    note: Mapped[str] = mapped_column(Text, default="")

class ScoutingTeam(Base):
    __tablename__ = "scouting_teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    team_type: Mapped[str] = mapped_column(String(30), default="club")  # club, national_team
    category: Mapped[str] = mapped_column(String(40), default="Women")
    age_group: Mapped[str] = mapped_column(String(40), default="Senior")
    country: Mapped[str] = mapped_column(String(80), default="")
    competition: Mapped[str] = mapped_column(String(180), default="")
    season_label: Mapped[str] = mapped_column(String(40), default="")
    roster_status: Mapped[str] = mapped_column(String(50), default="historical_pending_refresh")
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_note: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class ScoutingPlayer(Base):
    __tablename__ = "scouting_players"
    id: Mapped[int] = mapped_column(primary_key=True)
    scouting_team_id: Mapped[int] = mapped_column(ForeignKey("scouting_teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    cap_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nationality: Mapped[str] = mapped_column(String(40), default="")
    role: Mapped[str] = mapped_column(String(80), default="Role to confirm")
    source_season: Mapped[str] = mapped_column(String(40), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_quality: Mapped[str] = mapped_column(String(40), default="official_match_sheet")
    current_status: Mapped[str] = mapped_column(String(50), default="historical")
    note: Mapped[str] = mapped_column(Text, default="")

class RosterUpdateRequest(Base):
    __tablename__ = "roster_update_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    request_type: Mapped[str] = mapped_column(String(40), default="team")
    query: Mapped[str] = mapped_column(String(220), default="")
    source_hint: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class SourceWatch(Base):
    __tablename__ = "source_watches"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="media")
    platform: Mapped[str] = mapped_column(String(40), default="web")
    entity_scope: Mapped[str] = mapped_column(String(180), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    trust_level: Mapped[str] = mapped_column(String(30), default="secondary")
    refresh_hours: Mapped[int] = mapped_column(Integer, default=24)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[str] = mapped_column(String(40), default="seeded")
    note: Mapped[str] = mapped_column(Text, default="")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class TransferSignal(Base):
    __tablename__ = "transfer_signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_name: Mapped[str] = mapped_column(String(180), index=True)
    gender: Mapped[str] = mapped_column(String(20), default="Women")
    from_team: Mapped[str] = mapped_column(String(180), default="")
    to_team: Mapped[str] = mapped_column(String(180), default="")
    signal_type: Mapped[str] = mapped_column(String(30), default="confirmed")
    season: Mapped[str] = mapped_column(String(40), default="2026-2027")
    published_date: Mapped[str] = mapped_column(String(30), default="")
    source_name: Mapped[str] = mapped_column(String(180), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_tier: Mapped[str] = mapped_column(String(30), default="media_confirmed")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.8)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class MatchResearchTarget(Base):
    __tablename__ = "match_research_targets"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    competition: Mapped[str] = mapped_column(String(180), default="")
    season: Mapped[str] = mapped_column(String(40), default="")
    category: Mapped[str] = mapped_column(String(40), default="Women")
    team_a: Mapped[str] = mapped_column(String(180), default="")
    team_b: Mapped[str] = mapped_column(String(180), default="")
    event_date: Mapped[str] = mapped_column(String(30), default="")
    score_text: Mapped[str] = mapped_column(String(30), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    video_url: Mapped[str] = mapped_column(Text, default="")
    research_status: Mapped[str] = mapped_column(String(40), default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=50)
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class PlayerIntelligenceProfile(Base):
    __tablename__ = "player_intelligence_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    gender: Mapped[str] = mapped_column(String(20), default="Women")
    nationality: Mapped[str] = mapped_column(String(60), default="")
    role: Mapped[str] = mapped_column(String(100), default="Role to confirm")
    current_club: Mapped[str] = mapped_column(String(180), default="")
    current_national_team: Mapped[str] = mapped_column(String(180), default="")
    roster_status: Mapped[str] = mapped_column(String(60), default="research_required")
    roster_season: Mapped[str] = mapped_column(String(40), default="")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    primary_source_url: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class PlayerSourceRecord(Base):
    __tablename__ = "player_source_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("player_intelligence_profiles.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(50), default="web")
    label: Mapped[str] = mapped_column(String(220), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    season: Mapped[str] = mapped_column(String(40), default="")
    trust_level: Mapped[str] = mapped_column(String(40), default="secondary")
    claim_text: Mapped[str] = mapped_column(Text, default="")
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class PlayerMatchMetric(Base):
    __tablename__ = "player_match_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("player_intelligence_profiles.id"), index=True)
    library_match_id: Mapped[int | None] = mapped_column(ForeignKey("match_library_items.id"), nullable=True, index=True)
    metric: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_value: Mapped[str] = mapped_column(String(160), default="")
    unit: Mapped[str] = mapped_column(String(30), default="")
    provenance: Mapped[str] = mapped_column(String(40), default="official_report")
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    source_url: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class FranceSquadMembership(Base):
    __tablename__ = "france_squad_memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("player_intelligence_profiles.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    competition: Mapped[str] = mapped_column(String(180), default="")
    roster_kind: Mapped[str] = mapped_column(String(50), default="official")  # official / prelist / match_sheet
    club_at_event: Mapped[str] = mapped_column(String(180), default="")
    role_at_event: Mapped[str] = mapped_column(String(100), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")

class PlayerShotObservation(Base):
    __tablename__ = "player_shot_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("player_intelligence_profiles.id"), index=True)
    library_match_id: Mapped[int | None] = mapped_column(ForeignKey("match_library_items.id"), nullable=True, index=True)
    second: Mapped[float | None] = mapped_column(Float, nullable=True)
    pool_x: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1 length direction
    pool_y: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1 width direction
    goal_x: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1 goal width
    goal_y: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1 goal height
    outcome: Mapped[str] = mapped_column(String(40), default="unknown")  # goal/save/block/miss
    shot_context: Mapped[str] = mapped_column(String(60), default="unknown")
    shooter_side: Mapped[str] = mapped_column(String(40), default="unknown")
    provenance: Mapped[str] = mapped_column(String(40), default="ai_estimated")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    source_url: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
