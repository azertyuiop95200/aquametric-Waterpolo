"""Conservative adapter for the specialist multi-reference engine.
All reference anchors refer to the SAME physical goal and same side.
Agreement between fitted models is an engineering check, not independent metric truth.
"""
from math import hypot,isfinite
import numpy as np
from services.dynamic_calibration import MultiReference,transform,choose_projection
from services.metric_field import calibrate

def normalized_polygon(polygon):
    if not isinstance(polygon,list) or not 3<=len(polygon)<=16:
        raise ValueError("Masque de décor invalide.")
    for p in polygon:
        if not isinstance(p,list) or len(p)!=2 or not all(type(v) in (int,float) and isfinite(v) and 0<=v<=1 for v in p):
            raise ValueError("Coordonnées de décor invalides.")
    return polygon

def references(raw,scan,frame,L,W):
    extra=raw.get("additional_references")
    if not isinstance(extra,list) or not 1<=len(extra)<=2:
        raise ValueError("Une ou deux références supplémentaires requises.")
    if raw.get("same_goal_and_side_reviewed") is not True:
        raise ValueError("Confirmer le même but physique et côté pour tous les repères.")
    rows=[dict(reference_frame=raw["reference_frame"],anchors=raw["anchors"],polygon=raw["polygon"])]+extra
    allowed={f["source_frame_index"] for f in scan["frames"]}
    world=[[0,-1.5],[0,1.5],[0,W/2],[2,W/2],[6,W/2]]
    seen=set();data=[];metadata=[]
    for r in rows:
        if not isinstance(r,dict):raise ValueError("Référence invalide.")
        i=r.get("reference_frame")
        if type(i) is not int or i not in allowed or i in seen:raise ValueError("Référence hors fenêtre ou dupliquée.")
        seen.add(i)
        anchors=r.get("anchors");polygon=normalized_polygon(r.get("polygon"))
        cal=calibrate(anchors,W,L)
        data.append(dict(id=i,frame=frame(i),image_anchors=anchors,world_anchors=world,decor_polygon=polygon))
        metadata.append(dict(reference_frame=i,anchors=anchors,polygon=polygon,fit_error_normalized=cal["fit_error_normalized"]))
    model=MultiReference(data,width_m=W,length_m=L)
    if len(model.refs)!=len(data):raise ValueError("Décor insuffisant dans une référence ; aucune référence ignorée.")
    return model,metadata

def consensus(model,aligned,x,y):
    # Require at least two usable views; no single-view fallback. Reject an
    # invalid or out-of-pool projection rather than silently dropping it.
    if len(aligned)<2:return None
    options=[]
    for a in aligned:
        p=transform(a["matrix"],(x*model.w,y*model.h))
        if p is None or not 0<=p[0]<=model.length_m or not -model.width_m/2<=p[1]<=model.width_m/2:return None
        options.append(dict(x_m=p[0],y_m=p[1],reference=a["reference"],alignment_error_px=a["alignment_error_px"]))
    selected=choose_projection(options,.75)
    if selected is None:return None
    spread=max(hypot(a["x_m"]-b["x_m"],a["y_m"]-b["y_m"]) for a in options for b in options)
    return dict(selected,support=len(options),spread_m=spread)
