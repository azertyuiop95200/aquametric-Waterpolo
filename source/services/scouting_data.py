from sqlalchemy import select
from models import ScoutingTeam, ScoutingPlayer

FFN_GRANVILLE_RESULTS = "https://www.extranat.fr/waterpolo/cgi-bin/wp_results.php?action=structure&structure=3021"
FFN_GRANVILLE_CAL = "https://www.extranat.fr/waterpolo/cgi-bin/wp_calendar.php?action=structure&structure=3021"
WA_PARIS_2024_ROSTERS = "https://www.worldaquatics.com/news/4056084/womens-water-polo-paris-2024-olympic-games-confirmed-team-player-rosters"
WA_U20_2025 = "https://www.worldaquatics.com/competitions/4887/world-aquatics-women-s-u20-water-polo-championships"

# Historical rosters are deliberately marked as historical/pending refresh. They are scouting inputs,
# never silently presented as confirmed current-season registrations.
SCOUTING_TEAMS = [
    {
        "key":"club-fr-granville-w-elite", "name":"Granville Water Polo", "team_type":"club", "country":"France",
        "competition":"FF Natation — Elite Féminine", "season":"2026-2027", "status":"historical_2025_26_pending_2026_27_confirmation",
        "source":FFN_GRANVILLE_RESULTS, "note":"Players observed on official FFN match sheets in 2025-26. 2026-27 roster must be refreshed from new match sheets/club announcements.", "priority":100,
        "players":[
            (1,"Rumina Edgerton",2002,"CAN","Goalkeeper"),(2,"Morgane Le Berre",2008,"FRA","Field player"),(3,"Capucine Pillais",2010,"FRA","Centre / field player"),
            (4,"Cléo Kubas",2010,"FRA","Field player"),(5,"Luce Berthonneau",2009,"FRA","Field player"),(6,"Amandine Laîné",2009,"FRA","Field player"),
            (7,"Sofia Dan",2012,"FRA","Field player"),(8,"Eleni Bovali",2003,"GRE","Field player"),(9,"Clémence Letourneur",2011,"FRA","Field player"),
            (10,"Mauranne Cosnefroy",2010,"FRA","Field player"),(11,"Hanae Pezres",2010,"FRA","Field player"),(12,"Sofia Kolovou",2002,"GRE","Field player"),
            (12,"Mariia Lytvyniuk",2007,"UKR","Field player"),(13,"Maëlle Hequin",2007,"FRA","Goalkeeper / field use to verify"),(14,"Carmen Sourdrille-Arnal",2008,"FRA","Field player"),
        ]
    },
    {
        "key":"club-fr-lille-uc-w-elite", "name":"Lille UC Métropole Water-Polo", "team_type":"club", "country":"France",
        "competition":"FF Natation — Elite Féminine", "season":"2026-2027", "status":"historical_roster_pending_2026_27_confirmation",
        "source":"https://www.extranat.fr/waterpolo/cgi-bin/wp_results.php?action=structure&structure=422", "note":"Historical scouting list from FFN match sheets; refresh when 2026-27 sheets are published.", "priority":95,
        "players":[
            (None,"Eszter Lefebvre",2003,"FRA","Field player"),(None,"Anna Pal",2001,"HUN","Field player"),(None,"Elhyne Kilic-Pegourie",2007,"FRA","Field player"),
            (None,"Lara Andres",2006,"FRA","Field player"),(None,"Giulia Sponza",2008,"ITA","Field player"),(None,"Clémence Goulu",2010,"FRA","Field player"),
            (None,"Lana Di Fraja",2006,"FRA","Field player"),(None,"Cecilia Nardini",1999,"ITA","Field player"),(None,"Lily Vernoux",2007,"FRA","Field player"),
            (None,"Carmen Baringo Romero",1998,"ESP","Field player"),(None,"Myriam Lizotte",1999,"CAN","Field player"),(None,"Maéline Ribeiro de Souza",2011,"BEL","Field player"),
            (None,"Eszter Kozár",2002,"FIN","Field player"),(None,"Mariam Diara Ndiaye",2007,"USA","Field player"),
        ]
    },
    {
        "key":"club-fr-usb-bordeaux-w-elite", "name":"Union St-Bruno Bordeaux", "team_type":"club", "country":"France",
        "competition":"FF Natation — Elite Féminine", "season":"2026-2027", "status":"historical_roster_pending_2026_27_confirmation",
        "source":"https://www.extranat.fr/waterpolo/cgi-bin/wp_results.php?action=structure&structure=348", "note":"Historical scouting list from FFN match sheets; refresh when 2026-27 sheets are published.", "priority":94,
        "players":[
            (None,"Pasiphaé Martineaud-Peret",2005,"FRA","Field player"),(None,"Justine Turbeau",2004,"FRA","Field player"),(None,"Robyn Jennifer Currie",2002,"CAN","Field player"),
            (None,"Juliette Ribes",2004,"FRA","Field player"),(None,"Chloé Faure",1993,"FRA","Field player"),(None,"Lou Jean Michel",2003,"FRA","Field player"),
            (None,"Kenza Chadly",1999,"FRA","Field player"),(None,"Anne-Fleur Doucereux",1993,"FRA","Field player"),(None,"Marion Horcholle",1997,"FRA","Field player"),
            (None,"Noor El Ouaret",2011,"FRA","Field player"),(None,"Sherihene Ben Mouna",2008,"FRA","Field player"),(None,"Elizabeth Grace Estelle Birch",2002,"CAN","Field player"),
            (None,"Romane Secheresse",2009,"FRA","Field player"),(None,"Maëlle Lartigaut",2008,"FRA","Field player"),
        ]
    },
    {
        "key":"club-fr-nice-w-elite", "name":"Olympic Nice Natation", "team_type":"club", "country":"France",
        "competition":"FF Natation — Elite Féminine", "season":"2026-2027", "status":"roster_refresh_required",
        "source":"https://www.extranat.fr/waterpolo/cgi-bin/wp_calendar.php?action=structure&structure=1209", "note":"2026-27 opponent confirmed by FFN calendar. Roster ingestion queued from official match sheets/club announcements.", "priority":93, "players":[]
    },
    {
        "key":"club-fr-taverny-w-elite", "name":"Taverny Sports Nautiques 95", "team_type":"club", "country":"France",
        "competition":"FF Natation — Elite Féminine", "season":"2026-2027", "status":"historical_roster_pending_2026_27_confirmation",
        "source":"https://www.extranat.fr/waterpolo/cgi-bin/wp_calendar.php?action=structure&structure=1396", "note":"Historical roster; refresh against 2026-27 sheets.", "priority":92,
        "players":[
            (None,"Zélie Calime",None,"FRA","Field player"),(None,"Olivia Soler",None,"FRA","Field player"),(None,"Jade Boughrara",None,"FRA","Field player"),
            (None,"Zia Wasterlain",None,"FRA","Field player"),(None,"Eléonore Rigault",None,"FRA","Field player"),(None,"Oriane Lafin",None,"FRA","Field player"),
            (None,"Aurore Mayet Toussaint",None,"FRA","Field player"),(None,"Justine Moizant",None,"FRA","Field player"),(None,"Anastasiia Zelenko",None,"UKR","Field player"),
            (None,"Marine Lanoëlle",None,"FRA","Field player"),(None,"Sohane Bentaleb",None,"FRA","Field player"),(None,"Feryel Bentaleb",None,"FRA","Field player"),(None,"Anna Bonaventure",None,"FRA","Field player"),
        ]
    },
    {
        "key":"club-fr-toulon-w-elite", "name":"Toulon Waterpolo", "team_type":"club", "country":"France",
        "competition":"FF Natation — Elite Féminine", "season":"2026-2027", "status":"historical_roster_pending_2026_27_confirmation",
        "source":"https://www.extranat.fr/waterpolo/cgi-bin/wp_calendar.php?action=structure&structure=2326", "note":"Historical roster; refresh against 2026-27 sheets.", "priority":91,
        "players":[
            (None,"Chloé Vidal",None,"FRA","Goalkeeper / role to verify"),(None,"Anaelle Grass",None,"FRA","Field player"),(None,"Emma Duflos",None,"FRA","Field player"),
            (None,"Illyana Boughanmi",None,"FRA","Field player"),(None,"Chloé Bony",None,"FRA","Field player"),(None,"Aurore Faye",None,"FRA","Field player"),
            (None,"Sarah Amcher",None,"FRA","Field player"),(None,"Valentine Heurtaux",None,"FRA","Field player"),(None,"Maïwenn Le Gall",None,"FRA","Field player"),
            (None,"Lou-Ann Fourmont",None,"FRA","Field player"),(None,"Leopoldine Burle",None,"FRA","Field player"),(None,"Camille Blaize",None,"FRA","Field player"),(None,"Charlotte Giana",None,"FRA","Field player"),
        ]
    },
    {
        "key":"club-fr-choisy-w-elite", "name":"Sporting Club des Nageurs de Choisy le Roi", "team_type":"club", "country":"France",
        "competition":"FF Natation — Elite Féminine", "season":"2026-2027", "status":"historical_roster_pending_2026_27_confirmation",
        "source":"https://www.extranat.fr/waterpolo/", "note":"Historical roster from prior FFN match sheets; refresh before opponent report.", "priority":90,
        "players":[
            (None,"Nathalie Merle",None,"FRA","Field player"),(None,"Ranya Boutarbouche",None,"FRA","Field player"),(None,"Estrella Guingan-Beltran",None,"FRA","Field player"),
            (None,"Ranya El Ayeb",None,"FRA","Field player"),(None,"Annaelle Picard",None,"FRA","Field player"),(None,"Yasmine El Ayeb",None,"FRA","Field player"),
            (None,"Mya Rambecki",None,"FRA","Field player"),(None,"Stephanie Jean",None,"FRA","Field player"),(None,"Sarah Aissou",None,"FRA","Field player"),
            (None,"Elwyn Velon-Mayet",None,"FRA","Field player"),(None,"Lina Oudia",None,"FRA","Field player"),(None,"Clara Da Luz",None,"FRA","Field player"),(None,"Hanane Zeghough",None,"FRA","Field player"),
        ]
    },
    {"key":"club-fr-paris-w-elite","name":"Paris Water-Polo","team_type":"club","country":"France","competition":"FF Natation — Elite Féminine","season":"2026-2027","status":"new_label_roster_refresh_required","source":FFN_GRANVILLE_CAL,"note":"FFN 2026-27 opponent. Do not assume the prior Libellule/RCF roster is identical; new-season roster must be sourced.","priority":89,"players":[]},
    {"key":"club-fr-marseille-w-elite","name":"Cercle des Nageurs de Marseille","team_type":"club","country":"France","competition":"FF Natation — Elite Féminine","season":"2026-2027","status":"roster_refresh_required","source":FFN_GRANVILLE_CAL,"note":"FFN 2026-27 opponent; official roster to ingest from new season sheets.","priority":88,"players":[]},
    {"key":"club-fr-nancy-w-elite","name":"Grand Nancy Aquatique Club","team_type":"club","country":"France","competition":"FF Natation — Elite Féminine","season":"2026-2027","status":"roster_refresh_required","source":FFN_GRANVILLE_CAL,"note":"FFN 2026-27 opponent; official roster to ingest from new season sheets.","priority":87,"players":[]},

    # National-team scouting. Senior rosters are historical benchmark rosters unless a current event roster is added.
    {
        "key":"nat-fr-w-senior", "name":"France — Women Senior", "team_type":"national_team", "country":"France", "competition":"International", "season":"Paris 2024 benchmark", "status":"historical_confirmed_event_roster",
        "source":WA_PARIS_2024_ROSTERS, "note":"Confirmed Paris 2024 Olympic roster; useful historical benchmark, not a claim about the next senior competition roster.", "priority":80,
        "players":[(None,n,None,"FRA","Senior international") for n in ["Lara Andres","Camelia Bouloukbachi","Aurelie Battu","Audrey Daule","Juliette Dhalluin","Louise Guillet","Orsolya Hertzka","Valentine Heurtaux","Pasiphaé Martineaud-Peret","Tiziana Raspo","Camille Radosavljevic","Mia Rycraw","Emma Vernoux"]]
    },
    {
        "key":"nat-es-w-senior", "name":"Spain — Women Senior", "team_type":"national_team", "country":"Spain", "competition":"International", "season":"Paris 2024 benchmark", "status":"historical_confirmed_event_roster",
        "source":WA_PARIS_2024_ROSTERS, "note":"Confirmed Paris 2024 roster; update per current event.", "priority":79,
        "players":[(None,n,None,"ESP","Senior international") for n in ["Paula Camus","Paula Crespi","Anni Espar","Laura Ester","Judith Forca","Maica Garcia","Paula Leiton","Bea Ortiz","Pili Pena","Nona Perez","Isabel Piralkova","Elena Ruiz","Martina Terre"]]
    },
    {
        "key":"nat-usa-w-senior", "name":"United States — Women Senior", "team_type":"national_team", "country":"United States", "competition":"International", "season":"Paris 2024 benchmark", "status":"historical_confirmed_event_roster",
        "source":WA_PARIS_2024_ROSTERS, "note":"Confirmed Paris 2024 roster; update per current event.", "priority":78,
        "players":[(None,n,None,"USA","Senior international") for n in ["Emily Ausmus","Rachel Fattal","Jenna Flynn","Kaleigh Gilchrist","Ashleigh Johnson","Amanda Longan","Maddie Musselman","Ryann Neushul","Tara Prentice","Jordan Raney","Jewel Roemer","Jovanna Sekulic","Maggie Steffens"]]
    },
    {
        "key":"nat-usa-w-u20-2025", "name":"United States — Women U20", "team_type":"national_team", "country":"United States", "competition":"World Aquatics Women's U20 World Championships", "season":"2025", "status":"partial_official_match_report_roster",
        "source":WA_U20_2025, "note":"Partial roster populated from official 2025 tournament reports/library stats; expandable from official match sheets.", "priority":77,
        "players":[(None,"Emily Ausmus",None,"USA","U20 field player"),(None,"Lucy Haaland-Ford",None,"USA","U20 field player"),(None,"Julia Bonaguidi",None,"USA","U20 field player"),(None,"Charlotte Raisin",None,"USA","U20 field player"),(None,"Kamryn Barone",None,"USA","U20 field player"),(None,"Christine Carpenter",None,"USA","U20 goalkeeper")]
    },
    {
        "key":"nat-es-w-u20-2025", "name":"Spain — Women U20", "team_type":"national_team", "country":"Spain", "competition":"World Aquatics Women's U20 World Championships", "season":"2025", "status":"partial_official_match_report_roster",
        "source":WA_U20_2025, "note":"Partial roster from official 2025 match reports; expandable match by match.", "priority":76,
        "players":[(None,"Isabel Piralkova",None,"ESP","U20 field player"),(None,"Irene Casado",None,"ESP","U20 field player"),(None,"Carlota Penalver",None,"ESP","U20 field player")]
    },
    {
        "key":"nat-gr-w-u20-2025", "name":"Greece — Women U20", "team_type":"national_team", "country":"Greece", "competition":"World Aquatics Women's U20 World Championships", "season":"2025", "status":"partial_official_match_report_roster",
        "source":WA_U20_2025, "note":"Partial roster from official 2025 match reports; expandable match by match.", "priority":75,
        "players":[(None,"Nefeli Krassa",None,"GRE","U20 field player"),(None,"Aspasia Fouraki",None,"GRE","U20 field player"),(None,"Foteini Tricha",None,"GRE","U20 field player"),(None,"Ariadni Karampetsou",None,"GRE","U20 field player"),(None,"Dionysia Koureta",None,"GRE","U20 field player"),(None,"Rafaela Saltamanika",None,"GRE","U20 field player"),(None,"Nikoleta Kyriakopoulou",None,"GRE","U20 goalkeeper")]
    },
]


