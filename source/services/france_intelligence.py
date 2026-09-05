from sqlalchemy import select
from models import PlayerIntelligenceProfile, PlayerSourceRecord, PlayerMatchMetric, FranceSquadMembership, ScoutingTeam, ScoutingPlayer
from services.france_women_roster_update_2026 import seed_france_women_roster_update_2026

FFN_2022 = "https://www.ffnatation.fr/actualites/actu-grand-public/florian-bruzzo-la-onzieme-equipe-du-monde"
FFN_2023 = "https://www.ffnatation.fr/sites/default/files/fields/press/pdf/dp_fukuoka_2023_vf5_compressed.pdf"
WA_2024 = "https://www.worldaquatics.com/news/4056084/womens-water-polo-paris-2024-olympic-games-confirmed-team-player-rosters"
FFN_2025 = "https://www.ffnatation.fr/sites/default/files/2025-07/DP%20FSINGAPOUR%202025%20V9juillet.pdf"
WA_2025_REPORT = "https://resources.fina.org/fina/document/2026/01/29/d065bb42-328a-4922-874e-291f9f8fea36/2025_Singapore_WP_Report_F.pdf"
FFN_2026 = "https://www.ffnatation.fr/sites/default/files/2026-01/DP%20FUNCHAL%202026_VF.pdf"
EA_2026_FINAL = "https://europeanaquatics.org/ewpc-2026/funchal/funchal-2026-dutch-delight-as-netherlands-secure-second-successive-european-crown-with-epic-shootout-victory/"

FRANCE_CYCLES = [
    {
        "year": 2022, "competition": "World Championships — Budapest", "result": "8th — best World Championship finish",
        "roster_kind": "match_sheet", "source": FFN_2022,
        "players": ["Lou Counil","Estelle Millot","Léa Bachelier","Aurore Sacre","Louise Guillet","Géraldine Mahieu","Clémentine Valverde","Aurélie Battu","Adeline Sacre","Yaëlle Deschampt","Marie Barbieux","Audrey Daule","Lorène Derenty"],
        "note": "Final-match lineup evidence from FFN reporting; this is not presented as a full-season squad registry."
    },
    {
        "year": 2023, "competition": "World Championships — Fukuoka", "result": "World Championship cycle",
        "roster_kind": "prelist", "source": FFN_2023,
        "players": ["Lara Andres","Aurélie Battu","Camelia Bouloukbachi","Juliette Dhalluin","Audrey Daule","Louise Guillet","Erica Hardy","Orsolya Hertzka","Valentine Heurtaux","Viviane Kretzmann-Bahia","Pasiphaé Martineaud-Perret","Estelle Millot","Camille Radosavljevic","Tiziana Raspo","Mia Rycraw","Ema Vernoux","Chloé Vidal"],
        "note": "FFN pre-list of 17; 13 were to be selected. Membership is marked pre-list rather than final roster."
    },
    {
        "year": 2024, "competition": "Olympic Games — Paris", "result": "9th",
        "roster_kind": "official", "source": WA_2024,
        "players": ["Lara Andres","Camelia Bouloukbachi","Aurélie Battu","Audrey Daule","Juliette Dhalluin","Louise Guillet","Orsolya Hertzka","Valentine Heurtaux","Pasiphaé Martineaud-Peret","Tiziana Raspo","Camille Radosavljevic","Mia Rycraw","Ema Vernoux"],
        "note": "Confirmed Olympic roster."
    },
    {
        "year": 2025, "competition": "World Championships — Singapore", "result": "12th",
        "roster_kind": "prelist", "source": FFN_2025,
        "players": ["Lara Andres","Arianna Banchi","Jade Boughrara","Emma Duflos","Erica Hardy","Valentine Heurtaux","Lou Jean-Michel","Elhyne Kilic-Pegourie","Eszter Lefebvre","Pasiphaé Martineaud-Perret","Myriam Ouchache","Camille Radosavljevic","Tiziana Raspo","Ema Vernoux","Lily Vernoux"],
        "note": "FFN competition press kit lists a pre-list; World Aquatics performance report supplies tournament-level metrics."
    },
    {
        "year": 2026, "competition": "European Championships — Funchal", "result": "8th",
        "roster_kind": "official", "source": FFN_2026,
        "players": ["Lara Andres","Arianna Banchi","Kahena Benlekbir","Jade Boughrara","Camelia Bouloukbachi","Léopoldine Burle","Lana Di Fraja","Emma Duflos","Valentine Heurtaux","Elhyne Kilic-Pegourie","Eszter Lefebvre","Ona Pourtau Sire","Tiziana Raspo","Romane Secheresse","Ema Vernoux"],
        "note": "FFN official Funchal roster; European Aquatics final ranking lists France 8th."
    },
]

