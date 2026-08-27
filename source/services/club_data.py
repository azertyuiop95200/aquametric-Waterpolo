from sqlalchemy import select, delete
from models import Club, Team, TrainingSession, TeamSeasonSummary, OfficialFixture, OfficialDataSource, MatchLibraryItem, LibraryPlayerMatchStat

GRANVILLE_SOURCE = "https://www.granvillewaterpolo.com/n1-f%C3%A9minine/"
GRANVILLE_TRAINING_SOURCE = "https://www.granvillewaterpolo.com/2026/08/20/inscriptions-pour-la-saison-2026-2027/"
GRANVILLE_FFN_CALENDAR = "https://www.extranat.fr/waterpolo/cgi-bin/wp_calendar.php?action=structure&structure=3021"

GRANVILLE_RESULTS_2025_26 = [
    ("2025-10-04", "Granville Water Polo", "St Jean d'Angely", 16, 14, "home"),
    ("2025-11-08", "Montgeron", "Granville Water Polo", 7, 14, "away"),
    ("2025-11-15", "Granville Water Polo", "Arras", 10, 12, "home"),
    ("2025-12-06", "Granville Water Polo", "Limoges", 23, 10, "home"),
    ("2026-01-17", "Libellules", "Granville Water Polo", 10, 11, "away"),
    ("2026-01-31", "Granville Water Polo", "Laval", 16, 12, "home"),
    ("2026-02-07", "NCA Saint Jean d'Angely", "Granville Water Polo", 13, 5, "away"),
    ("2026-03-14", "Granville Water Polo", "Montgeron", 18, 5, "home"),
    ("2026-03-21", "Limoges", "Granville Water Polo", 4, 14, "away"),
    ("2026-03-28", "Arras", "Granville Water Polo", 9, 13, "away"),
    ("2026-04-25", "Granville Water Polo", "Libellules", 11, 9, "home"),
    ("2026-05-09", "Laval", "Granville Water Polo", 14, 15, "away"),
]

GRANVILLE_TRAINING = [
    ("Monday", "18:55", "21:15", "Elite women — water polo / prep", "Centre aquatique L'Hippocampe"),
    ("Tuesday", "06:40", "08:15", "Elite women — morning water session", "Centre aquatique L'Hippocampe"),
    ("Tuesday", "18:45", "21:00", "Elite women — water polo / prep", "Centre aquatique L'Hippocampe"),
    ("Wednesday", "18:50", "21:30", "Elite women — water polo / prep", "Centre aquatique L'Hippocampe"),
    ("Thursday", "06:40", "08:15", "Elite women — morning water session", "Centre aquatique L'Hippocampe"),
    ("Friday", "18:50", "21:30", "Elite women — water polo / prep", "Centre aquatique L'Hippocampe"),
    ("Saturday", "08:00", "10:00", "Elite women — water polo", "Centre aquatique L'Hippocampe"),
]

# Official FFN extraNat Elite Féminine regular-season calendar for Granville, 2026-27.
GRANVILLE_ELITE_2026_27 = [
    ("2026-09-12 20:00", "Lille UC Métropole Water-Polo", "Granville Waterpolo"),
    ("2026-09-19 20:00", "Granville Waterpolo", "Union St-Bruno Bordeaux"),
    ("2026-09-26 20:00", "Olympic Nice Natation", "Granville Waterpolo"),
    ("2026-10-03 20:00", "Granville Waterpolo", "Taverny Sports Nautiques 95"),
    ("2026-10-17 20:00", "Toulon Waterpolo", "Granville Waterpolo"),
    ("2026-10-24 20:00", "Granville Waterpolo", "Sporting Club des Nageurs de Choisy le Roi"),
    ("2026-11-21 20:00", "Granville Waterpolo", "Paris Water-Polo"),
    ("2026-12-19 20:00", "Cercle des Nageurs de Marseille", "Granville Waterpolo"),
    ("2027-01-09 20:00", "Grand Nancy Aquatique Club", "Granville Waterpolo"),
    ("2027-01-23 20:00", "Granville Waterpolo", "Lille UC Métropole Water-Polo"),
    ("2027-02-06 20:00", "Union St-Bruno Bordeaux", "Granville Waterpolo"),
    ("2027-02-20 20:00", "Granville Waterpolo", "Olympic Nice Natation"),
    ("2027-02-27 20:00", "Taverny Sports Nautiques 95", "Granville Waterpolo"),
    ("2027-03-06 20:00", "Granville Waterpolo", "Toulon Waterpolo"),
    ("2027-03-20 20:00", "Sporting Club des Nageurs de Choisy le Roi", "Granville Waterpolo"),
    ("2027-04-03 20:00", "Paris Water-Polo", "Granville Waterpolo"),
    ("2027-04-17 20:00", "Granville Waterpolo", "Cercle des Nageurs de Marseille"),
    ("2027-04-24 20:00", "Granville Waterpolo", "Grand Nancy Aquatique Club"),
]

