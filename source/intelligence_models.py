from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from db import Base


class PlayerMatchEvaluation(Base):
    __tablename__ = "player_match_evaluations"
    __table_args__ = (UniqueConstraint("match_id", "player_id", name="uq_player_match_evaluation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    attack: Mapped[float | None] = mapped_column(Float, nullable=True)
    defence: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision: Mapped[float | None] = mapped_column(Float, nullable=True)
    tactics: Mapped[float | None] = mapped_column(Float, nullable=True)
    transition: Mapped[float | None] = mapped_column(Float, nullable=True)
    discipline: Mapped[float | None] = mapped_column(Float, nullable=True)
    technique: Mapped[float | None] = mapped_column(Float, nullable=True)
    impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    physical: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_label: Mapped[str] = mapped_column(String(40), default="INSUFFICIENT DATA")
    role_snapshot: Mapped[str] = mapped_column(String(100), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    strengths_json: Mapped[str] = mapped_column(Text, default="[]")
    improvements_json: Mapped[str] = mapped_column(Text, default="[]")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    engine_version: Mapped[str] = mapped_column(String(50), default="rating-v3")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class CoachIntelligenceProfile(Base):
    __tablename__ = "coach_intelligence_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(180), index=True)
    team_name: Mapped[str] = mapped_column(String(180), index=True)
    team_type: Mapped[str] = mapped_column(String(40), default="club")
    category: Mapped[str] = mapped_column(String(60), default="Women")
    role: Mapped[str] = mapped_column(String(100), default="Head coach")
    season: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(60), default="historical_confirmed")
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_tier: Mapped[str] = mapped_column(String(40), default="club_official")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    tactical_identity: Mapped[str] = mapped_column(Text, default="")
    evaluation_overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    tactical_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    game_management_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    special_teams_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    development_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def biography(self):
        # Kept outside the DB schema so historical enrichment can evolve without a migration.
        from services.coach_biography import coach_biography_for
        return coach_biography_for(self)
