"""Spatial association of candidate event actors with independently reviewed tracks.
No promotion to verified sporting events. All tracks (including unreviewed
competitors) participate in ambiguity checks. Never bridge a missing track gap.
"""
from bisect import bisect_left
from collections import Counter, defaultdict
from hashlib import sha256
from math import hypot, isfinite
from pathlib import Path

def source_revision(path):
    try:
        p=Path(path).resolve(); s=p.stat()
        return sha256(repr((str(p),s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)).encode()).hexdigest()
    except (OSError,ValueError,TypeError):return None

def _point(p):
    try:t,x,y=(float(p[k]) for k in ("second","x","y"))
    except (ValueError,TypeError,KeyError):return None
    return (t,x,y) if all(isfinite(v) for v in (t,x,y)) and t>=0 and 0<=x<=1 and 0<=y<=1 else None

def _identity(r):
    s=r.get("side"); n=r.get("cap_number")
    if s in ("for","against") and type(n) is int and 1<=n<=30 and r.get("provenance")=="coach_review" and str(r.get("evidence") or "").strip():return s,n
    return None

class SpatialAttribution:
    def __init__(self,tracking,reviews,valid_ids,*,aspect=16/9,gate=.018,margin=.009,max_gap=.26):
        if not all(isfinite(x) and x>0 for x in (aspect,gate,margin,max_gap)):raise ValueError("Invalid spatial parameters")
        self.aspect=aspect;self.gate=gate;self.margin=margin;self.max_gap=max_gap
        self.tracks=[]; ids=Counter(str(r["id"]) for r in tracking.get("tracks",[]))
        for tr in tracking.get("tracks",[]):
            k=str(tr["id"])
            if ids[k]!=1:continue
            pp=[_point(p) for p in tr.get("points",[])]
            if not pp or any(p is None for p in pp) or any(b[0]<=a[0] for a,b in zip(pp,pp[1:])):continue
            ident=_identity(reviews.get(k,{})) if k in valid_ids else None
            self.tracks.append((k,pp,[p[0] for p in pp],ident))
    def match(self,position):
        p=_point(position or {})
        if p is None or not str((position or {}).get("evidence") or "").strip():return None,"missing_position"
        t,x,y=p; options=[]
        for k,pp,tt,ident in self.tracks:
            j=bisect_left(tt,t)
            if j<len(tt) and abs(tt[j]-t)<1e-8:_,a,b=pp[j]
            elif 0<j<len(tt) and tt[j]-tt[j-1]<=self.max_gap+1e-8:
                f=(t-tt[j-1])/(tt[j]-tt[j-1]);a=pp[j-1][1]+f*(pp[j][1]-pp[j-1][1]);b=pp[j-1][2]+f*(pp[j][2]-pp[j-1][2])
            else:continue
            d=hypot(a-x,(b-y)/self.aspect)
            if d<=self.gate+self.margin:options.append((d,k,ident))
        options.sort()
        if not options or options[0][0]>self.gate:return None,"no_track"
        d,k,ident=options[0]
        if len(options)>1 and options[1][0]-d<self.margin:return None,"ambiguous"
        if ident is None:return None,"unreviewed_track"
        # Another simultaneous track reviewed as the same athlete makes
        # this identity unsafe, even if it is farther from the action point.
        for other,pp,tt,who in self.tracks:
            if other==k or who!=ident:continue
            j=bisect_left(tt,t)
            if j<len(tt) and (abs(tt[j]-t)<1e-8 or (j>0 and tt[j]-tt[j-1]<=self.max_gap+1e-8)):
                return None,"duplicate_identity"
        return {"side":ident[0],"cap_number":ident[1],"track_id":k,"image_error":round(d,5)},"matched"

def attribute_events(events,tracking,metric,reviews):
    # Source revision must originate in the producer, not be reconstructed
    # from the current file at report time. Old runs remain unsupported.
    rev=tracking.get("source_revision")
    valid_ids={str(r["id"]) for r in metric.get("tracks",[])} if rev and metric.get("source_revision")==rev else set()
    index=SpatialAttribution(tracking,reviews.get("tracks",{}),valid_ids)
    out=[];counts=Counter();players=defaultdict(Counter)
    for e in events:
        if e.get("counted") is not True or e.get("conflict") or e.get("is_replay"):continue
        row=dict(e); detail={}
        for role,field,capfield in (("actor","actor_position","cap_number"),("receiver","receiver_position","receiver_cap_number")):
            if role=="receiver" and e.get("event_type") not in {"pass_complete","assist","key_pass"}:continue
            if role=="receiver" and detail.get("actor",{}).get("status")=="identity_conflict":
                counts["receiver_actor_conflict"]+=1
                detail["receiver"]={"status":"actor_conflict","match":None}
                continue
            m,status=index.match(e.get(field)) if rev and e.get("source_revision")==rev and valid_ids else (None,"source_or_review_unavailable")
            if m:
                old=e.get(capfield)
                if (e.get("side") in ("for","against") and e["side"]!=m["side"]) or (old is not None and old!=m["cap_number"]) or (role=="receiver" and row.get("side")!=m["side"]) or (role=="receiver" and row.get("cap_number")==m["cap_number"]):
                    status="identity_conflict"; row[capfield]=None
                    if role=="actor":row["receiver_cap_number"]=None
                else:
                    status="corroborated" if old is not None else "new_candidate"
                    if role=="actor":row["side"]=m["side"]
                    row[capfield]=m["cap_number"]
                    row["identity_evidence" if role=="actor" else "receiver_evidence"]="Spatial match to reviewed track "+m["track_id"]
            counts[role+"_"+status]+=1;detail[role]={"status":status,"match":m}
        # Do not expose source tokens in report exports.
        row.pop("source_revision",None); row["spatial_attribution"]=detail;out.append(row)
        s=row.get("side");n=row.get("cap_number")
        if s in ("for","against") and type(n) is int and detail.get("actor",{}).get("status") in ("new_candidate","corroborated"):
            players[s,n][row["event_type"]]+=1
    from services.pass_ledger import pass_ledger
    return {"scope":"candidate_only_reviewed_track_association","counts":dict(counts),"events":out,"pass_ledger":pass_ledger(out),"players":[{"side":s,"cap":n,"events":dict(c)} for (s,n),c in sorted(players.items())]}
