DEFENCE_PLAYBOOK = {
    "press": {
        "label":"Press defence",
        "defensive_goal":"Deny clean passing lanes, turn receivers away from goal and consume possession time.",
        "attack_counters":["Use disciplined drives to force switches and create separation.","Attack the weakest individual matchup after a controlled side-to-side circulation.","Use wet entry passes to the centre when front position is won; do not force dry entries through pressure.","Release early after a defender overcommits and use the next pass rather than holding the ball."],
        "defence_reply":["Maintain ball pressure before helping; a help without pressure opens the release pass.","Pre-call switches on drives and protect ball-side first.","If the centre matchup deteriorates, transition deliberately to the chosen drop rather than collapsing late."],
        "video_evidence_needed":["receiver body orientation","pass lane pressure","centre front position","switch timing"]
    },
    "drop_2_4": {
        "label":"2–4 / centre drop",
        "defensive_goal":"Protect the centre and concede selected perimeter decisions rather than high-value centre entries.",
        "attack_counters":["Move the ball before the drop is fully set and attack the recovering defender.","Use 2/3/4 arc movement and lateral passing to shift the drop and create a shooting seam.","Drive behind the dropping defender to punish ball-watching and force a switch.","Use the centre as a screen/occupier even when the direct entry is unavailable."],
        "defence_reply":["Drop on time, not after the centre has already sealed.","Keep the designated perimeter shot under a controlled block/goalkeeper plan.","Recover on flight of the pass; do not remain sunk after the ball changes side."],
        "video_evidence_needed":["drop origin","centre seal","weak-side gap","shot lane conceded"]
    },
    "m_zone": {
        "label":"M-zone",
        "defensive_goal":"Keep one defender protecting the centre while split defenders control three perimeter attackers and shooting lanes.",
        "attack_counters":["Stretch the split with width and fast reversals; avoid static perimeter possession.","Drive through the seam created when a splitter turns to the ball.","Use a high-post or pop movement to make the zoned defender choose between centre protection and the passing lane."],
        "defence_reply":["The zoned defender stays disciplined; split defenders piston with ball movement.","Outside defenders pick up top drives and communicate the exchange early.","Funnel the final shot toward the goalkeeper's planned side."],
        "video_evidence_needed":["split spacing","piston timing","drive pickup","goalkeeper funnel"]
    },
    "zone_3_4": {
        "label":"3–4 two-player zone",
        "defensive_goal":"Two defenders cooperate to deny centre entry and close central shooting lines while still pressuring the ball.",
        "attack_counters":["Reverse quickly between 3 and 4 to move the two-person zone.","Use a wing attack or drive when both zoners become narrow.","Create a double-threat receiver so the defender cannot both block and deny entry."],
        "defence_reply":["Piston: the ball-side defender advances while the partner protects the centre.","Do not let both zoners attack the same fake.","Recover to balanced spacing after every reversal."],
        "video_evidence_needed":["two-player spacing","ball-side advance","centre denial","wing exposure"]
    },
    "5v6_cluster": {
        "label":"5-on-6 compact / cluster",
        "defensive_goal":"Protect high-value near-goal spaces, layer blocks and funnel shots to the goalkeeper.",
        "attack_counters":["Change the point of attack faster than the block rotation.","Use post-to-post or diagonal passes only when the lane is genuinely open; value the extra pass over a low-quality forced shot.","Shift between 4-2 and 3-3 shapes according to personnel and defender response."],
        "defence_reply":["Rotate on ball flight, not after reception.","Preserve double-block responsibilities where planned and avoid opening the post unnecessarily.","Goalkeeper and field blocks must agree on the side being conceded."],
        "video_evidence_needed":["rotation delay","double block","post exposure","goalkeeper sightline"]
    },
}


def recommend_counter_plan(defence_key, evidence=None):
    p=DEFENCE_PLAYBOOK.get(defence_key) or DEFENCE_PLAYBOOK["press"]
    evidence=evidence or {}
    confidence="LOW"
    facts=sum(bool(v) for v in evidence.values())
    if facts>=4: confidence="HIGH"
    elif facts>=2: confidence="MODERATE"
    return {**p,"key":defence_key,"confidence":confidence,"observed":evidence,"principle":"Treat this as a decision tree, not a guaranteed play call: choose the branch supported by the current spacing, personnel, clock and score state."}
