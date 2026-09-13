from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class OfficialScorerStanding(Base):
    """Evidence-first scorer leaderboard row.

    This table is deliberately source-agnostic so federation parsers can progressively
    populate France, Spain, Italy, Hungary, Germany, Russia and any additional women's
    domestic championship AquaMetric follows. Empty/missing statistics are nullable and
    must never be converted to synthetic zeroes by the UI.
    """

    __tablename__ = "official_scorer_standings"
    __table_args__ = (
        UniqueConstraint(
            "competition", "season", "player_name", "team_name",
            name="uq_official_scorer_comp_season_player_team",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("official_data_sources.id"), nullable=True, index=True)
    competition: Mapped[str] = mapped_column(String(180), index=True)
    season: Mapped[str] = mapped_column(String(40), index=True)
    category: Mapped[str] = mapped_column(String(40), default="Women")
    country: Mapped[str] = mapped_column(String(80), default="")
    level: Mapped[str] = mapped_column(String(80), default="Elite")
    position: Mapped[int] = mapped_column(Integer, default=0)
    player_name: Mapped[str] = mapped_column(String(180), index=True)
    team_name: Mapped[str] = mapped_column(String(180), default="")
    goals: Mapped[int] = mapped_column(Integer, default=0)
    matches_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    penalties: Mapped[int | None] = mapped_column(Integer, nullable=True)
    non_penalty_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals_per_match: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_quality: Mapped[str] = mapped_column(String(50), default="official")
    coverage_label: Mapped[str] = mapped_column(String(80), default="official_published")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