# Expand the national-team index even when the current event roster has not yet been ingested.
# Empty cards are deliberate: the application can queue a roster refresh instead of guessing players.
_major_senior = [
    ("Australia","Australia"),("Canada","Canada"),("China","China"),("Greece","Greece"),("Hungary","Hungary"),
    ("Italy","Italy"),("Netherlands","Netherlands"),("Croatia","Croatia")
]
_existing_keys = {x["key"] for x in SCOUTING_TEAMS}
for _slug,_country in [("aus","Australia"),("can","Canada"),("chn","China"),("gre","Greece"),("hun","Hungary"),("ita","Italy"),("ned","Netherlands"),("cro","Croatia")]:
    _key=f"nat-{_slug}-w-senior"
    if _key not in _existing_keys:
        SCOUTING_TEAMS.append({"key":_key,"name":f"{_country} — Women Senior","team_type":"national_team","country":_country,"competition":"International","season":"Event roster tracking","status":"roster_refresh_required","source":WA_PARIS_2024_ROSTERS,"note":"National-team card ready. Roster must be attached to a specific current competition/event before being treated as current.","priority":60,"players":[]})

_u20_countries = ["Netherlands","New Zealand","Spain","Israel","Hungary","Greece","United States","Italy","Mexico","Brazil","Argentina","Croatia","Canada","South Africa","China","Australia"]
_existing_keys = {x["key"] for x in SCOUTING_TEAMS}
_u20_slug={"Netherlands":"ned","New Zealand":"nzl","Spain":"es","Israel":"isr","Hungary":"hun","Greece":"gr","United States":"usa","Italy":"ita","Mexico":"mex","Brazil":"bra","Argentina":"arg","Croatia":"cro","Canada":"can","South Africa":"rsa","China":"chn","Australia":"aus"}
for _country in _u20_countries:
    _key=f"nat-{_u20_slug[_country]}-w-u20-2025"
    if _key not in _existing_keys:
        SCOUTING_TEAMS.append({"key":_key,"name":f"{_country} — Women U20","team_type":"national_team","country":_country,"competition":"World Aquatics Women's U20 World Championships","season":"2025","status":"roster_refresh_required","source":WA_U20_2025,"note":"Team confirmed in the 2025 U20 field. Player roster ingestion is queued from official match sheets/reports.","priority":55,"players":[]})


def seed_scouting(db):
    for item in SCOUTING_TEAMS:
        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == item["key"]))
        if not team:
            team = ScoutingTeam(
                external_key=item["key"], name=item["name"], team_type=item["team_type"], category="Women",
                age_group="U20" if "U20" in item["name"] else "Senior", country=item["country"], competition=item["competition"],
                season_label=item["season"], roster_status=item["status"], source_url=item["source"], source_note=item["note"], priority=item["priority"]
            )
            db.add(team); db.flush()
        if not db.scalar(select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id == team.id)):
            for cap, name, birth_year, nationality, role in item.get("players", []):
                db.add(ScoutingPlayer(
                    scouting_team_id=team.id, name=name, cap_number=cap, birth_year=birth_year, nationality=nationality, role=role,
                    source_season=item["season"], source_url=item["source"], source_quality="official_match_sheet" if item["team_type"] == "club" else "official_event_roster",
                    current_status="historical_pending_refresh" if "historical" in item["status"] else "partial_current_event", note=item["note"]
                ))
    db.commit()
