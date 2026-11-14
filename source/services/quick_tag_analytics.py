"""Water-polo review desk metrics from explicitly verified action tags.

Never confuse a partially tagged sample with a full-match total.
A goal is a shot outcome: only one tag should be recorded for that attempt.
"""
from __future__ import annotations
from collections import defaultdict

SHOT_OUTCOMES={"goal","shot_on_target","shot_off_target","shot_blocked"}
LABELS={
 "goal":"But","shot_on_target":"Tir cadré sans but","shot_off_target":"Tir non cadré",
 "shot_blocked":"Tir bloqué","save":"Arrêt","turnover":"Perte de balle",
 "bad_pass":"Mauvaise passe","interception":"Interception","recovery":"Récupération",
 "assist":"Passe décisive","exclusion_earned":"Exclusion obtenue",
 "exclusion_committed":"Exclusion concédée","key_pass":"Passe clé","block":"Contre",
}


def _side(rows):
    goals=sum(e.get("event_type")=="goal" for e in rows)
    shots=sum(e.get("event_type") in SHOT_OUTCOMES for e in rows)
    saves=sum(e.get("event_type")=="save" for e in rows)
    turnovers=sum(e.get("event_type") in {"turnover","bad_pass"} for e in rows)
    return {
        "tagged_events":len(rows),
        "tagged_goals":goals,
        "tagged_shots":shots,
        "tagged_saves":saves,
        "tagged_turnovers":turnovers,
        "tagged_exclusions_earned":sum(e.get("event_type")=="exclusion_earned" for e in rows),
        "tagged_exclusions_committed":sum(e.get("event_type")=="exclusion_committed" for e in rows),
        "shot_conversion_pct":round(100*goals/shots,1) if shots else None,
    }


def reviewed_match_metrics(events: list[dict], video_url="") -> dict:
    from services.video import timestamped_video_url
    confirmed=[e for e in events if str(e.get("confidence") or "").upper() in {"CONFIRMED","VERIFIED"}]
    sides={}
    for label in ("for","against"):
        rows=[e for e in confirmed if e.get("perspective")==label]
        sides[label]=_side(rows)
    by_phase={}
    for phase,label in [("even_attack","6 contre 6"),("power_play","Supériorité numérique"),("counterattack","Contre-attaque")]:
        rows=[e for e in confirmed if e.get("phase")==phase]
        by_phase[phase]={"label":label,"for":_side([e for e in rows if e.get("perspective")=="for"]),
                         "against":_side([e for e in rows if e.get("perspective")=="against"])}
    by_player=defaultdict(list)
    for e in confirmed:
        if e.get("player_id") and e.get("perspective")=="for":
            by_player[(e.get("player_id"),e.get("player") or "Inconnue")].append(e)
    players=[{"name":name,"player_id":pid,**_side(rows)}
             for (pid,name),rows in by_player.items()]
    players.sort(key=lambda p:(-p["tagged_events"],-p["tagged_goals"],p["name"]))
    timeline=[
        {"second":round(float(e.get("second") or 0),1),
         "event_type":e.get("event_type") or "",
         "label":LABELS.get(e.get("event_type"),str(e.get("event_type") or "").replace("_"," ").title()),
         "side":e.get("perspective") or "neutral",
         "player":e.get("player") or "",
         "phase":e.get("phase") or "auto",
         "url":timestamped_video_url(video_url,float(e.get("second") or 0)) if video_url else ""}
        for e in sorted(confirmed,key=lambda e:float(e.get("second") or 0))
    ]
    return {"verified_count":len(confirmed),"team":sides["for"],"opponent":sides["against"],
            "phases":by_phase,"players":players,"timeline":timeline,
            "sample_only":True,
            "note":"Résultats calculés uniquement sur les actions annotées et confirmées. Les absences de tags ne valent pas zéro sur le match entier."}
