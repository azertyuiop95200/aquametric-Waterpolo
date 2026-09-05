"""Evidence-first France Elite women roster updates from direct podcast evidence.

La Pointe is treated as a media/direct-interview source, not as federation registration
proof. Named, explicit claims may update a current roster state while full squads remain
pending club or FFN match-sheet confirmation. Unnamed mercato claims are never converted
into players or transfers.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from intelligence_models import CoachIntelligenceProfile
from models import (
    PlayerIntelligenceProfile,
    PlayerSourceRecord,
    ScoutingPlayer,
    ScoutingTeam,
    SourceWatch,
    TransferSignal,
)


LA_POINTE_E101_EMA = (
    "https://podcasts.apple.com/fr/podcast/"
    "e101-replay-ema-vernoux-welcome-back/id1767312237?i=1000783982801"
)
LA_POINTE_E103_MARSEILLE = (
    "https://podcasts.apple.com/fr/podcast/"
    "e103-le-cn-marseille-f%C3%A9minin-bouscule-l%C3%A9lite-r%C3%A9v%C3%A9lations/"
    "id1767312237?i=1000787108990"
)
MARSEILLE_KEY = "club-fr-marseille-w-elite"
MARSEILLE_NAME = "Cercle des Nageurs de Marseille"
SEASON = "2026-2027"


def _append_once(current: str, addition: str) -> str:
    current = (current or "").strip()
    addition = (addition or "").strip()
    if not addition or addition in current:
        return current
    return f"{current} {addition}".strip()


def _upsert_source_watch(db):
    name = "La Pointe — mercato water-polo féminin français"
    row = db.scalar(select(SourceWatch).where(SourceWatch.name == name))
    if not row:
        row = SourceWatch(name=name)
        db.add(row)
    row.source_type = "media"
    row.platform = "podcast"
    row.entity_scope = "France — Elite Féminine / effectifs / mercato"
    row.url = LA_POINTE_E103_MARSEILLE
    row.trust_level = "media_direct_interview"
    row.refresh_hours = 24
    row.enabled = True
    row.last_status = "seeded"
    row.note = (
        "Direct-interview and specialist-media discovery source. Named explicit claims may be "
        "used as media-confirmed roster evidence, but full squads and registration status remain "
        "pending club/FFN corroboration. Unnamed 'mercato XXL' claims are not converted into players."
    )
    row.updated_at = datetime.now(timezone.utc)
    return row


def _upsert_ema_transfer(db):
    row = db.scalar(
        select(TransferSignal).where(
            TransferSignal.player_name == "Ema Vernoux",
            TransferSignal.to_team == "CN Marseille",
            TransferSignal.season == SEASON,
        )
    )
    if not row:
        row = TransferSignal(
            player_name="Ema Vernoux",
            to_team="CN Marseille",
            season=SEASON,
        )
        db.add(row)
    row.gender = "Women"
    row.from_team = "University of Hawai'i"
    row.signal_type = "confirmed"
    row.published_date = "2026-08-18"
    row.source_name = "La Pointe — E101 Ema Vernoux Welcome Back"
    row.source_url = LA_POINTE_E101_EMA
    row.source_tier = "media_direct_interview"
    row.confidence_score = 0.97
    row.note = (
        "La Pointe E101 explicitly states that Ema Vernoux returns to Marseille to join the "
        "Cercle des Nageurs women's Elite project after her US college spell. The previous "
        "University of Hawai'i affiliation is independently documented by FFN/Hawai'i records. "
        "This is a named transfer claim, not a claim that Marseille's full roster is confirmed."
    )
    return row


def _upsert_marseille_scouting(db):
    team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == MARSEILLE_KEY))
    if not team:
        return None

    team.roster_status = "partial_current_media_confirmed_pending_ffn_match_sheet"
    team.source_note = _append_once(
        team.source_note,
        "Ema Vernoux's return to Marseille for the women's Elite project is explicitly announced "
        "by La Pointe E101 (18 Aug 2026). La Pointe E103 identifies Yann Vernoux as leading the "
        "new women's team and describes major market activity. The rest of the current roster "
        "remains pending named club/FFN evidence; unnamed podcast claims are not inserted as players.",
    )
    team.updated_at = datetime.now(timezone.utc)

    player = db.scalar(
        select(ScoutingPlayer).where(
            ScoutingPlayer.scouting_team_id == team.id,
            ScoutingPlayer.name == "Ema Vernoux",
        )
    )
    if not player:
        player = ScoutingPlayer(scouting_team_id=team.id, name="Ema Vernoux")
        db.add(player)
    player.cap_number = None
    player.birth_year = 2004
    player.nationality = "FRA"
    player.role = "Winger / demi"
    player.source_season = SEASON
    player.source_url = LA_POINTE_E101_EMA
    player.source_quality = "media_direct_interview"
    player.current_status = "current_media_confirmed_pending_ffn_match_sheet"
    player.note = (
        "Named current-roster signal: La Pointe E101 states Ema Vernoux is returning to Marseille "
        "to join the CN Marseille women's Elite project. Registration/full squad still awaits FFN "
        "match-sheet or club roster confirmation."
    )
    return team


def _upsert_ema_profile(db):
    profile = db.scalar(
        select(PlayerIntelligenceProfile).where(
            PlayerIntelligenceProfile.canonical_name == "Ema Vernoux"
        )
    )
    if not profile:
        profile = PlayerIntelligenceProfile(canonical_name="Ema Vernoux", gender="Women")
        db.add(profile)
        db.flush()

    profile.nationality = profile.nationality or "FRA"
    profile.role = "Winger / demi"
    profile.current_club = MARSEILLE_NAME
    profile.current_national_team = profile.current_national_team or "France — Women Senior"
    profile.roster_status = "media_direct_interview_current_pending_ffn_match_sheet"
    profile.roster_season = SEASON
    profile.confidence_score = max(float(profile.confidence_score or 0), 0.97)
    profile.primary_source_url = LA_POINTE_E101_EMA
    profile.note = _append_once(
        profile.note,
        "Current-club update: La Pointe E101 explicitly announces her return to Marseille for the "
        "CN Marseille women's Elite project; official FFN/club match-sheet confirmation remains pending.",
    )
    db.flush()

    source = db.scalar(
        select(PlayerSourceRecord).where(
            PlayerSourceRecord.profile_id == profile.id,
            PlayerSourceRecord.url == LA_POINTE_E101_EMA,
            PlayerSourceRecord.label == "Current club evidence — CN Marseille 2026-27",
        )
    )
    if not source:
        source = PlayerSourceRecord(
            profile_id=profile.id,
            source_type="podcast_direct_interview",
            label="Current club evidence — CN Marseille 2026-27",
            url=LA_POINTE_E101_EMA,
            season=SEASON,
            trust_level="media_direct_interview",
            claim_text=(
                "La Pointe E101 explicitly states that Ema Vernoux returns to Marseille to join "
                "the Cercle des Nageurs women's Elite project."
            ),
        )
        db.add(source)
    return profile


def _upsert_yann_vernoux(db):
    row = db.scalar(
        select(CoachIntelligenceProfile).where(
            CoachIntelligenceProfile.canonical_name == "Yann Vernoux",
            CoachIntelligenceProfile.team_name == MARSEILLE_NAME,
            CoachIntelligenceProfile.season == SEASON,
        )
    )
    if not row:
        row = CoachIntelligenceProfile(
            canonical_name="Yann Vernoux",
            team_name=MARSEILLE_NAME,
            team_type="club",
            category="Women Senior",
            role="Head coach — Elite Féminine",
            season=SEASON,
        )
        db.add(row)
    row.team_type = "club"
    row.category = "Women Senior"
    row.role = "Head coach — Elite Féminine"
    row.status = "media_direct_interview_current_pending_club_or_ffn_confirmation"
    row.source_url = LA_POINTE_E103_MARSEILLE
    row.source_tier = "media_direct_interview"
    row.confidence_score = 0.97
    row.tactical_identity = (
        "La Pointe E103 identifies Yann Vernoux as being in charge of the newly created CN Marseille "
        "women's team and discusses the sporting project for Elite and Europe. No tactical performance "
        "score is inferred from the interview description alone."
    )
    row.note = (
        "Current assignment is directly stated in La Pointe E103's episode description/interview context. "
        "A club or FFN match-sheet source is still required before upgrading the source tier to official."
    )
    row.updated_at = datetime.now(timezone.utc)
    return row


def seed_france_women_roster_update_2026(db):
    """Apply named La Pointe roster intelligence without promoting unnamed rumours."""
    _upsert_source_watch(db)
    _upsert_ema_transfer(db)
    _upsert_marseille_scouting(db)
    _upsert_ema_profile(db)
    _upsert_yann_vernoux(db)
    db.commit()
