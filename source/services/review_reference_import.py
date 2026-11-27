"""Import a portable review as reference, not as verified match events."""
import json, hashlib, re
from math import isfinite
from collections import Counter
from services.possession_evidence import validate, CAUSES
from services.pass_review import validate_pass_review, summarize_pass_review
from services.evidence_manifest import validate_manifest

MAX_BYTES=512*1024
MAX_ROWS=2000
COLORS={"blancs","bleus"}
def require(ok,msg):
    if not ok: raise ValueError(msg)
def num(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and isfinite(x)
def clean_id(x):
    return isinstance(x,str) and re.fullmatch(r"[A-Za-z0-9_-]{1,60}",x)
def internal(color):
    return {'bleus':'for','blancs':'against',None:'unknown'}[color]
def strict_bool(x):
    return type(x) is bool
def load(raw):
    require(len(raw)<=MAX_BYTES,"Fichier de référence supérieur à 512 Kio.")
    try:
        p=json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nombre non fini")))
    except (ValueError,UnicodeError,RecursionError) as e:
        raise ValueError("JSON de référence invalide.") from e
    require(isinstance(p,dict) and p.get("format")=="aquametric-review-v1","Format inconnu.")
    t=p.get("timeline");r=p.get("reference")
    require(isinstance(t,dict) and isinstance(r,dict) and r.get("schema_version")=="2.1","Version incompatible.")
    dur=t.get("duration_s")
    require(num(dur) and 0<dur<=43200 and r.get("source_duration_s")==dur,"Durée incohérente.")
    require(r.get("coverage_complete") is False,"Seules les références partielles sont importées.")
    seg=t.get("segments")
    require(isinstance(seg,list) and 1<=len(seg)<=20,"Segments invalides.")
    edge=0;names=set()
    for s in seg:
        require(isinstance(s,dict),"Segment invalide.")
        a,b=s.get("start_s"),s.get("end_s")
        require(num(a) and num(b) and abs(a-edge)<1e-6 and a<b<=dur,"Chronologie discontinue.")
        require(isinstance(s.get("file"),str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",s["file"]) and s["file"] not in names,"Nom de segment invalide.")
        require(isinstance(s.get("sha256"),str) and re.fullmatch(r"[a-f0-9]{64}",s["sha256"]),"Empreinte invalide.")
        require(type(s.get("bytes")) is int and s["bytes"]>0,"Taille invalide.")
        require(num(s.get("first_local_pts_s")) and abs(s["first_local_pts_s"])<=60,"PTS invalide.")
        names.add(s["file"]);edge=b
    require(abs(edge-dur)<1e-6,"Fin de chronologie incohérente.")
    ev=r.get("events");iv=r.get("possession_review_intervals")
    require(isinstance(ev,list) and isinstance(iv,list) and len(ev)+len(iv)<=MAX_ROWS,"Registre invalide.")
    ids=set();periods=set()
    for e in ev:
        require(isinstance(e,dict) and clean_id(e.get("event_id")) and e["event_id"] not in ids,"Identifiant événement invalide/dupliqué.")
        a,b=e.get("video_start_s"),e.get("video_end_s")
        require(num(a) and num(b) and 0<=a<=b<dur,"Temps événement invalide.")
        require(type(e.get("period")) is int and 1<=e["period"]<=8,"Période invalide.")
        require(e.get("team_before") in COLORS | {None},"Équipe inconnue.")
        require(e.get("cause") in CAUSES and strict_bool(e.get("cause_verified")),"Cause invalide.")
        require(e.get("source_kind") in {"shot","shot_candidate","pass_like","ball_hold"},"Type d'événement invalide.")
        require(e.get("source_review_state") in {"reference_single_review","unresolved","not_shot_example"},"Statut de revue invalide.")
        ids.add(e["event_id"]);periods.add(e["period"])
    iv_ids=set()
    for e in iv:
        require(isinstance(e,dict) and clean_id(e.get("interval_id")) and e["interval_id"] not in iv_ids,"Identifiant intervalle invalide/dupliqué.")
        a,b=e.get("start_s"),e.get("end_s")
        require(num(a) and num(b) and 0<=a<b<dur,"Temps intervalle invalide.")
        require(type(e.get("period")) is int and 1<=e["period"]<=8,"Période invalide.")
        for k in ("before_team","after_team"):
            require(e.get(k) in COLORS | {None},"Équipe intervalle invalide.")
        for k in ("cause_verified","decision_verified","single_transition_verified","linked_prior_shot"):
            require(strict_bool(e.get(k)),"Drapeau de preuve invalide.")
        require(e.get("linked_prior_event") is None or e["linked_prior_event"] in ids,"Lien événement absent.")
        require(isinstance(e.get("observation"),str) and len(e["observation"])<=4000,"Observation invalide.")
        require(strict_bool(e.get("referee_signal_observed",False)),"Drapeau de geste arbitral invalide.")
        require(e.get("cause_candidate") is None or isinstance(e["cause_candidate"],str) and len(e["cause_candidate"])<=500,"Hypothèse de cause invalide.")
        validate(a,b,internal(e.get("before_team")),internal(e.get("after_team")),
                 e.get("before_state"),e.get("after_state"),e.get("cause"),e["cause_verified"],e["decision_verified"],
                 e["single_transition_verified"],e["linked_prior_shot"],e["observation"])
        iv_ids.add(e["interval_id"]);periods.add(e["period"])
    require(len(periods)==1,"Une référence doit correspondre à une seule période.")
    validate_pass_review(r,dur)
    validate_manifest(r)
    try: canonical=json.dumps(p,sort_keys=True,ensure_ascii=True,separators=(",",":"),allow_nan=False)
    except (ValueError,RecursionError) as e: raise ValueError("JSON invalide.") from e
    return p,canonical,hashlib.sha256(canonical.encode()).hexdigest(),next(iter(periods))

def locate(timeline,second):
    for i,s in enumerate(timeline["segments"]):
        if s["start_s"]<=second<s["end_s"]:
            return dict(part=i+1,file=s["file"],local_s=round(second-s["start_s"],6))
    return None

def summarize(p,home_color):
    require(home_color in COLORS,"Couleur de notre équipe non choisie.")
    t=p["timeline"];r=p["reference"]
    def side(c): return "Notre équipe" if c==home_color else "Adversaire" if c in COLORS else "Indéterminée"
    ev=[]
    for e in r["events"]:
        ev.append(dict(id=e["event_id"],time=e["video_end_s"],start=e["video_start_s"],side=side(e.get("team_before")),
            kind=e["source_kind"],cause=e["cause"],state=e["source_review_state"],location=locate(t,e["video_end_s"]),
            observation=e.get("source_observation","")))
    iv=[]
    for e in r["possession_review_intervals"]:
        result=validate(e["start_s"],e["end_s"],internal(e.get("before_team")),internal(e.get("after_team")),
            e["before_state"],e["after_state"],e["cause"],e["cause_verified"],e["decision_verified"],
            e["single_transition_verified"],e["linked_prior_shot"],e["observation"])
        iv.append(dict(id=e["interval_id"],start=e["start_s"],end=e["end_s"],before=side(e.get("before_team")),after=side(e.get("after_team")),
            status=result["status"],location_start=locate(t,e["start_s"]),location_end=locate(t,e["end_s"]),
            observation=e["observation"],prior_shot=e["linked_prior_shot"],
            referee_signal_observed=e.get("referee_signal_observed",False),decision_verified=e["decision_verified"],
            cause_candidate=e.get("cause_candidate"),attributed_cause=result["attributed_cause"]))
    # Opposite observed controls at the same instant cannot both be true.
    endpoints={}
    for e in r["possession_review_intervals"]:
        for edge,key in (("before","start_s"),("after","end_s")):
            if e[edge+"_state"]=="observed":
                endpoints.setdefault(e[key],{}).setdefault(e[edge+"_team"],set()).add(e["interval_id"])
    conflicts=sorted({uid for teams in endpoints.values() if len(teams)>1 for ids in teams.values() for uid in ids})
    for e in iv:
        e["endpoint_conflict"]=e["id"] in conflicts
    chosen=[]; last=-1
    for e in sorted(iv,key=lambda e:e["end"]):
        if e["status"]=="opposite_endpoints" and not e["prior_shot"] and not e["endpoint_conflict"] and e["start"]>=last:
            chosen.append(e["id"]);last=e["end"]
    return dict(events=ev,intervals=iv,counts=dict(Counter(e["state"] for e in ev)),
                interval_statuses=dict(Counter(e["status"] for e in iv)), lower_bound_excluding_linked_shots=len(chosen),
                bound_interval_ids=chosen, endpoint_conflict_ids=conflicts, referee_signals=sum(e["referee_signal_observed"] for e in iv),
                confirmed_referee_decisions=sum(e["decision_verified"] for e in iv), exact_total_changes=None,
                duration_s=t["duration_s"],home_color=home_color,coverage_complete=False,
                pass_review=summarize_pass_review(r,t["duration_s"]),
                evidence_manifest=validate_manifest(r),
                verified_match_event_count=0,note="Référence importée, non fusionnée aux événements du match. Temps locaux relatifs au premier échantillon de chaque partie; alignement au lecteur à vérifier.")
