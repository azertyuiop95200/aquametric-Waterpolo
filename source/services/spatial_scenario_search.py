"""Bounded tactical search over explicit coach hypotheses, not observed outcomes."""
from copy import deepcopy
from services.spatial_sandbox import sandbox
from services.spatial_replay import number

def search_scenarios(baseline, edits):
    if not isinstance(edits,dict): raise ValueError("Invalid scenario")
    seed=deepcopy(edits)
    seed["suggest"]=True
    L,W=baseline["length_m"],baseline["width_m"]
    g=baseline["goal_x"]
    direction=1 if g==L else -1
    start=seed.get("start",baseline["start"])
    defenders=seed.get("defenders",baseline["defenders"])
    options=seed.get("options",baseline["options"])
    candidates=[]
    def add(name,description,change):
        c=deepcopy(seed)
        change(c)
        candidates.append((name,description,c))
    add("Référence coach","Configuration actuelle",lambda c:None)
    for t in (.25,.5,1.,1.5,2.):
        add("Temporiser "+str(t)+" s","Projection des vitesses renseignées",lambda c,t=t:c.update(delay_s=t))
    for dx,dy,name in [(0,-.75,"Décalage gauche"),(0,.75,"Décalage droite"),(.75,0,"Avancer"),(-.75,0,"Reculer"),(.75,-.75,"Diagonale gauche"),(.75,.75,"Diagonale droite")]:
        def shift(c,dx=dx,dy=dy):
            p=list(start);p[0]+=direction*dx;p[1]+=dy;c["start"]=p
        add(name,"Repositionnement hypothétique de la porteuse",shift)
    for side in (-1,1):
        def spread(c,side=side):
            c["options"]=deepcopy(options)
            for o in c["options"]:
                if o["kind"]=="pass":
                    p=o["target"];p[1]+=side*.75
        add("Translation collective "+("gauche" if side<0 else "droite"),"Translation des cibles de réception renseignées",spread)
    def widen(c):
        c["options"]=deepcopy(options)
        for o in c["options"]:
            if o["kind"]=="pass":
                p=o["target"];p[1]+=.75 if p[1]>=W/2 else -.75
    add("Élargir le jeu","Écarter les cibles de réception du centre",widen)
    def narrow(c):
        c["options"]=deepcopy(options)
        for o in c["options"]:
            if o["kind"]=="pass":
                p=o["target"];p[1]+=max(-.75,min(.75,W/2-p[1]))
    add("Resserrer le jeu","Rapprocher les cibles de réception",narrow)
    # Opponent reaction sensitivity is explicitly separate from coach-controlled actions.
    for side in (-1,1):
        def block(c,side=side):
            c["defenders"]=deepcopy(defenders)
            for d in c["defenders"]:d["position"][1]+=side*.5
        add("Bloc adverse "+("gauche" if side<0 else "droite"),"Sensibilité à une réaction adverse imposée",block)
    out=[]; rejected=[]; windows=[]
    for name,description,c in candidates:
        timing=name=="Référence coach" or name.startswith("Temporiser ")
        evaluated=deepcopy(c)
        if not timing: evaluated.pop("keeper_id",None)
        try:r=sandbox(baseline,evaluated,trials=16)
        except (ValueError,TypeError,KeyError) as exc:
            rejected.append({"name":name,"reason":str(exc)[:150]});continue
        # A shot outside goal or truncated observed trajectory cannot win a search.
        eligible=[o for o in r["options"] if o["clearance_frequency"] is not None and (o["kind"]=="pass" or o["target_in_goal"])]
        shots=[o for o in eligible if o["kind"]=="shot"]
        passes=[o for o in eligible if o["kind"]=="pass"]
        def best(xs):
            if not xs:return None
            o=max(xs,key=lambda o:(o["clearance_frequency"],o["clearance_m"]))
            return {k:o[k] for k in ("id","kind","clearance_frequency","clearance_m","simulation_interval","flight_s")}
        if timing and r.get("goal_coverage"):
            gmap=r["goal_coverage"]
            windows.append(dict(delay_s=r["delay_s"],keeper=gmap["keeper"],defence=gmap["defence"],
                                best_shot=best(shots),best_pass=best(passes)))
        out.append({"name":name,"description":description,"edits":c,"best_shot":best(shots),"best_pass":best(passes),
                    "reaction_sensitivity":name.startswith("Bloc adverse")})
    windows.sort(key=lambda w:w["delay_s"])
    return {"timing_samples":windows,"mode":"coach_hypothesis_search","trials_per_option":16,"scenarios":out,"rejected":rejected,
            "limitations":["Exploratory frequencies; refine a chosen scenario before comparison",
                           "No prediction of goals or pass completion",
                           "Timing samples compare discrete release delays, not continuous optimal windows; no possession clock or pass-then-shot outcome modeled",
                           "Instant repositioning is a hypothetical initial configuration, not a feasible movement plan",
                           "Collective movement affects receiver proxies, not verified player identities"]}
