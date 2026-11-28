"""Explicit review of existing R7 links. Never synthesize missing observations."""
from math import isfinite

def fragment_ids(item,scan,by_id,fps):
    if not isinstance(item,dict):raise ValueError("Identité invalide.")
    first=item.get("track_id")
    if type(first) is not int:raise ValueError("Identifiant de piste invalide.")
    ids=item.get("fragment_track_ids",[first])
    if not isinstance(ids,list) or not 1<=len(ids)<=4 or any(type(k) is not int for k in ids):
        raise ValueError("Une à quatre pistes par identité.")
    if ids[0]!=first or len(set(ids))!=len(ids) or any(str(k) not in by_id for k in ids):
        raise ValueError("Piste inconnue, répétée ou ordre invalide.")
    if len(ids)==1:return ids
    if item.get("links_reviewed") is not True:
        raise ValueError("Confirmer visuellement chaque raccordement.")
    evidence=item.get("link_evidence")
    if not isinstance(evidence,str) or not 3<=len(evidence.strip())<=300:
        raise ValueError("Justification des raccordements requise.")
    review=scan.get("fragment_link_review",{})
    if not isinstance(review,dict) or review.get("engine")!="r7-fragment-links-v1" or review.get("statistical_use_allowed") is not False:
        raise ValueError("Scan avec propositions de raccordement requis.")
    cuts=[f["source_frame_index"] for f in scan["frames"] if f.get("scene_reset") is True]
    for a,b in zip(ids,ids[1:]):
        p,q=by_id[str(a)],by_id[str(b)]
        if p.get("kind")!="head" or q.get("kind")!="head" or not p.get("points") or not q.get("points"):
            raise ValueError("Fragments de tête requis.")
        t,u=p["points"][-1]["second"],q["points"][0]["second"]
        if not all(type(v) in (float,int) and isfinite(v) for v in (t,u)) or not 0<u-t<=.240001:
            raise ValueError("Fragments chevauchants ou trop éloignés.")
        if any(round(t*fps)<c<=round(u*fps) for c in cuts):
            raise ValueError("Raccordement à travers une coupure interdit.")
        matches=[e for e in review.get("links",[]) if e.get("from_track_id")==a and e.get("to_track_id")==b
            and e.get("status")=="review_candidate_not_verified" and e.get("from_second")==t and e.get("to_second")==u]
        if len(matches)!=1:raise ValueError("Raccordement absent ou ambigu dans la preuve.")
    return ids
