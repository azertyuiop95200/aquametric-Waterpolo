"""Contextual review of possession windows; does not infer a direct transition or a foul."""
from collections import Counter
from math import isfinite
from services.review_coverage import coverage

TEAMS={"blancs","bleus"}
STATES={"observed","not_observed","unknown"}

def require(ok,msg):
    if not ok: raise ValueError(msg)

def decisions(reference,duration):
    intervals=reference.get("possession_review_intervals",[])
    events={e["event_id"]:e for e in reference.get("events",[])}
    manifest=reference.get("evidence_manifest") or []
    proofs={(e["id"],e["path"]) for e in manifest if e["kind"] in {"interval","correction"}}
    ledger=reference.get("possession_context_review_windows")
    cov=coverage(dict(fps=reference.get("possession_context_fps"),review_windows=ledger),duration)
    if ledger is not None:
        signatures={e["path"]:(e["sha256"],e["bytes"]) for e in manifest}
        for w in ledger:
            for s in w["sheets"]:
                require(signatures.get(s["path"],(s["sha256"],s["bytes"]))==(s["sha256"],s["bytes"]),"Empreinte de planche contextuelle contradictoire.")
    out={}
    for e in intervals:
        c=e.get("context_review")
        if c is None:continue
        uid=e["interval_id"];start,end=e["start_s"],e["end_s"]
        require(isinstance(c,dict) and e["after_state"]=="observed","Contexte : contrôle final observé requis.")
        t=c.get("next_s");team=c.get("next_team");kind=c.get("next_kind")
        require(type(t) in (float,int) and isfinite(t) and end<t<duration and team==e["after_team"] and team in TEAMS,"Contexte : suite temporelle ou équipe incompatible.")
        require(kind in {"control","carry","throw","shot","restart"},"Nature de suite invalide.")
        require(c.get("path_consistent") is None or type(c["path_consistent"]) is bool,"Trajectoire invalide.")
        require(c.get("intervening_opponent_control") in STATES and c.get("intervening_restart") in STATES,"Indice intermédiaire invalide.")
        for key in ("reason","alternative"):
            require(isinstance(c.get(key),str) and 0<len(c[key].strip())<=2000,"Justification et alternative requises.")
        proof=c.get("evidence")
        require(isinstance(proof,list) and 1<=len(proof)<=12 and all(isinstance(p,str) and (uid,p) in proofs for p in proof),"Preuve contextuelle non rattachée.")
        link=c.get("next_event_id")
        if link is not None:
            require(isinstance(link,str) and link in events and kind=="shot","Lien vers événement suivant invalide.")
            v=events[link]
            require(v["source_kind"]=="shot" and v["source_review_state"]=="reference_single_review" and v["team_before"]==team and v["video_start_s"]<=t<=v["video_end_s"],"Tir suivant incompatible.")
        conflicts=set(); endpoint_conflicts=set()
        # For a claimed conservation, any opposing observed control within the window contradicts it.
        for other in intervals:
            if other["interval_id"]==uid:continue
            for edge,key in (("before","start_s"),("after","end_s")):
                if other.get(edge+"_state")=="observed":
                    for own,own_key in (("before","start_s"),("after","end_s")):
                        if e[own+"_state"]=="observed" and other[key]==e[own_key] and other[edge+"_team"]!=e[own+"_team"]:
                            endpoint_conflicts.add(other["interval_id"])
                if other.get(edge+"_state")=="observed" and other.get(edge+"_team") in TEAMS and other[edge+"_team"]!=team and start<=other[key]<=t:
                    conflicts.add(other["interval_id"])
        for v in events.values():
            if v.get("source_kind")=="shot" and v.get("source_review_state")=="reference_single_review" and v.get("team_before") in TEAMS and v["team_before"]!=team and start<=v["video_start_s"]<=t:
                conflicts.add(v["event_id"])
        for a in (reference.get("pass_review") or {}).get("actions",[]):
            k=a.get("control_frame");fps=reference["pass_review"]["fps"]
            if k is not None and a.get("control_team") in TEAMS and a["control_team"]!=team and start<=k/fps<=t:
                conflicts.add(a["id"])
        status="later_control_only"
        if endpoint_conflicts:
            status="endpoint_conflict"
        elif e["before_state"]=="observed" and e["before_team"]!=team:
            status="change_between_observed_controls"
        elif conflicts or c["intervening_opponent_control"]=="observed" or c["intervening_restart"]=="observed" or kind=="restart":
            status="retention_not_supported"
        elif e["before_team"]==team and c.get("path_consistent") is True and c["intervening_opponent_control"]==c["intervening_restart"]=="not_observed":
            status="probable_retained" if e["before_state"]=="observed" else "probable_retained_initial_apparent"
        out[uid]=dict(status=status,next_s=t,next_team=team,next_kind=kind,next_event_id=link,
                      reason=c["reason"],alternative=c["alternative"],evidence=proof,conflict_ids=sorted(conflicts),endpoint_conflict_ids=sorted(endpoint_conflicts),
                      direct_transition_verified=False,cause_attributed=None,complete_possession=False)
    return dict(decisions=out,review_coverage=cov,statuses=dict(Counter(d["status"] for d in out.values())),note="Conclusions contextuelles distinctes des contrôles observés ; ni continuité certaine, ni faute, ni durée de possession déduite.")
