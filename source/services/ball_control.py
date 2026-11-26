"""Ball-control interval reducer. Candidate visual intervals, never game-clock time.
Overlapping clips are unioned, contradictory controllers are excluded, gaps are
not filled. No inference from mere ball/player proximity or adjacent events.
"""
from collections import defaultdict, Counter
from math import isfinite

SIDES=("for","against","unknown")

def normalize_control_intervals(rows, segment, scene):
    """Clip supported observations to their unique owning core interval."""
    if scene not in {"water_polo","mixed"} and rows:
        raise ValueError("Control observations in unreadable scene")
    out=[]
    clip_start=float(segment["clip_start"]); clip_end=float(segment["clip_end"])
    core_start=float(segment["start"]); core_end=float(segment["end"])
    if not clip_start<=core_start<core_end<=clip_end:raise ValueError("Invalid core")
    for row in rows:
        if row.get("is_replay"):continue
        a,b=float(row["start_second"]),float(row["end_second"])
        if not (isfinite(a) and isfinite(b) and 0<=a<b<=clip_end-clip_start+1e-6):
            raise ValueError("Control interval outside clip")
        a=max(core_start,a+clip_start);b=min(core_end,b+clip_start)
        a,b=round(a,3),round(b,3)
        if b<=a:continue
        out.append({**row,"start_second":a,"end_second":b,"segment_index":segment["index"]})
    return out

def _identity(r):
    s=r.get("side")
    if s not in ("for","against") or not str(r.get("team_evidence") or "").strip():return ("unknown",None)
    cap=r.get("cap_number")
    if type(cap) is not int or not 1<=cap<=30 or not str(r.get("identity_evidence") or "").strip():cap=None
    return (s,cap)

def control_report(rows):
    """Sweep half-open time intervals. Only unique identities receive time.
    Same-team conflicting cap numbers still establish team control, but not
    individual control. Cross-team conflicts establish neither.
    Unknown evidence overlapping a known identity cannot verify that identity.
    """
    starts=defaultdict(list); ends=defaultdict(list); excluded=0
    for i,r in enumerate(rows):
        if r.get("is_replay") or r.get("conflict") or not str(r.get("evidence") or "").strip():
            excluded+=1;continue
        try:a,b,c=map(float,(r["start_second"],r["end_second"],r["confidence"]))
        except (ValueError,TypeError,KeyError):excluded+=1;continue
        if not all(isfinite(x) for x in (a,b,c)) or not 0<=a<b or not .65<=c<=1:
            excluded+=1;continue
        k=_identity(r);starts[a].append((i,k));ends[b].append(i)
    active={}; intervals=[]; last=None
    totals=Counter(); players=defaultdict(float); conflicted=0.; observed=0.
    for t in sorted(set(starts)|set(ends)):
        if last is not None and t>last and active:
            dt=t-last; observed+=dt
            ids=set(active.values()); sides={s for s,n in ids}
            if len(sides)!=1 or "unknown" in sides:
                side="unknown";cap=None; status="team_conflict" if len(sides)>1 else "unknown_team"
            else:
                side=next(iter(sides)); caps={n for s,n in ids}
                cap=next(iter(caps)) if len(caps)==1 else None
                status="identified" if cap is not None else ("identity_conflict" if len(caps-{None})>1 else "unresolved_cap")
            if status in ("team_conflict","identity_conflict"):conflicted+=dt
            totals[side]+=dt
            if cap is not None:players[(side,cap)]+=dt
            # Merge only adjacent intervals with the same attribution and status.
            if intervals and intervals[-1]["end_second"]==last and (intervals[-1]["side"],intervals[-1]["cap_number"],intervals[-1]["status"])==(side,cap,status):
                intervals[-1]["end_second"]=t
            else:
                intervals.append({"start_second":last,"end_second":t,"side":side,"cap_number":cap,"status":status})
        for i in ends[t]:active.pop(i,None)
        for i,k in starts[t]:active[i]=k
        last=t
    for r in intervals:r["seconds"]=round(r["end_second"]-r["start_second"],3)
    teams={}
    for side in SIDES:
        ps=[{"cap":n,"control_video_seconds":round(v,3)} for (s,n),v in sorted(players.items()) if s==side]
        team=totals[side]; attributed=sum(v for (s,n),v in players.items() if s==side)
        teams[side]={"control_video_seconds":round(team,3) if team else None,
                     "unattributed_video_seconds":round(max(0.,team-attributed),3) if team else None,
                     "players":ps}
    if abs(sum(totals.values())-observed)>1e-6:raise RuntimeError("Control reconciliation failed")
    return {"scope":"candidate_visible_control_video_time","observed_video_seconds":round(observed,3),
            "conflicting_video_seconds":round(conflicted,3),"excluded_intervals":excluded,
            "teams":teams,"intervals":intervals}