ROLE_2026 = {
    "Camelia Bouloukbachi":"Arrière pointe / demi", "Léopoldine Burle":"Ailière", "Lana Di Fraja":"Polyvalente",
    "Emma Duflos":"Polyvalente", "Valentine Heurtaux":"Polyvalente", "Elhyne Kilic-Pegourie":"Pointe",
    "Eszter Lefebvre":"Gardienne", "Ona Pourtau Sire":"Polyvalente", "Tiziana Raspo":"Arrière pointe",
    "Romane Secheresse":"Gardienne", "Ema Vernoux":"Ailière / demi", "Kahena Benlekbir":"Ailière / demi",
    "Lara Andres":"Polyvalente", "Arianna Banchi":"Polyvalente", "Jade Boughrara":"Polyvalente",
}

SINGAPORE_2025_PLAYER_METRICS = {
    "Ema Vernoux": [("tournament_goals",15,"goals",1.0),("team_goal_contribution",29,"%",1.0),("shot_efficiency",50,"%",1.0)],
    "Pasiphaé Martineaud-Perret": [("goalkeeper_saves",65,"saves",1.0),("shots_on_goal_received",127,"shots",1.0),("save_efficiency",51,"%",1.0)],
    "Eszter Lefebvre": [("goalkeeper_saves",8,"saves",1.0),("shots_on_goal_received",23,"shots",1.0),("save_efficiency",35,"%",1.0)],
    "Lou Jean-Michel": [("rebounds_per_game",1.17,"/game",1.0),("matches_observed",6,"matches",1.0)],
    "Myriam Ouchache": [("blocks_per_game",0.83,"/game",1.0),("matches_observed",6,"matches",1.0)],
    "Camille Radosavljevic": [("blocks_per_game",0.80,"/game",1.0),("matches_observed",5,"matches",1.0)],
    "Emma Duflos": [("sprints_per_game",3.50,"/game",1.0),("matches_observed",4,"matches",1.0)],
}

FRANCE_2025_TEAM = {
    "final_rank": 12, "world_ranking_after": 10,
    "steals": 35, "steals_per_game": 5.83, "rebounds": 29, "rebounds_per_game": 4.83,
    "blocks": 18, "blocks_per_game": 3.00, "saves": 51, "shots_on_goal_received": 120, "save_efficiency": 43,
    "shot_distribution": {"Action":64,"Centre":6,"Driving":0,"Extra player":21,"6m":0,"Penalty shoot-out":6,"Counterattack":0},
    "xfg": {"Action":4.17,"Centre":0.83,"Extra player":2.33,"Total":7.33},
    "source": WA_2025_REPORT,
}


def _profile(db, name):
    p = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name==name))
    if not p:
        p = PlayerIntelligenceProfile(canonical_name=name, nationality="FRA", current_national_team="France — Women Senior", roster_status="france_history", confidence_score=.82)
        db.add(p); db.flush()
    if not p.current_national_team or "France" in p.current_national_team:
        p.current_national_team = "France — Women Senior"
    if not p.nationality: p.nationality="FRA"
    if name in ROLE_2026 and (not p.role or p.role in {"Field player","Senior international","Role to confirm"}): p.role=ROLE_2026[name]
    return p


