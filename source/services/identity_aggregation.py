"""Match-scoped identity and partial metric aggregation.

Track IDs are observations, never cap numbers. Reviewed identity is (side, cap)
and colour is a reviewed attribute (goalkeepers may wear red on either side).
Automatic hypotheses, confirmed sporting events and metric samples are separate.
"""
from collections import defaultdict, Counter
from math import hypot, isfinite
from services.elite_performance import reduce_side, METRICS

SIDES=("for","against")
COLOURS=("white","blue","red","black","other","unknown")

def identity(row):
    side=row.get("side")
    cap=row.get("cap_number")
    if side not in SIDES or type(cap) is not int or not 1<=cap<=30:return None
    return side,cap

def review_identity(row):
    if not isinstance(row,dict):raise ValueError("Identité invalide.")
    side=row.get("side"); cap=row.get("cap_number"); colour=row.get("colour","unknown")
    if side not in SIDES or colour not in COLOURS:raise ValueError("Équipe ou couleur invalide.")
    if cap is not None and (type(cap) is not int or not 1<=cap<=30):raise ValueError("Numéro invalide.")
    evidence=str(row.get("evidence") or "").strip()
    if not evidence or len(evidence)>300:raise ValueError("Justification visuelle requise (300 caractères maximum).")
    return {"side":side,"cap_number":cap,"colour":colour,"evidence":evidence,"provenance":"coach_review"}

def validate_reviews(raw, valid_tracks, valid_events, valid_shots):
    if not isinstance(raw,dict):raise ValueError("Données invalides.")
    result={}
    for group,allowed in (("tracks",valid_tracks),("events",valid_events),("shots",valid_shots)):
        rows=raw.get(group,{})
        if not isinstance(rows,dict) or len(rows)>len(allowed):raise ValueError("Liste invalide.")
        result[group]={}
        for key,row in rows.items():
            if key not in allowed:raise ValueError("Référence périmée.")
            value=review_identity(row)
            if group=="events" and value["side"]!=allowed[key]:raise ValueError("L'équipe de l'action doit correspondre à l'annotation.")
            result[group][key]=value
    return result

def edges(track):
    for seg in track.get("segments",[]):
        for a,b in zip(seg,seg[1:]):
            try:
                t,u=float(a["second"]),float(b["second"])
                x,y,X,Y=map(float,(a["x_m"],a["y_m"],b["x_m"],b["y_m"]))
            except (ValueError,TypeError,KeyError):continue
            if not all(isfinite(v) for v in (t,u,x,y,X,Y)) or not 0<u-t<=.26 or hypot(X-x,Y-y)/(u-t)>3.5:continue
            yield (t,u,x,y,X,Y)

def distance_union(tracks):
    """Sweep observed intervals; overlapping estimates are counted once.
    Conflicting overlaps (>0.75 m between interpolated midpoints) are omitted.
    No extrapolation or bridging gaps. Video seconds, not effective playing time.
    """
    spans=[e for tr in tracks for e in edges(tr)]
    if not spans:return {"distance_m":None,"observed_seconds":0.,"overlap_seconds":0.,"conflict_seconds":0.}
    boundaries=sorted(set(t for e in spans for t in e[:2]))
    distance=duration=overlap=conflict=0.
    for a,b in zip(boundaries,boundaries[1:]):
        active=[e for e in spans if e[0]<=a and e[1]>=b]
        if not active:continue
        dt=b-a; mid=(a+b)/2
        def point(e):
            f=(mid-e[0])/(e[1]-e[0])
            return e[2]+f*(e[4]-e[2]),e[3]+f*(e[5]-e[3])
        if len(active)>1:
            overlap+=dt
            points=[point(e) for e in active]
            if any(hypot(x-X,y-Y)>.75 for i,(x,y) in enumerate(points) for X,Y in points[i+1:]):
                conflict+=dt;continue
        # Prefer the shortest sampled interval (highest temporal resolution).
        e=min(active,key=lambda r:r[1]-r[0])
        distance+=hypot(e[4]-e[2],e[5]-e[3])*dt/(e[1]-e[0]);duration+=dt
    return {"distance_m":round(distance,2) if duration else None,"observed_seconds":round(duration,3),
            "overlap_seconds":round(overlap,3),"conflict_seconds":round(conflict,3)}

