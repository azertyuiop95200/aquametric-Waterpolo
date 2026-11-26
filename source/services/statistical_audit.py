"""Canonical evidence inventory, shared by HTML, JSON and CSV.
Values refer to the reviewed sample, never the unobserved match.
"""
from collections import Counter, defaultdict
from math import isfinite
from services.elite_performance import METRICS, reduce_side, tags, exposure, clock

SOURCES = {
 "official":"https://www.worldaquatics.com/news/4441220/inside-the-action-water-polo-performance-analysis-at-singapore-2025",
 "rules":"https://www.worldaquatics.com/rules/competition-regulations",
 "omega":"https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0363358",
 "wps":"https://water-polo-stats.com/help-visual-entry.html",
 "wpi":"https://www.waterpoloinsights.com/data",
 "tsap":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10532484/",
}
GROUPS = {
 "score_tirs": "goals shots on_target off_target blocked_shots shot_unknown shot_conversion shot_accuracy penalty_shots penalty_goals penalty_conversion",
 "creation_passes":"assists points key_passes passes pass_attempts bad_passes pass_accuracy touches centre_touches actions_created",
 "duels_defense":"duels_won duels_lost duel_pct steals recoveries blocks fast_recoveries late_recoveries",
 "discipline":"fouls_committed fouls_earned offensive_fouls exclusions_committed exclusions_earned penalties_committed penalties_earned personal_fouls",
 "gardiennes":"saves goals_against save_pct",
 "possessions":"possession_ends classified_ends attack_conversion power_play_completed power_play_conversion penalty_kill_completed penalty_kill_success counterattacks turnovers unforced_errors",
 "gestion_match":"swimoffs_won swimoffs_lost timeouts clock_expiries",
 "physique_temps":"sprints playing_seconds distance_m distance_samples playing_intervals unpaired_markers",
}
RATES = {
 "shot_conversion":("goals","shots"),"shot_accuracy":("on_target","shots"),
 "pass_accuracy":("passes","pass_attempts"),"duel_pct":("duels_won",("duels_won","duels_lost")),
 "penalty_conversion":("penalty_goals","penalty_shots"),"save_pct":("saves",("saves","goals_against")),
 "attack_conversion":(None,"classified_ends"),"power_play_conversion":(None,"power_play_completed"),
 "penalty_kill_success":(None,"penalty_kill_completed"),
}
# Zero counts can describe a reviewed sample; a missing measurement is never zero.
PENDING = {
 "score_tirs":[("shot_target_heatmap","Carte des cibles dans le but","positions d'impact"),("shot_speed","Vitesse et accélération du ballon","tracking calibré"),("shot_release_height","Hauteur de libération","reconstruction 3D"),("shot_angle","Angles horizontal / vertical","coordonnées 3D"),("shot_type_split","Tirs par technique, main et contexte","typologie vérifiée"),("xg","Buts attendus (xG)","modèle validé hors échantillon"),("post_shot_xg","xG après tir","trajectoire et modèle validé")],
 "creation_passes":[("pass_network","Réseau de passes orienté","identifiants émetteur / destinataire"),("pass_length","Longueur, vitesse, trajectoire de passe","tracking calibré"),("xpass","Probabilité de passe réussie","modèle calibré"),("secondary_assists","Avant-dernières passes","chaînes d'actions identifiées"),("centre_entry_success","Réussite des entrées en pointe","passes classées avec issue"),("tsap","TSAP : VP, EI, PS","annotation RB, CB, NB, LB, OB, SS"),("ball_contact_time","Durée de contrôle du ballon","début et fin de contrôle")],
 "duels_defense":[("pressure_distance","Distance et intensité de pression","tracking adversaire"),("defensive_reach","Volume défensif / portée des bras","reconstruction 3D"),("interception_time","Temps d'interception","trajectoires temporelles"),("defensive_rotation","Rotations, aides et reprises","tracking collectif"),("offball_creation","Création d'espace sans ballon","tracking collectif"),("rebound_outcome","Rebonds offensifs / défensifs","identifiant de rebond et équipe")],
 "gardiennes":[("save_heatmap","Carte des arrêts et buts encaissés","impact dans la cage"),("save_by_shot_type","Arrêts par type et zone de tir","tir associé à l'arrêt"),("keeper_reaction","Temps de réaction et déplacement","tracking et synchronisation"),("keeper_distribution","Relances réussies / perdues","passes attribuées à la gardienne"),("goals_prevented","Buts évités vs xG après tir","modèle calibré")],
 "possessions":[("possession_duration","Durée et part de possession","début/fin et horloge de jeu"),("goals_per_possession","Buts par possession","possessions complètes identifiées"),("passes_per_possession","Passes par possession","identifiant et couverture des actions"),("transition_duration","Durée des transitions","bornes temporelles"),("counterattack_conversion","Efficacité des contre-attaques","début/fin et issue"),("extra_player_duration","Durée des surnombres","horloge et entrées/sorties"),("formation","Organisation et largeur / profondeur","tracking collectif"),("timeout_impact","Impact avant/après temps mort","possessions complètes horodatées"),("epv","Valeur attendue de possession","modèle validé")],
 "gestion_match":[("on_water_plus_minus","Différentiel de buts en jeu","intervalles et buts horodatés"),("lineup_efficiency","Efficacité des compositions","présence complète des joueuses"),("score_momentum","Dynamique du score","chronologie complète validée"),("shot_clock_at_release","Chrono de possession au tir","lecture horloge"),("decision_quality","Qualité de décision indépendante de l'issue","alternatives pré-action évaluées"),("decision_regret","Coût d'opportunité d'une décision","valeur attendue calibrée"),("scenario_3d","Relecture et scénarios 3D","reconstruction métrique et module 3D")],
 "physique_temps":[("trajectory_map","Cartographie continue des déplacements","tracking calibré"),("swim_speed","Vitesse moyenne et maximale de nage","tracking calibré et temps"),("acceleration","Accélération et décélération","tracking calibré"),("sprint_5m_10m","Temps de sprint sur 5 et 10 m","segments mesurés"),("high_intensity_distance","Distance à haute intensité","seuil individualisé et tracking"),("work_rest","Temps d'effort et récupération","classification temporelle"),("fatigue","Évolution de la charge / fatigue","mesures répétées et contexte"),("vertical_elevation","Élévation verticale","calibration 3D"),("per_minute","Indicateurs par minute jouée","temps de jeu fiable"),("tracking_coverage","Couverture du suivi joueur / ballon","intervalles de visibilité"),("formation_heatmap","Heatmap occupation par joueuse","positions avec durée observée")],
}
def audit_rows(events, roster=()):
    confirmed=[e for e in events if str(e.get("confidence") or "").upper() in {"CONFIRMED","VERIFIED"}]
    sides={s:[e for e in confirmed if e.get("perspective")==s] for s in ("for","against")}
    def group(rows, scope):
        v=reduce_side(rows)
        if scope=="team":
            ids=defaultdict(list)
            for e in rows:
                if e.get("player_id") is not None: ids[e["player_id"]].append(e)
            ex=[exposure(r) for r in ids.values()]
            v["playing_seconds"]=sum(x["playing_seconds"] for x in ex if x["playing_seconds"] is not None) if any(x["playing_seconds"] is not None for x in ex) else None
            v["playing_intervals"]=sum(x["playing_intervals"] for x in ex)
            v["unpaired_markers"]=sum(x["unpaired_markers"] for x in ex)+sum(e.get("event_type") in {"player_in","player_out"} and e.get("player_id") is None for e in rows)
        result=[]
        for section,keys in GROUPS.items():
            for k,label in METRICS:
                if k not in keys.split():continue
                value=v.get(k) if rows else None
                denom=None
                if k in RATES:
                    _,d=RATES[k]
                    denom=sum(v.get(x,0) or 0 for x in d) if isinstance(d,tuple) else v.get(d)
                    if not denom:value=None
                    if k=="penalty_conversion" and any(e.get("phase")=="penalty" and e.get("event_type")=="shot_unknown" for e in rows):value=None
                state="derived_sample" if k in RATES and value is not None else "confirmed_sample" if value is not None else "not_measured"
                if k in {"playing_seconds","distance_m"} and value is not None:state="partial_measurement"
                result.append(dict(key=k,label=label,section=section,value=value,state=state,denominator=denom,requirement="événements confirmés et dénominateur observé" if k in RATES else "annotations confirmées",scope=scope))
            for k,label,req in PENDING.get(section,[]):
                result.append(dict(key=k,label=label,section=section,value=None,state="requires_evidence_or_model",denominator=None,requirement=req,scope=scope))
        return result
    issues=[]
    missing_period=sum(clock(e) is None and tags(e).get("period") not in {"1","2","3","4"} for e in confirmed)
    if missing_period:issues.append(dict(code="missing_period",count=missing_period,detail="Ne pas attribuer automatiquement ces actions au Q1."))
    neutral=sum(e.get("perspective") not in sides for e in confirmed)
    if neutral:issues.append(dict(code="unknown_side",count=neutral,detail="Actions sans équipe certaine exclues des comparaisons."))
    unidentified=sum(e.get("player_id") is None for e in confirmed)
    if unidentified:issues.append(dict(code="unattributed",count=unidentified,detail="Ne pas attribuer les actions à une joueuse par défaut."))
    seen=Counter((e.get("perspective"),e.get("player_id"),e.get("event_type"),e.get("second"),tags(e).get("period"),tags(e).get("segment")) for e in confirmed if e.get("second") is not None)
    duplicate=sum(n-1 for n in seen.values() if n>1)
    if duplicate:issues.append(dict(code="possible_duplicate",count=duplicate,detail="Annotations identiques à vérifier ; aucun effacement automatique."))
    if any(e.get("event_type") in {"assist","key_pass"} for e in confirmed):
        issues.append(dict(code="pass_semantics",count=None,detail="Les catégories passe réussie / clé / décisive doivent être exclusives ou reliées par un identifiant d'action."))
    players=defaultdict(list)
    for s,rows in sides.items():
        for e in rows:
            if e.get("player_id") is not None:players[(s,e["player_id"])].append(e)
    for p in roster:
        players.setdefault(("for",p["id"]),[])
    roster_names={p["id"]:p["name"] for p in roster}
    return dict(version="ultimate-audit-v1",sources=SOURCES,scope="confirmed_sample_only",issues=issues,
                team=group(sides["for"],"team"),opponent=group(sides["against"],"team"),
                players=[dict(side=s,player_id=pid,name=(roster_names.get(pid) if s=="for" else None) or (rows[0].get("player") if rows else None) or "Non nommée",metrics=group(rows,"player")) for (s,pid),rows in players.items()],
                confirmed_count=len(confirmed),excluded_count=len(events)-len(confirmed),
                note="Les valeurs comptent les annotations vérifiées, pas un match intégral. Les indicateurs non raccordés dans ce registre peuvent exister ailleurs dans le logiciel ; aucune valeur n'est inventée.")