LIBRARY_MATCHES = [
    {
        "external_key":"EA-CLW-2024-FINAL-SABA-OLY", "title":"Astralpool CN Sabadell vs Olympiacos — Champions League Women final", "competition":"European Aquatics Champions League Women", "season":"2023-2024", "entity_type":"club", "team_a":"Astralpool CN Sabadell", "team_b":"Olympiacos SFP", "score_a":16, "score_b":10, "quarters":[[2,1],[5,3],[6,3],[3,3]],
        "video_url":"https://www.youtube.com/watch?v=pIJu8tQT7-I", "video_kind":"full_match", "official":"https://europeanaquatics.org/sensational-sabadell-storm-to-seventh-champions-league-title/", "status":"officially_sourced",
        "summary":"Sabadell broke the final open with a seven-goal run in the second half. The official report highlights rapid punishment of offensive mistakes, counterattack conversion and decisive 6-on-5 defence.",
        "team_stats":{"Astralpool CN Sabadell":{"final_score":16,"decisive_run":"7-0","halftime":"7-4"},"Olympiacos SFP":{"final_score":10,"halftime":"4-7"}},
        "players":[("Astralpool CN Sabadell","Sofia Giustini",5,None,"five goals in the official match narrative"),("Astralpool CN Sabadell","Irene Gonzalez",None,None,"multiple decisive goals referenced in official report"),("Olympiacos SFP","Vasiliki Plevritou",None,None,"multiple goals referenced in official report")]
    },
    {
        "external_key":"EA-CLW-2025-FINAL-SABA-SA", "title":"Astralpool CN Sabadell vs CN Sant Andreu — Champions League Women final", "competition":"European Aquatics Champions League Women", "season":"2024-2025", "entity_type":"club", "team_a":"Astralpool CN Sabadell", "team_b":"CN Sant Andreu", "score_a":8, "score_b":9, "quarters":[[3,2],[2,1],[2,3],[1,3]],
        "video_url":"", "video_kind":"official_report", "official":"https://europeanaquatics.org/sant-andreu-stun-sabadell-to-secure-champions-league-crown/", "status":"officially_sourced",
        "summary":"Sant Andreu led only once: with 2.4 seconds remaining. A 3-0 closing run turned an 8-6 deficit into the club's first Champions League title.",
        "team_stats":{"Astralpool CN Sabadell":{"final_score":8,"late_lead":"8-6"},"CN Sant Andreu":{"final_score":9,"closing_run":"3-0","winner":"2.4 seconds remaining"}},
        "players":[("CN Sant Andreu","Queralt Anton",None,None,"scored the decisive late winner according to the official report")]
    },

    {
        "external_key":"WA-U20W-2025-SF-ESP-GRE", "title":"Spain vs Greece — U20 Women semifinal", "competition":"World Aquatics Women's U20 World Championships", "season":"2025", "entity_type":"national_team", "team_a":"Spain", "team_b":"Greece", "score_a":11, "score_b":9, "quarters":[[0,3],[3,4],[3,0],[5,2]],
        "video_url":"https://www.youtube.com/watch?v=bF-Am10VtF4", "video_kind":"full_match", "official":"https://www.worldaquatics.com/news/4342094/spain-makes-third-straight-u20-womens-final", "status":"officially_sourced",
        "summary":"Spain recovered from 6-1 down. A 3-0 third quarter and 5-2 fourth quarter reversed the match; power-play execution and goalkeeper saves were central to the comeback.",
        "team_stats":{"Spain":{"shots":36,"extra_player":"4/9","penalties":"3/4","steals":4,"goalkeeper_saves":13},"Greece":{"shots":35,"extra_player":"2/6","penalties":"0/1","steals":2,"goalkeeper_saves":9}},
        "players":[("Spain","Isabel Piralkova",5,None,"Olympic champion; five goals in official report"),("Greece","Nefeli Krassa",2,None,"two goals"),("Greece","Aspasia Fouraki",2,None,"two goals"),("Greece","Foteini Tricha",2,None,"two goals"),("Greece","Ariadni Karampetsou",2,None,"two goals"),("Greece","Nikoleta Kyriakopoulou",None,9,"nine saves")]
    },
    {
        "external_key":"WA-U20W-2025-F-USA-ESP", "title":"USA vs Spain — U20 Women gold medal", "competition":"World Aquatics Women's U20 World Championships", "season":"2025", "entity_type":"national_team", "team_a":"United States", "team_b":"Spain", "score_a":16, "score_b":15, "quarters":[[3,3],[3,3],[6,5],[4,4]],
        "video_url":"https://www.worldaquatics.com/videos/4335116/usa-vs-esp-womens-u20-water-polo-2025-thrilling-gold-medal-clash", "video_kind":"full_session", "official":"https://www.worldaquatics.com/news/4342802/usa-rumbles-spain-for-record-extending-fifth-u20-crown", "status":"officially_sourced",
        "summary":"A one-goal world final decided by USA's ability to hold a late three-goal cushion. The official report highlights extra-player efficiency and a narrow shot-volume edge for Spain.",
        "team_stats":{"United States":{"shots":31,"extra_player":"7/12","penalties":"2 scored","steals":4},"Spain":{"shots":32,"extra_player":"5/7","penalties":"2/3","steals":7}},
        "players":[("United States","Lucy Haaland-Ford",4,None,"Player of the Final"),("United States","Julia Bonaguidi",3,None,"three goals"),("United States","Charlotte Raisin",2,None,"two goals"),("United States","Kamryn Barone",2,None,"two goals"),("United States","Emily Ausmus",2,None,"two goals; tournament MVP"),("United States","Christine Carpenter",None,8,"eight saves"),("Spain","Irene Casado",5,None,"five goals"),("Spain","Carlota Penalver",4,None,"four goals"),("Spain","Isabel Piralkova",3,None,"three goals")]
    },
    {
        "external_key":"WA-U20W-2025-BRONZE-ITA-GRE", "title":"Italy vs Greece — U20 Women bronze medal", "competition":"World Aquatics Women's U20 World Championships", "season":"2025", "entity_type":"national_team", "team_a":"Italy", "team_b":"Greece", "score_a":7, "score_b":10, "quarters":[[2,1],[2,2],[1,6],[2,1]],
        "video_url":"", "video_kind":"official_report", "official":"https://www.worldaquatics.com/news/4342802/usa-rumbles-spain-for-record-extending-fifth-u20-crown", "status":"officially_sourced",
        "summary":"Greece broke the match open with a 6-1 third quarter. The official report records strong extra-player execution despite Italy taking more shots.",
        "team_stats":{"Italy":{"shots":34,"extra_player":"1/5","steals":4},"Greece":{"shots":26,"extra_player":"5/10","steals":3,"penalties":"1/1"}},
        "players":[("Greece","Nefeli Krassa",2,None,"two goals"),("Greece","Dionysia Koureta",2,None,"two goals"),("Greece","Ariadni Karampetsou",2,None,"two goals"),("Greece","Rafaela Saltamanika",2,None,"two goals"),("Italy","Paola di Maria",2,None,"two goals")]
    },
    {
        "external_key":"WA-U20W-2025-7TH-CRO-BRA", "title":"Croatia vs Brazil — U20 Women classification 7-8", "competition":"World Aquatics Women's U20 World Championships", "season":"2025", "entity_type":"national_team", "team_a":"Croatia", "team_b":"Brazil", "score_a":17, "score_b":11, "quarters":[[5,5],[5,3],[2,3],[5,0]],
        "video_url":"", "video_kind":"official_report", "official":"https://www.worldaquatics.com/news/4342802/usa-rumbles-spain-for-record-extending-fifth-u20-crown", "status":"officially_sourced",
        "summary":"Croatia separated late with a 5-0 final quarter. Penalty conversion and a strong final phase were decisive.",
        "team_stats":{"Croatia":{"shots":36,"extra_player":"1/1","penalties":"4/5","steals":5},"Brazil":{"shots":20,"extra_player":"4/12 defended by CRO","penalties":"1/1","steals":3}},
        "players":[("Croatia","Iva Rozic",5,None,"five goals"),("Croatia","Nika Alamat",4,None,"four goals"),("Croatia","Latica Medvesek",None,8,"eight saves"),("Brazil","Maiah Nascimento",3,None,"three goals"),("Brazil","Leticia Lorieto",3,None,"three goals")]
    },
]

