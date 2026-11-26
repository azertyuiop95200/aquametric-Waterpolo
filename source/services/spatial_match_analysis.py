"""Shot-point data for authentic interactive water-polo court maps.

Coordinates are human-verified normalized attack-half-pool positions:
(x=0..100 left->right, y=0..100 goal->midfield). No artificial shot points,
xG estimates, or auto-generated event coordinates.
"""
from __future__ import annotations

from collections import defaultdict
from sqlalchemy import select
from models import Event, EventPosition
from services.video import timestamped_video_url

SHOTS = {"goal", "shot_on_target", "shot_off_target", "shot_blocked", "shot_unknown"}
MAP_EVENTS = SHOTS | {"save", "recovery", "interception", "turnover", "pass_complete"}


def spatial_match_dashboard(db, match, segments):
    indexes={s["id"]:s for s in segments if s["id"] is not None}
    legacy = next((s for s in segments if s["id"] is None), None)
    positions={p.event_id:p for p in db.scalars(
        select(EventPosition).join(Event, Event.id==EventPosition.event_id)
        .where(Event.match_id==match.id)).all()}
    points=[]
    by_period=defaultdict(lambda:{"for":0,"against":0,"shots_for":0,"shots_against":0})
    observed_shots=0
    confirmed_events=0
    unknown_period_events=0
    for event in sorted(match.events, key=lambda e:(e.id or 0)):
        if (event.confidence or "").upper() not in {"CONFIRMED","VERIFIED"}:
            continue
        confirmed_events+=1
        context=getattr(event,"context_meta",None)
        side=getattr(context,"perspective","for")
        if side not in {"for","against"}:
            side="neutral"
        position=positions.get(event.id)
        from services.ultimate_analytics import note_tags
        raw_period=position.period if position and position.period else note_tags(event).get("period")
        period=int(raw_period) if str(raw_period) in {"1","2","3","4","5","6","7","8"} else None
        if period is None: unknown_period_events+=1
        segment=indexes.get(position.segment_id) if position and position.segment_id else legacy
        second=round(float(position.segment_second if position and position.segment_second is not None
                           else event.second or 0),1)
        if event.event_type in SHOTS:
            observed_shots+=1
            if side in {"for","against"} and period is not None:
                by_period[period]["shots_"+side]+=1
        if event.event_type=="goal" and side in {"for","against"} and period is not None:
            by_period[period][side]+=1
        if not position or position.x_pct is None or position.y_pct is None:
            continue
        video_url=(segment or {}).get("video_url") or ""
        if video_url:
            proof=timestamped_video_url(video_url,second)
        elif segment:
            proof=f"/matches/{match.id}/analysis/result?segment={segment.get('id') or 'primary'}&t={second}#annotation"
        else:
            proof=""
        points.append({
            "event_id":event.id,"event_type":event.event_type,
            "x":round(float(position.x_pct),3),"y":round(float(position.y_pct),3),
            "side":side,"player_id":event.player_id,
            "player":event.player.name if event.player else "",
            "second":second,"period":period,
            "segment_id":position.segment_id,"proof_url":proof,
            "phase":getattr(context,"phase_tag","auto"),
            "provenance":position.provenance,
        })
    points.sort(key=lambda p:(p["period"] or 99,p["second"],p["event_id"]))
    mapped_shots=sum(p["event_type"] in SHOTS for p in points)
    cells={}
    for side in ("for","against"):
        selected=[p for p in points if p["side"]==side and p["event_type"] in SHOTS]
        zone_rows=[]
        for row,yrange in enumerate([(0,33.333),(33.333,66.666),(66.666,100.0001)]):
            for col,xrange in enumerate([(0,33.333),(33.333,66.666),(66.666,100.0001)]):
                area=[p for p in selected if xrange[0]<=p["x"]<xrange[1] and yrange[0]<=p["y"]<yrange[1]]
                goals=sum(p["event_type"]=="goal" for p in area)
                zone_rows.append({
                    "zone":f"{'Proche' if row==0 else 'Médiane' if row==1 else 'Lointaine'} · {'gauche' if col==0 else 'centre' if col==1 else 'droite'}",
                    "x_index":col,"y_index":row,
                    "shots":len(area),"goals":goals,
                    "conversion_pct":round(100*goals/len(area),1) if area and not any(p["event_type"]=="shot_unknown" for p in area) else None,
                })
        cells[side]=zone_rows
    return {
        "points":points,"points_count":len(points),
        "shots_mapped":mapped_shots,"shots_reviewed":observed_shots,
        "events_reviewed":confirmed_events,"unknown_period_events":unknown_period_events,
        "unlocated_shots":observed_shots-mapped_shots,
        "periods":[{"period":k,**v} for k,v in sorted(by_period.items())],
        "shot_zones":cells,
        "coordinate_system":"normalized_attack_half_0_100",
        "measured":"manual_verified_event_position",
        "xg_available":False,
        "note":"Chaque point vient d'une action annotée et confirmée ; les zones sans point n'impliquent pas zéro tir sur le match.",
    }