def enrich_audit(audit,advanced,identity,statistics):
    """Expose computed values without conflating tagged samples with tracking estimates."""
    def update(rows,key,value,n,requirement,state="derived_sample"):
        for r in rows:
            if r["key"]==key:
                r.update(value=value,denominator=n,requirement=requirement,
                         state=state if value is not None else "not_measured")
                return
    for side,key in (("for","team"),("against","opponent")):
        rr=audit[key];a=advanced["sides"][side];s=statistics[key];track=identity.get("teams",{}).get(side,{})
        for k in ("goals_per_possession","possession_duration","passes_per_possession"):
            x=a[k];update(rr,k,x["value"],x["n"],x["requirement"]+" · "+x["unit"])
        network=a["pass_network"]["edges"]
        update(rr,"pass_network",len(network) if network else None,sum(e["count"] for e in network),"Nombre de liens orientés · réseau détaillé sous le tableau")
        update(rr,"shot_type_split",sum(r.get("shots",0) for r in s["shots"]["types"] if r.get("key")!="unknown") or None,s["shots"]["total"],"Tirs avec technique renseignée · détail dans statistiques de tir")
        update(rr,"shot_speed",a["numeric"]["shot_speed_kmh"]["mean"]["value"],a["numeric"]["shot_speed_kmh"]["mean"]["n"],"Moyenne km/h sur mesures calibrées renseignées")
        update(rr,"shot_release_height",a["numeric"]["shot_release_height_m"]["mean"]["value"],a["numeric"]["shot_release_height_m"]["mean"]["n"],"Hauteur moyenne (m) · calibration déclarée")
        update(rr,"tracking_coverage",track.get("player_seconds") if track.get("players_measured") else None,track.get("players_measured"),"Secondes-joueuses de suivi métrique observé (pas temps de jeu)","partial_measurement")
        update(rr,"trajectory_map",track.get("distance_m"),track.get("players_measured"),"Somme des distances suivies (m) · identités revues, sans extrapolation","partial_measurement")
    index={(p["side"],p["player_id"]):p for p in advanced["players"]}
    for p in audit["players"]:
        a=index.get((p["side"],p["player_id"]))
        if not a:continue
        ts=a["tsap"]
        update(p["metrics"],"tsap",ts["performance_score"],ts["sample"],"Score TSAP sur catégories explicitement classées")
        for k,raw,req in [("shot_speed","shot_speed_kmh","Moyenne km/h"),("shot_release_height","shot_release_height_m","Hauteur moyenne (m)"),("pass_length","pass_distance_m","Longueur moyenne (m)"),("swim_speed","max_swim_speed_mps","Maximum m/s")]:
            x=a["numeric"][raw]["max" if k=="swim_speed" else "mean"]
            update(p["metrics"],k,x["value"],x["n"],req+" · mesures calibrées renseignées")
