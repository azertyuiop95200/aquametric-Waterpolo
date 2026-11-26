"""Cross-check independent video signals without promoting them to verified events."""
from collections import Counter, defaultdict
from math import isfinite

SHOT = {"goal", "shot_on_target", "shot_off_target", "shot_blocked", "shot_unknown"}
PASS = {"assist", "key_pass", "pass_complete", "bad_pass"}

def finite(value):
    try:
        v=float(value)
        return v if isfinite(v) else None
    except (ValueError, TypeError):
        return None

def temporal_score_rows(rows):
    """Collapse simultaneous OCR crops; conflicting reads are not independent evidence."""
    by_frame=defaultdict(list)
    for r in rows:
        t=finite(r.get("second"))
        if t is not None and t>=0:
            by_frame[round(t,2)].append(r)
    output=[]
    for t, group in sorted(by_frame.items()):
        if len(group)==1:
            output.append(group[0])
            continue
        # Ambiguous time/score cannot support a goal. Preserve blocked status.
        states={(r.get("home_score"),r.get("away_score")) for r in group}
        periods={r.get("period") for r in group if r.get("period") is not None}
        if len(states)!=1 or len(periods)>1:
            continue
        best=dict(max(group,key=lambda r:finite(r.get("ocr_confidence")) or 0))
        for k in ("is_replay","is_break","is_final"):
            best[k]=any(r.get(k) for r in group)
        output.append(best)
    return output

def audit(automatic, actions):
    """Report cross-modal consistency, not a calibrated accuracy percentage.

    OCR side (home/away) is not equated to the selected team without a verified
    mapping. Match on time only, and only one-to-one unambiguous windows.
    """
    observations=automatic.get("observations") or []
    candidates=automatic.get("candidates") or []
    events=actions.get("events") or []
    goals=[e for e in events if e.get("event_type")=="goal" and e.get("counted") is True]
    brackets=[]
    for c in candidates:
        if not str(c.get("event_type","")).startswith("goal_candidate_"):
            continue
        evidence=c.get("evidence") or {}
        if not isinstance(evidence,dict):
            continue
        a,b=finite(evidence.get("bracket_start_second")),finite(evidence.get("bracket_end_second"))
        if a is None or b is None or not 0<=a<=b:
            continue
        brackets.append((a,b))
    # Only compare the latest action run when its time axis matches the
    # automatic evidence. Callers must explicitly establish this.
    comparable=bool(automatic.get("same_source_timeline"))
    matched=[]
    if comparable:
        edges={i:[j for j,g in enumerate(goals) if finite(g.get("second")) is not None and a<=float(g["second"])<=b]
               for i,(a,b) in enumerate(brackets) if b-a<=30}
        reverse=Counter(j for js in edges.values() for j in js)
        matched=[(i,js[0]) for i,js in edges.items() if len(js)==1 and reverse[js[0]]==1]
    shot_rows=[e for e in events if e.get("counted") is True and e.get("event_type") in SHOT]
    counted=[e for e in events if e.get("counted") is True]
    return {
        "scope":"candidate_consistency_not_accuracy",
        "ocr_frames":len(temporal_score_rows(observations)),
        "score_windows":len(brackets),
        "ai_goal_candidates":len(goals),
        "time_matches":len(matched) if comparable else None,
        "comparison_enabled":comparable,
        "unmatched_ocr":len(brackets)-len(matched) if comparable else None,
        "unmatched_ai":len(goals)-len(matched) if comparable else None,
        "unreadable_or_unassigned":sum(e.get("side") in {None,"unknown"} or not e.get("cap_number") for e in counted),
        "conflicting_actions":sum(bool(e.get("conflict")) for e in events),
        "shot_count":len(shot_rows),
        "review_required":True,
        "accuracy_verified":False,
        "note":"Les concordances temporelles ne prouvent ni l'identité, ni l'équipe, ni la précision réelle. Les signaux indépendants restent séparés.",
    }

def evaluate(reference, predictions, tolerance=2.0):
    """One-to-one class/side event scoring for a labelled held-out sequence.
    Unlabelled coverage must be excluded by the caller. No synthetic score
    may be reported as real-match accuracy.
    """
    edges=[]
    for i,r in enumerate(reference):
        t=finite(r.get("second"))
        if t is None:
            raise ValueError("Invalid reference timestamp")
        for j,p in enumerate(predictions):
            s=finite(p.get("second"))
            if s is not None and r.get("event_type")==p.get("event_type") and r.get("side")==p.get("side") and abs(t-s)<=tolerance:
                edges.append((i,j,abs(t-s)))
    # Maximum cardinality matching, nearest candidate first; no reuse.
    links=defaultdict(list)
    for i,j,d in sorted(edges,key=lambda v:v[2]):
        links[i].append(j)
    owners={}
    def augment(i,seen):
        for j in links[i]:
            if j in seen: continue
            seen.add(j)
            if j not in owners or augment(owners[j],seen):
                owners[j]=i
                return True
        return False
    for i in range(len(reference)):
        augment(i,set())
    tp=len(owners)
    fp=len(predictions)-tp
    fn=len(reference)-tp
    precision=tp/(tp+fp) if tp+fp else None
    recall=tp/(tp+fn) if tp+fn else None
    return {"tp":tp,"fp":fp,"fn":fn,"precision":precision,"recall":recall,
            "f1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            "mean_time_error_s":round(sum(abs(float(reference[i]["second"])-float(predictions[j]["second"])) for j,i in owners.items())/tp,3) if tp else None}
