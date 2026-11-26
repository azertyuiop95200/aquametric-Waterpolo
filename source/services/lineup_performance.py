"""Effective-clock lineup and context analysis. Never use video seconds as playing time."""
from collections import defaultdict, Counter
from services.elite_performance import clock, tags
from services.advanced_observed_metrics import complete_possessions

SIDES=("for","against")

def confirmed(events):
    return [e for e in events if str(e.get("confidence") or "").upper() in {"CONFIRMED","VERIFIED"}]

def intervals(rows,player_ids):
    """Strict per-player quarter pairing. Ambiguous streams are withheld."""
    markers=defaultdict(list); issues=[]
    for e in rows:
        if e.get("event_type") not in {"player_in","player_out"}:continue
        pid=e.get("player_id");tc=clock(e)
        if pid not in player_ids or tc is None:
            issues.append(e.get("id"));continue
        markers[(tc[0],pid)].append((tc[1],e.get("event_type"),e.get("id")))
    result=defaultdict(list);bad_quarters=set()
    for (q,pid),seq in markers.items():
        start=None; local=[]; valid=True
        for c,typ,eid in sorted(seq,key=lambda x:(-x[0],x[1]!="player_out",x[2] or 0)):
            if typ=="player_in":
                if start is not None:valid=False;break
                start=(c,eid)
            elif start is None or start[0]<=c:
                valid=False;break
            else:
                local.append(dict(period=q,player_id=pid,start_clock=start[0],end_clock=c,
                                  seconds=round(start[0]-c,3),event_ids=[start[1],eid]))
                start=None
        if start is not None:valid=False
        if valid:result[q].extend(local)
        else:
            bad_quarters.add(q);issues.extend(eid for c,t,eid in seq)
    return dict(result),bad_quarters,issues

def coverage_claim(rows,q,key,side):
    return any(e.get("event_type")=="period_end" and e.get("perspective")==side
               and clock(e)==(q,0) and tags(e).get(key)=="yes" for e in rows)

