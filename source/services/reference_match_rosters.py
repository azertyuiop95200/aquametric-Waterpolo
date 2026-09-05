from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


REFERENCE_VIDEO_ID = "Guo_UU282pI"


@dataclass(frozen=True)
class MatchRosterCandidate:
    side: str
    cap_number: int
    player_name: str
    source: str = "user_match_reference"


_REFERENCE_ROSTERS: dict[str, tuple[MatchRosterCandidate, ...]] = {
    REFERENCE_VIDEO_ID: (
        MatchRosterCandidate("for", 1, "Rumina"),
        MatchRosterCandidate("for", 2, "Morgane"),
        MatchRosterCandidate("for", 3, "Capu"),
        MatchRosterCandidate("for", 4, "Cléo"),
        MatchRosterCandidate("for", 5, "Luce"),
        MatchRosterCandidate("for", 6, "Sofia"),
        MatchRosterCandidate("for", 7, "Amandine"),
        MatchRosterCandidate("for", 8, "Suzanne"),
        MatchRosterCandidate("for", 9, "Clémence"),
        MatchRosterCandidate("for", 10, "Mauranne"),
        MatchRosterCandidate("for", 11, "Veronika"),
        MatchRosterCandidate("for", 12, "Hitomi"),
        MatchRosterCandidate("for", 12, "Hanae"),
        MatchRosterCandidate("for", 13, "Maëlle"),
        MatchRosterCandidate("for", 13, "Clara"),
        MatchRosterCandidate("for", 14, "Charlotte"),
    )
}


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
    return _REFERENCE_ROSTERS.get(video_id(url), ())


def cap_candidates(url: str | None, side: str, cap_number: int) -> tuple[str, ...]:
    side = (side or "for").strip().lower()
    return tuple(
        row.player_name
        for row in roster_for_video(url)
        if row.side == side and row.cap_number == int(cap_number)
    )


def roster_payload(url: str | None) -> list[dict]:
    rows = roster_for_video(url)
    cap_counts: dict[tuple[str, int], int] = {}
    for row in rows:
        key = (row.side, row.cap_number)
        cap_counts[key] = cap_counts.get(key, 0) + 1
    return [
        {
            "side": row.side,
            "cap_number": row.cap_number,
            "player_name": row.player_name,
            "ambiguous_cap": cap_counts[(row.side, row.cap_number)] > 1,
            "source": row.source,
        }
        for row in rows
    ]