def _source_once(db,p,label,url,season,claim,trust="official"):
    row=db.scalar(select(PlayerSourceRecord).where(PlayerSourceRecord.profile_id==p.id,PlayerSourceRecord.url==url,PlayerSourceRecord.label==label))
    if not row:
        db.add(PlayerSourceRecord(profile_id=p.id,source_type="france_national_team",label=label,url=url,season=season,trust_level=trust,claim_text=claim))


def _metric_once(db,p,metric,value,unit,source,note=""):
    row=db.scalar(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id==p.id,PlayerMatchMetric.library_match_id==None,PlayerMatchMetric.metric==metric,PlayerMatchMetric.source_url==source))
    if not row:
        db.add(PlayerMatchMetric(profile_id=p.id,library_match_id=None,metric=metric,value=float(value),unit=unit,provenance="official_tournament_report",confidence_score=1.0,source_url=source,note=note))


def seed_france_intelligence(db):
    for cycle in FRANCE_CYCLES:
        for name in cycle["players"]:
            p=_profile(db,name)
            membership=db.scalar(select(FranceSquadMembership).where(FranceSquadMembership.profile_id==p.id,FranceSquadMembership.year==cycle["year"],FranceSquadMembership.competition==cycle["competition"]))
            if not membership:
                db.add(FranceSquadMembership(profile_id=p.id,year=cycle["year"],competition=cycle["competition"],roster_kind=cycle["roster_kind"],role_at_event=ROLE_2026.get(name,""),source_url=cycle["source"],note=cycle["note"]))
            _source_once(db,p,f"France {cycle['year']} — {cycle['competition']}",cycle["source"],str(cycle["year"]),cycle["note"])
    for name, metrics in SINGAPORE_2025_PLAYER_METRICS.items():
        p=_profile(db,name)
        for metric,value,unit,conf in metrics:
            _metric_once(db,p,metric,value,unit,WA_2025_REPORT,"World Aquatics Singapore 2025 Results Report")
    db.commit()
    # Apply the latest named French Elite women roster intelligence only after the
    # canonical profiles have been seeded, so newer club evidence can supersede a
    # historical club-at-event value without deleting that official history.
    seed_france_women_roster_update_2026(db)


def france_dashboard(db):
    memberships=db.scalars(select(FranceSquadMembership).order_by(FranceSquadMembership.year,FranceSquadMembership.id)).all()
    profiles={p.id:p for p in db.scalars(select(PlayerIntelligenceProfile)).all()}
    appearances={}
    for m in memberships:
        appearances.setdefault(m.profile_id,[]).append(m)
    players=[]
    for pid,mems in appearances.items():
        p=profiles.get(pid)
        if not p: continue
        metrics=db.scalars(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id==pid,PlayerMatchMetric.source_url==WA_2025_REPORT)).all()
        players.append({"profile":p,"years":[m.year for m in mems],"appearances":len(mems),"metrics":{x.metric:x for x in metrics}})
    players.sort(key=lambda x:(-x["appearances"],x["profile"].canonical_name))
    french_teams=db.scalars(select(ScoutingTeam).where(ScoutingTeam.team_type=="club",ScoutingTeam.country=="France").order_by(ScoutingTeam.priority.desc())).all()
    league=[]
    for t in french_teams:
        count=db.query(ScoutingPlayer).filter(ScoutingPlayer.scouting_team_id==t.id).count()
        league.append({"team":t,"players":count,"coverage":"roster" if count else "refresh_required"})
    return {"cycles":FRANCE_CYCLES,"players":players,"team2025":FRANCE_2025_TEAM,"league":league,"years":[2022,2023,2024,2025,2026]}