def build_identity_report(metric,events,automatic,roster,reviews):
    reviews=reviews or {}
    tracks=metric.get("tracks",[])
    shots=metric.get("shots",[])
    confirmed=[e for e in events if str(e.get("confidence") or "").upper() in {"CONFIRMED","VERIFIED"}]
    roster_by_id={p["id"]:p for p in roster}
    cap_counts=Counter(p.get("cap_number") for p in roster if p.get("cap_number"))
    names={("for",p["cap_number"]):p["name"] for p in roster if p.get("cap_number") and cap_counts[p["cap_number"]]==1}
    groups=defaultdict(lambda:{"tracks":[],"events":[],"shots":[],"colours":set()})
    unassigned_tracks=[]; unassigned_events=defaultdict(list); unassigned_shots=[]
    track_rows=[];event_rows=[];shot_rows=[]
    for tr in tracks:
        a=reviews.get("tracks",{}).get(str(tr["id"]),{})
        k=identity(a);track_rows.append({"id":tr["id"],"colour":tr.get("colour"),"second":next((s[0]["second"] for s in tr.get("segments",[]) if s),None),"distance_m":tr.get("distance_m"),"review":a})
        if k:groups[k]["tracks"].append(tr);groups[k]["colours"].add(a["colour"])
        else:unassigned_tracks.append(tr)
    for e in confirmed:
        a=reviews.get("events",{}).get(str(e["id"]),{})
        p=roster_by_id.get(e.get("player_id"))
        # The existing confirmed roster link is authoritative; do not silently
        # replace it with another cap. Duplicate roster numbers stay unresolved.
        if p and e.get("perspective")=="for" and p.get("cap_number") and cap_counts[p["cap_number"]]==1:
            k=("for",p["cap_number"])
            if identity(a)!=k:a={"side":"for","cap_number":k[1],"colour":"unknown","provenance":"confirmed_roster"}
        elif p and e.get("perspective")=="for":
            a={}
        k=identity(a)
        if k and k[0]!=e.get("perspective"):k=None
        event_rows.append({"id":e["id"],"second":e.get("second"),"event_type":e.get("event_type"),"side":e.get("perspective"),"review":a,"roster_locked":bool(p and e.get("perspective")=="for")})
        if k:groups[k]["events"].append(e);groups[k]["colours"].add(a.get("colour","unknown"))
        else:unassigned_events[e.get("perspective")].append(e)
    for i,s in enumerate(shots):
        a=reviews.get("shots",{}).get(str(i),{});k=identity(a)
        shot_rows.append({"id":i,"second":s.get("second"),"range_m":s.get("range_m"),"review":a})
        if k:groups[k]["shots"].append(s);groups[k]["colours"].add(a["colour"])
        else:unassigned_shots.append(s)
    players=[]
    for (side,cap),g in sorted(groups.items()):
        m=distance_union(g["tracks"])
        colours=sorted(g["colours"]-{"unknown"})
        # Different colours may be legitimate (change of cap); retain both.
        players.append({"side":side,"cap_number":cap,"name":names.get((side,cap),f"Bonnet {cap}"),
                        "colours":colours,"track_ids":[t["id"] for t in g["tracks"]],
                        "mapped_shots":len(g["shots"]),**m,"stats":reduce_side(g["events"])})
    teams={}
    for side in SIDES:
        ps=[p for p in players if p["side"]==side]
        measured=[p for p in ps if p["distance_m"] is not None]
        rows=[e for e in confirmed if e.get("perspective")==side]
        play=[p["stats"]["playing_seconds"] for p in ps if p["stats"]["playing_seconds"] is not None]
        teams[side]={"playing_seconds":round(sum(play),1) if play else None,"distance_m":round(sum(p["distance_m"] for p in measured),2) if measured else None,
                     "players_measured":len(measured),"player_seconds":round(sum(p["observed_seconds"] for p in measured),3),
                     "players_identified":len(ps),"unassigned_events":len(unassigned_events[side]),
                     "unassigned_stats":reduce_side(unassigned_events[side]),"stats":reduce_side(rows),
                     "mapped_shots":sum(p["mapped_shots"] for p in ps)}
    # Provisional model counts stay completely separate from reviewed rows.
    candidates=defaultdict(list)
    for e in automatic.get("events",[]):
        k=identity(e)
        if k and e.get("counted") is True and not e.get("conflict"):candidates[k].append(e)
    auto_players=[{"side":s,"cap_number":n,"colours":sorted({e.get("cap_colour","unknown") for e in rows}),
                   "event_counts":dict(Counter(e["event_type"] for e in rows))} for (s,n),rows in sorted(candidates.items())]
    # A global team total includes team-attributed anonymous sporting actions,
    # but unidentified distances are withheld to avoid duplicate individuals.
    return {"players":players,"teams":teams,"unassigned_tracks":len(unassigned_tracks),
            "unassigned_shots":len(unassigned_shots),"unknown_side_events":len(unassigned_events[None])+len([e for e in confirmed if e.get("perspective") not in SIDES and e.get("perspective") is not None]),
            "track_rows":track_rows,"event_rows":event_rows,"shot_rows":shot_rows,"auto_players":auto_players,
            "metrics":[[k,l] for k,l in METRICS if k not in {"distance_m","distance_samples","playing_seconds","playing_intervals","unpaired_markers"}],
            "scope":"partial_reviewed_identity_not_full_match"}
