from __future__ import annotations

import re

_ALLOWED_SIDES = {"for", "against", "neutral"}
_CAP_RE = re.compile(r"(?:^|[\s;|])(?:cap|cap_number)\s*=\s*(\d{1,2})(?=$|[\s;|])", re.I)
_TRACK_RE = re.compile(r"(?:^|[\s;|])(?:track|track_id)\s*=\s*([A-Za-z0-9._-]{1,80})(?=$|[\s;|])", re.I)


def normalize_side(value: str | None) -> str:
    side = (value or "for").strip().lower()
    return side if side in _ALLOWED_SIDES else "neutral"


def _track_token(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "ambiguous"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_")
    return safe[:80] or "ambiguous"


def cap_identity_key(
    match_id: int,
    side: str | None,
    cap_number: int | str | None,
    track_id: str | None = None,
) -> str:
    """Return a collision-safe identity for a cap sighting inside one match.

    A cap number is not a player identity. Opposing teams can share the same number,
    and friendly matches can even use the same number for multiple players on the
    same team. Therefore an unresolved cap sighting is explicitly marked ambiguous.
    A visual tracker id may refine that group into a stable in-match identity.
    """
    try:
        cap = int(cap_number) if cap_number is not None else None
    except (TypeError, ValueError):
        cap = None
    if cap is None or not 0 <= cap <= 99:
        cap_token = "unknown"
    else:
        cap_token = str(cap)
    return (
        f"m{int(match_id)}:{normalize_side(side)}:cap:{cap_token}:"
        f"track:{_track_token(track_id)}"
    )


def event_identity_key(event) -> str:
    """Build the strongest safe identity available for a tagged event.

    A database player id wins when available. Otherwise an explicit cap=NN tag is
    combined with the event perspective and, when present, an explicit track=... tag.
    Without a track/player id the result remains deliberately ambiguous and must not
    be promoted to an individual player's statistics.
    """
    match_id = int(getattr(event, "match_id", 0) or 0)
    meta = getattr(event, "context_meta", None)
    side = normalize_side(getattr(meta, "perspective", "for") if meta else "for")
    player_id = getattr(event, "player_id", None)
    if player_id:
        return f"m{match_id}:{side}:player:{int(player_id)}"
    note = getattr(event, "note", "") or ""
    cap_match = _CAP_RE.search(note)
    track_match = _TRACK_RE.search(note)
    return cap_identity_key(
        match_id,
        side,
        cap_match.group(1) if cap_match else None,
        track_match.group(1) if track_match else None,
    )
