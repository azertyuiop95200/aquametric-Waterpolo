"""One evidence gate for match, player, tactical and rating calculations."""


def verified_events(events):
    return [event for event in events or []
            if str(getattr(event, "confidence", "CONFIRMED") or "").upper()
            in {"CONFIRMED", "VERIFIED"}]
