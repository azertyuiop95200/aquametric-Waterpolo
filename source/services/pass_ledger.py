"""Passes from canonical candidate events, not from proximity to a ball."""
from collections import Counter
SUCCESS={"pass_complete","assist","key_pass"}
TYPES=SUCCESS|{"bad_pass","pass_unknown"}

def cap(v):return v if type(v) is int and 1<=v<=30 else None

def pass_ledger(events):
    teams={}
    for side in ("for","against","unknown"):
        rows=[a for a in events if a.get("side")==side and a.get("event_type") in TYPES and not a.get("conflict") and not a.get("is_replay") and a.get("counted",True)]
        c=Counter(a["event_type"] for a in rows)
        n=sum(c.values());ok=sum(c[k] for k in SUCCESS);unknown=c["pass_unknown"]
        sent=Counter();received=Counter();links=Counter();methods=Counter()
        for a in rows:
            p=cap(a.get("cap_number")) if side!="unknown" and a.get("identity_evidence") else None
            r=cap(a.get("receiver_cap_number")) if side!="unknown" and a.get("receiver_evidence") else None
            if p:sent[p]+=1
            if a["event_type"] in SUCCESS and r and p!=r:
                received[r]+=1
                if p:links[(p,r)]+=1
            methods[a.get("pass_method","unknown")]+=1
        teams[side]={"attempts":n if n else None,"completed":ok if n else None,"failed":c["bad_pass"] if n else None,"unknown":unknown if n else None,
                     "completion_pct":round(100*ok/n,1) if n and not unknown else None,
                     "sent":dict(sent),"received":dict(received),"network":[{"from":p,"to":r,"count":v} for (p,r),v in sorted(links.items())],
                     "players":[{"cap":p,"sent":sent[p],"received":received[p]} for p in sorted(set(sent)|set(received))],
                     "methods":dict(methods),"unattributed_passers":n-sum(sent.values()),"unattributed_receivers":ok-sum(received.values())}
    return {"teams":teams,"scope":"observed_candidates_only"}
