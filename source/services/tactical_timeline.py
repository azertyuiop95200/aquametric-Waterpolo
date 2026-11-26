"""Provisional possession state, only inside one continuous observed segment."""
from collections import Counter

def tactical_timeline(events):
    result=[]; attacking=None; segment=None; period=None
    for e in sorted(events,key=lambda e:(e.get("segment_index",0),e["second"])):
        kind=e["event_type"]; side=e.get("side","unknown"); q=e.get("period")
        current=e.get("segment_index")
        if current!=segment or (q is not None and period is not None and q!=period):
            attacking=None
        segment=current
        if q is not None:period=q
        before=attacking
        if kind=="possession_start":
            attacking=side if side in ("for","against") else None
        elif kind in ("possession_end","goal"):
            attacking=None
        # A pass/shot does not independently establish who controls the ball
        # in the rest of the segment. Never derive possession from cap colour.
        if kind in ("possession_start","possession_end","goal","shot_on_target","shot_off_target","shot_blocked","assist","key_pass","pass_complete","bad_pass","interception","save","exclusion_earned","exclusion_committed","penalty_earned","penalty_committed"):
            result.append({"second":e["second"],"period":q,"segment":current,"event_type":kind,
                           "actor_side":side,"cap_number":e.get("cap_number"),
                           "attack_before":before,"attack_after":attacking,
                           "defence_after":({"for":"against","against":"for"}.get(attacking)),
                           "game_clock_seconds":e.get("game_clock_seconds"),
                           "shot_clock_seconds":e.get("shot_clock_seconds"),
                           "outcome":e.get("possession_outcome","unknown")})
    return result
