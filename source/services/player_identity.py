from __future__ import annotations

import re

_ALLOWED_SIDES = {"for", "against", "neutral"}
_CAP_RE = re.compile(r"(?:^|[\s;|])(?:cap|cap_number)\s*=\s*(\d{1,2})(?=$|[\s;|])", re.I)


def normalize_side(value: str | None) -> str:
    side = (value or "for").strip().lower()
    return side if side in _ALLOWED_SIDES else "neutral"


def cap_identity_key(match_id: int, side: str | None, cap_number: int | str | None) -> str:
    """Return a collision-safe identity for a cap sighting inside one match.

    Water-polo cap numbers are only unique *within one team*. A white #7 and a
    dark #7 must therefore never collapse into the same identity. The side is
    part of the key by construction.
    """
    try:
        cap = int(cap_number) if cap_number is not None else None
    except (TypeError, ValueError):
        cap = None
    if cap is None or not 0 <= cap <= 99:
        cap_token = "unknown"
    else:
        cap_token = str(cap)
    return f"m{int(match_id)}:{normalize_side(side)}:cap:{cap_token}"


def event_identity_key(event) -> str:
    """Build the strongest safe identity available for a tagged event.

    A database player id wins when available. Otherwise an explicit cap=NN tag
    is used together with the event perspective. No inference from a bare number
    in free text is attempted.
    """
    match_id = int(getattr(event, "match_id", 0) or 0)
    meta = getattr(event, "context_meta", None)
    side = normalize_side(getattr(meta, "perspective", "for") if meta else "for")
    player_id = getattr(event, "player_id", None)
    if player_id:
        return f"m{match_id}:{side}:player:{int(player_id)}"
    note = getattr(event, "note", "") or ""
    match = _CAP_RE.search(note)
    return cap_identity_key(match_id, side, match.group(1) if match else None)
