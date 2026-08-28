"""Transfer-watch compatibility layer with the expanded 2026-27 market catalogue."""

from services.transfer_watch_core import *  # noqa: F401,F403
from services import transfer_watch_core as _core
from services.transfer_market_2026 import (
    EXTRA_TRANSFER_SIGNALS,
    OA_MEN_URL,
    OA_WOMEN_URL,
    HA10_AUG_URL,
)
from services.transfer_market_2026_wave2 import WAVE2_TRANSFER_SIGNALS, JUG_SIMIC_URL

# Keep the original seed/deduplication engine intact, but feed it the broader
# catalogue. Import happens once per process, so the extension is deterministic.
_core.TRANSFER_SIGNALS.extend(EXTRA_TRANSFER_SIGNALS)
_core.TRANSFER_SIGNALS.extend(WAVE2_TRANSFER_SIGNALS)
TRANSFER_SIGNALS = _core.TRANSFER_SIGNALS

_EXTRA_SOURCE_WATCHES = [
    ("OA Sport — A1 men mercato 2026-27", "media", "web", "Italy — Serie A1 men", OA_MEN_URL, "media", 12, "Club-by-club 2026-27 arrivals, departures and retirements; reported evidence until upgraded by club/federation sources."),
    ("OA Sport — A1 women mercato 2026-27", "media", "web", "Italy — Serie A1 women", OA_WOMEN_URL, "media", 12, "Club-by-club 2026-27 arrivals, departures and retirements; reported evidence until upgraded by club/federation sources."),
    ("HA10 / LEWaterpolo — Spain mercato", "league_media", "web", "Spain — División de Honor women and men", HA10_AUG_URL, "media", 12, "Relays LEWaterpolo summer-market/new-faces coverage; cross-check with clubs and RFEN when available."),
    ("VK Jug — official news", "club_official", "web", "VK Jug Dubrovnik", JUG_SIMIC_URL, "primary", 12, "Official club announcements and current first-team roster changes."),
]
_existing_source_names = {row[0] for row in _core.SOURCE_WATCHES}
_core.SOURCE_WATCHES.extend(row for row in _EXTRA_SOURCE_WATCHES if row[0] not in _existing_source_names)
SOURCE_WATCHES = _core.SOURCE_WATCHES
