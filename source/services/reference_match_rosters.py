from __future__ import annotations

"""Compatibility shim for historical match-roster calls.

AquaMetric used to preload a user-supplied roster for one reference video. That
is intentionally disabled: player names and cap numbers must now come from the
video analysis itself. Existing callers can keep importing these helpers while
they are migrated, but they always receive no identity evidence.
"""

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


REFERENCE_VIDEO_ID = "Guo_UU282pI"


@dataclass(frozen=True)
class MatchRosterCandidate:
    side: str
    cap_number: int
    player_name: str
    role: str = ""
    cap_color: str = ""
    source: str = "disabled_manual_reference"


# Deliberately empty. User-supplied names/numbers are context only and must not
# be injected into Vision, reports, or cap-number identification.
_REFERENCE_ROSTERS: dict[str, tuple[MatchRosterCandidate, ...]] = {}


def video_id(url: str | None) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    host = parsed.netloc.lower().split(":", 1)[0]
    if host.endswith("youtu.be"):
        return parsed.path.strip("/").split("/", 1)[0]
    if "youtube.com" in host:
        return (parse_qs(parsed.query).get("v") or [""])[0]
    return ""


def roster_for_video(url: str | None) -> tuple[MatchRosterCandidate, ...]:
    # Never turn a manually supplied roster into analysis evidence.
    return ()


def cap_candidates(url: str | None, side: str, cap_number: int) -> tuple[str, ...]:
    # Identity must be resolved from visual/temporal tracking, not a cap lookup.
    return ()


def roster_payload(url: str | None) -> list[dict]:
    # Historical templates/routes may still call this until fully removed.
    return []
