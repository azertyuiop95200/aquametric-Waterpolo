"""Transfer-watch compatibility layer with expanded European and NCAA market data."""

from sqlalchemy import select

from models import TransferSignal
from services.transfer_watch_core import *  # noqa: F401,F403
from services import transfer_watch_core as _core
from services.transfer_market_2026 import (
    EXTRA_TRANSFER_SIGNALS,
    OA_MEN_URL,
    OA_WOMEN_URL,
    HA10_AUG_URL,
)
from services.transfer_market_2026_wave2 import WAVE2_TRANSFER_SIGNALS, JUG_SIMIC_URL
from services.transfer_market_2026_wave3 import WAVE3_TRANSFER_SIGNALS
from services.transfer_market_2026_wave4_france import WAVE4_FRANCE_SIGNALS, MWP_PUBLIC
from services.transfer_market_ncaa_2026 import NCAA_2026_TRANSFER_SIGNALS


def _signal_key(item):
    return (
        item.get("gender", ""), item.get("player", ""), item.get("from", ""),
        item.get("to", ""), item.get("date", ""), item.get("source", ""),
        item.get("season", _core.TRANSFER_SEASON),
    )


def _extend_unique(rows):
    """Avoid multiplying static datasets if this compatibility module is reloaded."""
    existing = {_signal_key(item) for item in _core.TRANSFER_SIGNALS}
    for item in rows:
        key = _signal_key(item)
        if key not in existing:
            _core.TRANSFER_SIGNALS.append(item)
            existing.add(key)


# Keep the original seed/deduplication engine intact and feed it broader datasets.
_extend_unique(EXTRA_TRANSFER_SIGNALS)
_extend_unique(WAVE2_TRANSFER_SIGNALS)
_extend_unique(WAVE3_TRANSFER_SIGNALS)
_extend_unique(WAVE4_FRANCE_SIGNALS)
_extend_unique(NCAA_2026_TRANSFER_SIGNALS)
TRANSFER_SIGNALS = _core.TRANSFER_SIGNALS

_EXTRA_SOURCE_WATCHES = [
    ("OA Sport — A1 men mercato 2026-27", "media", "web", "Italy — Serie A1 men", OA_MEN_URL, "media", 12, "Club-by-club 2026-27 arrivals, departures and retirements; reported evidence until upgraded by club/federation sources."),
    ("OA Sport — A1 women mercato 2026-27", "media", "web", "Italy — Serie A1 women", OA_WOMEN_URL, "media", 12, "Club-by-club 2026-27 arrivals, departures and retirements; reported evidence until upgraded by club/federation sources."),
    ("HA10 / LEWaterpolo — Spain mercato", "league_media", "web", "Spain — División de Honor women and men", HA10_AUG_URL, "media", 12, "Relays LEWaterpolo summer-market/new-faces coverage; cross-check with clubs and RFEN when available."),
    ("VK Jug — official news", "club_official", "web", "VK Jug Dubrovnik", JUG_SIMIC_URL, "primary", 12, "Official club announcements and current first-team roster changes."),
    ("CN Sabadell — official water polo", "club_official", "web", "CN Sabadell women and men", "https://nataciosabadell.es/seccio-waterpolo/", "primary", 12, "Official club water-polo section; use for roster validation and cross-checking announced signings/exits."),
    ("CN Terrassa — official water polo", "club_official", "web", "CN Terrassa women and men", "https://clubnatacioterrassa.cat/", "primary", 12, "Official club site for 2026-27 signings, roster continuity and competition context."),
    ("Montpellier Water-Polo — public club feed", "club_social", "instagram", "Montpellier Water-Polo", MWP_PUBLIC, "club_public", 6, "Public club feed embedded on the official shop; useful for explicit signing and farewell announcements."),
    ("UCLA Water Polo — official athletics", "team_official", "web", "NCAA — UCLA women and men", "https://uclabruins.com/sports/water-polo", "primary", 12, "Official UCLA rosters and season previews; primary source for NCAA transfer arrivals."),
    ("USC Water Polo — official athletics", "team_official", "web", "NCAA — USC women and men", "https://usctrojans.com/", "primary", 12, "Official USC roster and season news; primary source for collegiate transfers."),
    ("Stanford Water Polo — official athletics", "team_official", "web", "NCAA — Stanford women and men", "https://gostanford.com/", "primary", 12, "Official Stanford transfer announcements and current rosters."),
]
_existing_source_names = {row[0] for row in _core.SOURCE_WATCHES}
_core.SOURCE_WATCHES.extend(row for row in _EXTRA_SOURCE_WATCHES if row[0] not in _existing_source_names)
SOURCE_WATCHES = _core.SOURCE_WATCHES


def _apply_explicit_signal_seasons(db):
    """Move explicitly-seasoned signals out of the default European market season.

    The core seeder predates calendar-year NCAA seasons and initially processes every
    item under 2026-27. This pass makes `item['season']` authoritative, merges any
    transient duplicate created by a later application restart, and preserves the
    strongest evidence. It works for any future non-default market season, not just NCAA.
    """
    for item in TRANSFER_SIGNALS:
        item_season = item.get("season")
        if not item_season or item_season == _core.TRANSFER_SEASON:
            continue

        candidates = db.scalars(
            select(TransferSignal).where(
                TransferSignal.player_name == item["player"],
                TransferSignal.to_team == item["to"],
                TransferSignal.season.in_([_core.TRANSFER_SEASON, item_season]),
            ).order_by(TransferSignal.id.asc())
        ).all()
        if not candidates:
            continue

        correctly_seasoned = [row for row in candidates if row.season == item_season]
        signal = correctly_seasoned[0] if correctly_seasoned else candidates[0]
        signal.season = item_season
        signal.gender = item["gender"]
        signal.from_team = item["from"] or signal.from_team
        signal.to_team = item["to"]
        dates = [date for date in (signal.published_date, item["date"]) if date]
        signal.published_date = min(dates) if dates else item["date"]
        if _core._rank(item["kind"]) >= _core._rank(signal.signal_type):
            signal.signal_type = item["kind"]
        if item["confidence"] >= float(signal.confidence_score or 0):
            signal.source_name = item["source"]
            signal.source_url = item["url"]
            signal.source_tier = item["tier"]
            signal.confidence_score = item["confidence"]
        signal.note = _core._append_note(signal.note, item.get("note", ""))

        for duplicate in candidates:
            if duplicate is signal:
                continue
            signal.note = _core._append_note(signal.note, duplicate.note)
            db.delete(duplicate)

    db.commit()


def seed_transfer_watch(db):
    _core.seed_transfer_watch(db)
    _apply_explicit_signal_seasons(db)
