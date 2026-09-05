from sqlalchemy import func, select

# Importing the application executes the normal seed chain used in production/CI.
# The tests below then verify that the La Pointe updater is both correct and idempotent.
from main import app as _app  # noqa: F401
from db import SessionLocal
from intelligence_models import CoachIntelligenceProfile
from models import (
    PlayerIntelligenceProfile,
    PlayerSourceRecord,
    ScoutingPlayer,
    ScoutingTeam,
    SourceWatch,
    TransferSignal,
)
from services.france_women_roster_update_2026 import (
    LA_POINTE_E101_EMA,
    LA_POINTE_E103_MARSEILLE,
    MARSEILLE_KEY,
    MARSEILLE_NAME,
    SEASON,
    seed_france_women_roster_update_2026,
)


def test_la_pointe_updates_marseille_without_claiming_full_roster():
    db = SessionLocal()
    try:
        seed_france_women_roster_update_2026(db)

        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == MARSEILLE_KEY))
        assert team is not None
        assert team.roster_status == "partial_current_media_pending_ffn"
        assert "rest of the current roster" in team.source_note
        assert "unnamed podcast claims are not inserted as players" in team.source_note

        ema = db.scalar(
            select(ScoutingPlayer).where(
                ScoutingPlayer.scouting_team_id == team.id,
                ScoutingPlayer.name == "Ema Vernoux",
            )
        )
        assert ema is not None
        assert ema.source_season == SEASON
        assert ema.source_url == LA_POINTE_E101_EMA
        assert ema.source_quality == "media_direct_interview"
        assert ema.current_status == "current_media_confirmed_pending_ffn"
    finally:
        db.close()


def test_ema_current_club_is_updated_but_official_history_is_preserved():
    db = SessionLocal()
    try:
        seed_france_women_roster_update_2026(db)
        profile = db.scalar(
            select(PlayerIntelligenceProfile).where(
                PlayerIntelligenceProfile.canonical_name == "Ema Vernoux"
            )
        )
        assert profile is not None
        assert profile.current_club == MARSEILLE_NAME
        assert profile.roster_season == SEASON
        assert profile.roster_status == "current_media_direct_pending_ffn"

        sources = db.scalars(
            select(PlayerSourceRecord).where(PlayerSourceRecord.profile_id == profile.id)
        ).all()
        assert any(source.url == LA_POINTE_E101_EMA for source in sources)
        # The older FFN/official national-team evidence must remain alongside the new club update.
        assert any("ffnatation.fr" in (source.url or "") for source in sources)
    finally:
        db.close()


def test_ema_transfer_and_yann_coach_are_named_direct_evidence_only():
    db = SessionLocal()
    try:
        seed_france_women_roster_update_2026(db)

        transfer = db.scalar(
            select(TransferSignal).where(
                TransferSignal.player_name == "Ema Vernoux",
                TransferSignal.to_team == "CN Marseille",
                TransferSignal.season == SEASON,
            )
        )
        assert transfer is not None
        assert transfer.from_team == "University of Hawai'i"
        assert transfer.signal_type == "confirmed"
        assert transfer.source_tier == "media_direct_interview"
        assert transfer.source_url == LA_POINTE_E101_EMA

        coach = db.scalar(
            select(CoachIntelligenceProfile).where(
                CoachIntelligenceProfile.canonical_name == "Yann Vernoux",
                CoachIntelligenceProfile.team_name == MARSEILLE_NAME,
                CoachIntelligenceProfile.season == SEASON,
            )
        )
        assert coach is not None
        assert coach.role == "Head coach — Elite Féminine"
        assert coach.status == "current_media_direct_pending_official"
        assert coach.source_tier == "media_direct_interview"
        assert coach.source_url == LA_POINTE_E103_MARSEILLE

        la_pointe_transfers = db.scalars(
            select(TransferSignal).where(TransferSignal.source_name.like("La Pointe%"))
        ).all()
        assert [row.player_name for row in la_pointe_transfers] == ["Ema Vernoux"]
    finally:
        db.close()


def test_la_pointe_seed_is_idempotent():
    db = SessionLocal()
    try:
        seed_france_women_roster_update_2026(db)
        seed_france_women_roster_update_2026(db)

        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == MARSEILLE_KEY))
        assert team is not None
        assert db.scalar(
            select(func.count(ScoutingPlayer.id)).where(
                ScoutingPlayer.scouting_team_id == team.id,
                ScoutingPlayer.name == "Ema Vernoux",
            )
        ) == 1
        assert db.scalar(
            select(func.count(TransferSignal.id)).where(
                TransferSignal.player_name == "Ema Vernoux",
                TransferSignal.to_team == "CN Marseille",
                TransferSignal.season == SEASON,
            )
        ) == 1
        assert db.scalar(
            select(func.count(CoachIntelligenceProfile.id)).where(
                CoachIntelligenceProfile.canonical_name == "Yann Vernoux",
                CoachIntelligenceProfile.team_name == MARSEILLE_NAME,
                CoachIntelligenceProfile.season == SEASON,
            )
        ) == 1
        assert db.scalar(
            select(func.count(SourceWatch.id)).where(
                SourceWatch.name == "La Pointe — mercato water-polo féminin français"
            )
        ) == 1
    finally:
        db.close()
