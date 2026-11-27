"""Explicitly paired tactical sequences and timeout context.
Game-clock duration excludes stoppages. Timeout context is descriptive, not causal.
"""
from collections import defaultdict
from services.elite_performance import clock,tags
from services.advanced_observed_metrics import complete_possessions
from services.lineup_performance import confirmed,SIDES

KINDS=("power_play","penalty_kill","counterattack","defensive_recovery","timeout")

def sequence_report(events):
    rows=confirmed(events);result={}
    for side in SIDES:
        rr=[e for e in rows if e.get("perspective")==side]
        poss,_=complete_possessions(rr)
        groups=defaultdict(list);unlinked=0
        for e in rr:
            typ=e.get("event_type","")
            kind=next((k for k in KINDS if typ in {k+"_start",k+"_end"}),None)
            if kind is None:continue
            t=tags(e);tc=clock(e);uid=t.get("sequence")
            if not uid or tc is None:unlinked+=1;continue
            groups[(kind,tc[0],uid)].append(e)
        sequences=[];rejected=[]
        for (kind,q,uid),seq in groups.items():
            a=[e for e in seq if e["event_type"]==kind+"_start"]
            b=[e for e in seq if e["event_type"]==kind+"_end"]
            if len(a)!=1 or len(b)!=1:
                rejected.append(dict(sequence=uid,kind=kind,period=q,reason="bornes absentes ou dupliquées"));continue
            c,d=clock(a[0])[1],clock(b[0])[1]
            if c<d or (kind=="timeout" and c!=d):
                rejected.append(dict(sequence=uid,kind=kind,period=q,reason="chronologie incompatible"));continue
            outcome=tags(b[0]).get("outcome")
            sequences.append(dict(kind=kind,period=q,sequence=uid,start_clock=c,end_clock=d,
                seconds=round(c-d,3) if kind!="timeout" else None,
                outcome=outcome if outcome in {"goal","no_goal","other"} else None,
                event_ids=[a[0].get("id"),b[0].get("id")]))
        conflict=set()
        for i,a in enumerate(sequences):
            for j in range(i+1,len(sequences)):
                b=sequences[j]
                if a["kind"]==b["kind"] and a["period"]==b["period"] and min(a["start_clock"],b["start_clock"])>max(a["end_clock"],b["end_clock"]):
                    conflict.update((i,j))
        for i in sorted(conflict):
            s=sequences[i];rejected.append(dict(sequence=s["sequence"],kind=s["kind"],period=s["period"],reason="chevauchement de séquences"))
        sequences=[s for i,s in enumerate(sequences) if i not in conflict]
        metrics=[]
        for kind in KINDS:
            ss=[s for s in sequences if s["kind"]==kind]
            times=[s["seconds"] for s in ss if s["seconds"] is not None]
            known=[s for s in ss if s["outcome"] in {"goal","no_goal"}]
            # For penalty kill the outcome refers to the attacking opponent.
            success="no_goal" if kind=="penalty_kill" else "goal"
            rate=round(100*sum(s["outcome"]==success for s in known)/len(known),2) if known and kind in {"power_play","penalty_kill","counterattack"} else None
            metrics.append(dict(kind=kind,count=len(ss),timed_count=len(times),total_seconds=round(sum(times),3) if times else None,
                                mean_seconds=round(sum(times)/len(times),3) if times else None,
                                classified_count=len(known),success_pct=rate))
        timeouts=[]
        for s in sequences:
            if s["kind"]!="timeout":continue
            q=s["period"];c=s["start_clock"]
            # Strict inequality excludes a possession straddling a timeout or
            # sharing a boundary without known action order.
            before=sorted([p for p in poss if p["period"]==q and p["end_clock"]>c],key=lambda p:p["end_clock"])[:2]
            after=sorted([p for p in poss if p["period"]==q and p["start_clock"]<c],key=lambda p:-p["start_clock"])[:2]
            def sample(ps):
                n=len(ps);g=sum(p["outcome"]=="goal" for p in ps)
                return dict(n=n,goals=g if n else None,conversion_pct=round(100*g/n,2) if n else None,possessions=[p["possession"] for p in ps])
            a,b=sample(before),sample(after)
            timeouts.append(dict(period=q,clock_s=c,sequence=s["sequence"],before=a,after=b,
                 delta_pp=round(b["conversion_pct"]-a["conversion_pct"],2) if a["n"]==b["n"]==2 else None,
                 note="Deux possessions appariées avant/après au maximum. Association descriptive, aucune causalité."))
        result[side]=dict(sequences=sequences,metrics=metrics,timeouts=timeouts,rejected=rejected,unlinked=unlinked)
    return dict(sides=result,scope="explicit_paired_tactical_sequences",note="Durées effectives sur le chrono de jeu. Aucun calcul de durée réelle de temps mort à partir d'une horloge arrêtée.")