def ensure_granville_team(db, owner_id):
    club = db.scalar(select(Club).where(Club.name == "Granville Water Polo"))
    if not club:
        club=Club(name="Granville Water Polo",country="France",division="Elite / N1",category="Women",is_demo=True)
        db.add(club); db.flush()
    team = db.scalar(select(Team).where(Team.owner_id==owner_id, Team.name=="Granville Water Polo — Women"))
    if not team:
        team=Team(name="Granville Water Polo — Women",club_id=club.id,owner_id=owner_id,category="Women")
        db.add(team); db.flush()
    # Upgrade older AquaMetric databases as soon as the 2026-27 published grid is known.
    current_training = db.scalar(select(TrainingSession).where(TrainingSession.team_id==team.id, TrainingSession.source_season=="2026-2027"))
    if not current_training:
        db.execute(delete(TrainingSession).where(TrainingSession.team_id==team.id))
        for wd,st,en,typ,venue in GRANVILLE_TRAINING:
            db.add(TrainingSession(team_id=team.id,weekday=wd,start_time=st,end_time=en,session_type=typ,venue=venue,source_season="2026-2027",source_url=GRANVILLE_TRAINING_SOURCE,is_official=True,note="Published 20 Aug 2026. Club notes that Elite/N1/CAF strength sessions are not included yet and will be clarified by coaches."))
    if not db.scalar(select(TeamSeasonSummary).where(TeamSeasonSummary.team_id==team.id,TeamSeasonSummary.season=="2025-2026")):
        gf=ga=w=l=0
        for _,home,away,hs,as_,_ in GRANVILLE_RESULTS_2025_26:
            gran=hs if home.startswith("Granville") else as_; opp=as_ if home.startswith("Granville") else hs
            gf+=gran; ga+=opp; w+=gran>opp; l+=gran<opp
        db.add(TeamSeasonSummary(team_id=team.id,season="2025-2026",competition="Nationale 1 Féminine",final_position=2,played=len(GRANVILLE_RESULTS_2025_26),won=w,lost=l,goals_for=gf,goals_against=ga,source_url=GRANVILLE_SOURCE,source_note="Final position confirmed by Granville Water Polo; record reconstructed from the published match list."))
    source = db.scalar(select(OfficialDataSource).where(OfficialDataSource.name=="Granville Water Polo — club site"))
    if not source:
        source=OfficialDataSource(name="Granville Water Polo — club site",provider="club_official",region="France",url=GRANVILLE_SOURCE,parser_kind="seeded_club_data",refresh_interval_hours=24,enabled=True)
        db.add(source); db.flush()
    for idx,(date,home,away,hs,as_,_) in enumerate(GRANVILLE_RESULTS_2025_26):
        key=f"granville-n1f-2526-{idx}"
        if not db.scalar(select(OfficialFixture).where(OfficialFixture.external_key==key)):
            db.add(OfficialFixture(source_id=source.id,external_key=key,competition="Nationale 1 Féminine",season="2025-2026",category="Women",start_text=date,home_team=home,away_team=away,home_score=hs,away_score=as_,status="finished",venue="Granville" if home.startswith("Granville") else "Away",source_url=GRANVILLE_SOURCE))

    ffn = db.scalar(select(OfficialDataSource).where(OfficialDataSource.name=="FFN extraNat — Granville calendar"))
    if not ffn:
        ffn=OfficialDataSource(name="FFN extraNat — Granville calendar",provider="FFN extraNat",region="France",url=GRANVILLE_FFN_CALENDAR,parser_kind="ffn_granville_seed",refresh_interval_hours=6,enabled=True)
        db.add(ffn); db.flush()
    for idx,(date,home,away) in enumerate(GRANVILLE_ELITE_2026_27, start=1):
        key=f"ffn-elitef-2627-granville-j{idx}"
        row=db.scalar(select(OfficialFixture).where(OfficialFixture.external_key==key))
        if not row:
            db.add(OfficialFixture(source_id=ffn.id,external_key=key,competition="Elite Féminine",season="2026-2027",category="Women",start_text=date,home_team=home,away_team=away,status="scheduled",venue="Granville" if home.lower().startswith("granville") else "Away",source_url=GRANVILLE_FFN_CALENDAR))
    db.commit(); return team

def seed_library(db):
    import json
    for item in LIBRARY_MATCHES:
        row=db.scalar(select(MatchLibraryItem).where(MatchLibraryItem.external_key==item['external_key']))
        if not row:
            row=MatchLibraryItem(external_key=item['external_key'],title=item['title'],competition=item['competition'],season=item['season'],entity_type=item['entity_type'],team_a=item['team_a'],team_b=item['team_b'],score_a=item['score_a'],score_b=item['score_b'],quarter_scores_json=json.dumps(item['quarters']),video_url=item['video_url'],video_kind=item['video_kind'],official_source_url=item['official'],analysis_status=item['status'],tactical_summary=item['summary'],team_stats_json=json.dumps(item['team_stats']))
            db.add(row); db.flush()
            for team,name,goals,saves,note in item['players']:
                db.add(LibraryPlayerMatchStat(library_match_id=row.id,team_name=team,player_name=name,goals=goals,saves=saves,note=note))
    db.commit()
