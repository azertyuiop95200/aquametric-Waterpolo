"""Import a portable review as reference, not as verified match events."""
import json, hashlib, re
from math import isfinite
from collections import Counter
from services.possession_evidence import validate, CAUSES

MAX_BYTES=512*1024
MAX_ROWS=2000
COLORS={"blancs","bleus"}
def require(ok,msg):
    if not ok: raise ValueError(msg)
def num(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and isfinite(x)
def clean_id(x):
    return isinstance(x,str) and re.fullmatch(r"[A-Za-z0-9_-]{1,60}",x)
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
        validate(a,b,e.get("before_team") or "unknown",e.get("after_team") or "unknown",
                 e.get("before_state"),e.get("after_state"),e.get("cause"),e["cause_verified"],e["decision_verified"],
                 e["single_transition_verified"],e["linked_prior_shot"],e["observation"])
        iv_ids.add(e["interval_id"]);periods.add(e["period"])
    require(len(periods)==1,"Une référence doit correspondre à une seule période.")
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
        result=validate(e["start_s"],e["end_s"],e.get("before_team") or "unknown",e.get("after_team") or "unknown",
            e["before_state"],e["after_state"],e["cause"],e["cause_verified"],e["decision_verified"],
            e["single_transition_verified"],e["linked_prior_shot"],e["observation"])
        iv.append(dict(id=e["interval_id"],start=e["start_s"],end=e["end_s"],before=side(e.get("before_team")),after=side(e.get("after_team")),
            status=result["status"],location_start=locate(t,e["start_s"]),location_end=locate(t,e["end_s"]),
            observation=e["observation"],prior_shot=e["linked_prior_shot"]))
    return dict(events=ev,intervals=iv,counts=dict(Counter(e["state"] for e in ev)),
                duration_s=t["duration_s"],home_color=home_color,coverage_complete=False,
                verified_match_event_count=0,note="Référence importée, non fusionnée aux événements du match. Temps locaux relatifs au premier échantillon de chaque partie; alignement au lecteur à vérifier.")