def lineup_report(events,roster):
    rows=confirmed(events)
    own=[e for e in rows if e.get("perspective")=="for"]
    names={p["id"]:p["name"] for p in roster}
    per,bad,issues=intervals(own,set(names))
    # A marker without clock or identity cannot be assigned safely to any quarter.
    unknown_marker=any(e.get("event_type") in {"player_in","player_out"} and
                       (clock(e) is None or e.get("player_id") not in names) for e in own)
    goals=[e for e in rows if e.get("event_type")=="goal"]
    unknown_goal=any(clock(e) is None or e.get("perspective") not in SIDES for e in goals)
    players={pid:dict(player_id=pid,name=name,playing_seconds=None,intervals=[],goals_for=None,
                      goals_against=None,plus_minus=None,goal_evaluated_seconds=0,eligible_quarters=[])
             for pid,name in names.items()}
    for q,spans in per.items():
        for span in spans:
            p=players[span["player_id"]]
            p["intervals"].append(span)
            p["playing_seconds"]=round((p["playing_seconds"] or 0)+span["seconds"],3)
    lineups={};quarters=[]
    for q in range(1,5):
        spans=per.get(q,[])
        lineup_claim=coverage_claim(rows,q,"lineups_complete","for")
        goal_claim=all(coverage_claim(rows,q,"goals_complete",s) for s in SIDES)
        record=dict(period=q,lineup_claim=lineup_claim,goal_claim=goal_claim,
                    valid=False,reason="",unassigned_boundary_goals=0,seconds=0)
        quarters.append(record)
        if not lineup_claim or not goal_claim:
            record["reason"]="Couverture des compositions et des buts à confirmer";continue
        if q in bad or unknown_marker or unknown_goal:
            record["reason"]="Marqueurs ou buts incohérents / non attribuables";continue
        boundaries=sorted({0.,480.,*(v for s in spans for v in (s["start_clock"],s["end_clock"]))},reverse=True)
        windows=[]
        for a,b in zip(boundaries,boundaries[1:]):
            members=tuple(sorted(s["player_id"] for s in spans if s["start_clock"]>=a and s["end_clock"]<=b))
            if not 1<=len(members)<=7 or len(set(members))!=len(members):
                break
            windows.append((a,b,members))
        if len(windows)!=len(boundaries)-1:
            record["reason"]="Composition absente ou supérieure à sept joueuses";continue
        qgoals=[e for e in goals if clock(e)[0]==q]
        keys=[(e["perspective"],clock(e)[1]) for e in qgoals]
        if len(keys)!=len(set(keys)):
            record["reason"]="Buts potentiellement dupliqués au même chrono";continue
        # A goal on an internal substitution boundary is ambiguous without event ordering.
        ambiguous=[e for e in qgoals if clock(e)[1] in boundaries[1:-1]]
        if ambiguous:
            record["unassigned_boundary_goals"]=len(ambiguous)
            record["reason"]="But au même chrono qu'un changement : ordre à vérifier";continue
        record.update(valid=True,reason="Échantillon du quart déclaré complet et cohérent",seconds=480)
        for a,b,members in windows:
            gg=[e for e in qgoals if b<=clock(e)[1]<=a]
            f=sum(e["perspective"]=="for" for e in gg);g=len(gg)-f
            bucket=lineups.setdefault(members,dict(player_ids=list(members),names=[names[i] for i in members],
                     seconds=0,goals_for=0,goals_against=0,plus_minus=0,goal_event_ids=[],periods=[]))
            bucket["seconds"]+=a-b;bucket["goals_for"]+=f;bucket["goals_against"]+=g;bucket["plus_minus"]+=f-g
            bucket["goal_event_ids"].extend(e.get("id") for e in gg)
            if q not in bucket["periods"]:bucket["periods"].append(q)
            for pid in members:
                p=players[pid];p["goal_evaluated_seconds"]+=a-b
                p["goals_for"]=(p["goals_for"] or 0)+f
                p["goals_against"]=(p["goals_against"] or 0)+g
                p["plus_minus"]=(p["plus_minus"] or 0)+f-g
                if q not in p["eligible_quarters"]:p["eligible_quarters"].append(q)
    for p in players.values():
        t=p["goal_evaluated_seconds"]
        p["plus_minus_per_8min"]=round(480*p["plus_minus"]/t,3) if t else None
    for r in lineups.values():
        r["plus_minus_per_8min"]=round(480*r["plus_minus"]/r["seconds"],3)
    return dict(scope="senior_regulation_quarters_declared_complete",players=list(players.values()),
                lineups=list(lineups.values()),quarters=quarters,invalid_marker_ids=issues,
                note="Différentiel descriptif, non causal. Exclut les quarts sans couverture déclarée et les buts aux changements ambigus. Temps partiels disponibles séparément.")

def phase_context_report(events):
    rows=confirmed(events);result={}
    for side in SIDES:
        rr=[e for e in rows if e.get("perspective")==side]
        poss,_=complete_possessions(rr)
        phases=[]
        for phase in ("even_attack","power_play","counterattack","centre_play","penalty","auto"):
            pp=[p for p in poss if p["phase"]==phase]
            n=len(pp);g=sum(p["outcome"]=="goal" for p in pp)
            phases.append(dict(phase=phase,possessions=n,goals=g if n else None,
                              conversion_pct=round(100*g/n,2) if n else None,
                              mean_seconds=round(sum(p["seconds"] for p in pp)/n,3) if n else None,
                              event_ids=[i for p in pp for i in p["event_ids"]]))
        result[side]=dict(phases=phases)
    return dict(scope="paired_possessions_by_start_phase",sides=result,
                note="Phase au début de la possession, pas durée exclusive de la phase. Les changements de phase nécessitent des bornes distinctes.")
