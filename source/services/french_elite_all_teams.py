import json
from sqlalchemy import select

from models import MatchLibraryItem, LibraryPlayerMatchStat

OPENING = "https://www.ffnatation.fr/actualites/actualite-grand-public/lelite-feminine-demarre-tres-fort"
DAY2 = "https://www.ffnatation.fr/actualites/actu-grand-public/une-deuxieme-journee-animee-en-elite-feminine"
DAY3 = "https://www.ffnatation.fr/actualites/actualite-grand-public/lille-et-bordeaux-toujours-invaincus-le-derby-pour-taverny"
LILLE_BDX = "https://www.ffnatation.fr/actualites/actu-grand-public/lille-assure-nancy-au-bout-du-suspense"
MIDSEASON = "https://www.ffnatation.fr/actualites/actu-grand-public/lille-simpose-bordeaux-et-nice-font-le-job"
MARCH8 = "https://www.ffnatation.fr/actualites/actu-grand-public/lille-confirme-bordeaux-et-toulon-assurent"
MARCH22 = "https://www.ffnatation.fr/actualites/actualite-grand-public/nancy-revient-sur-le-podium-taveny-et-lille-en-patron"
MARCH29 = "https://www.ffnatation.fr/actualites/actualite-grand-public/lille-intouchable-nancy-frappe-fort"
REGULAR_FINAL = "https://www.ffnatation.fr/actualites/actu-grand-public/nice-soffre-la-deuxieme-place-sur-le-fil"
FINAL = "https://www.ffnatation.fr/actualites/actu-grand-public/lille-champion-de-france-2026"

LILLE = "Lille UC Métropole Water-Polo"
BORDEAUX = "Union St-Bruno Bordeaux"
NICE = "Olympic Nice Natation"
NANCY = "Grand Nancy Aquatique Club"
TOULON = "Toulon Waterpolo"
TAVERNY = "Taverny Sports Nautiques 95"
CHOISY = "Sporting Club des Nageurs de Choisy le Roi"

# Names are normalized only when the FFN article clearly uses a surname/abbreviation
# that maps to an already identified player. Ambiguous one-word names stay as-is.
N = {
    "Ben Mouna": "Sherihene Ben Mouna", "Birch": "Elizabeth Grace Estelle Birch",
    "Jean Michel": "Lou Jean Michel", "Jean-Michel": "Lou Jean Michel", "Jean Lichel": "Lou Jean Michel",
    "Horcholle": "Marion Horcholle", "Chadly": "Kenza Chadly", "Faure": "Chloé Faure",
    "Currie": "Robyn Jennifer Currie", "Ribes": "Juliette Ribes", "J. Ribes": "Juliette Ribes",
    "Doucereux": "Anne-Fleur Doucereux", "Turbeau": "Justine Turbeau",
    "Christl": "Caroline Christl", "Accordino": "Lise Accordino", "Barbieux": "Marie Barbieux",
    "Naneva": "Michaela Naneva", "Delorme": "Élodie Delorme", "Larson": "Mackenzie Larson",
    "Manuel": "Eva Manuel", "Nutella’s": "Cutellas",
    "Valverde": "Clémentine Valverde", "Burle": "Leopoldine Burle", "Heurtaux": "Valentine Heurtaux",
    "Faye": "Aurore Faye", "Boucif": "Magdouline Boucif", "Bony": "Chloé Bony", "bon": "Chloé Bony",
    "Giana": "Charlotte Giana", "Boughanmi": "Illyana Boughanmi", "Amcher": "Sarah Amcher",
    "Fourmont": "Lou-Ann Fourmont", "Blaize": "Camille Blaize",
    "Boughrara": "Jade Boughrara", "F. Bentaleb": "Feryel Bentaleb", "Bentaleb F.": "Feryel Bentaleb",
    "S. Bentaleb": "Sohane Bentaleb", "Bentaleb S.": "Sohane Bentaleb",
    "Mayet Toussaint": "Aurore Mayet Toussaint", "Zelenko": "Anastasiia Zelenko",
    "Moizant": "Justine Moizant", "Rigault": "Eléonore Rigault", "Lanoëlle": "Marine Lanoëlle",
    "Soler": "Olivia Soler", "Wasterlain": "Zia Wasterlain",
    "Picard": "Annaelle Picard", "El Ayeb": "Ranya El Ayeb", "El Ayeb R.": "Ranya El Ayeb",
    "Da Luz": "Clara Da Luz", "Aissou": "Sarah Aissou", "Rambecki": "Mya Rambecki",
    "Bouloukbachi": "Camelia Bouloukbachi", "Guingan-Beltran": "Estrella Guingan-Beltran",
    "Velon-Mayet": "Elwyn Velon-Mayet", "Boutarbouche": "Ranya Boutarbouche", "Odia": "Lina Oudia",
    "Benlekbir": "Kahena Benlekbir", "De Miranda": "Karen De Miranda Da Silva",
    "De Miranda da Silva": "Karen De Miranda Da Silva", "De Miranda Da Silva": "Karen De Miranda Da Silva",
    "Pacheco Herce": "Sandra Pacheco Herce", "Raspo": "Tiziana Raspo",
    "Süzmeçelik": "Hamiyet Süzmeçelik", "Suzmecelik": "Hamiyet Süzmeçelik",
    "Gurcan": "Emma Gurcan", "Fanara": "Lucie Fanara",
    "Pal": "Anna Pal", "Kilic-Pegourie": "Elhyne Kilic-Pegourie", "Kilic-Pégourie": "Elhyne Kilic-Pegourie",
    "Andres": "Lara Andres", "Andrs": "Lara Andres", "Sponza": "Giulia Sponza",
    "Di Fraja": "Lana Di Fraja", "Nardini": "Cecilia Nardini", "Vernoux": "Lily Vernoux",
    "Baringo Romero": "Carmen Baringo Romero", "Lizotte": "Myriam Lizotte",
    "Ribeiro De Souza": "Maéline Ribeiro de Souza", "Ribieiro De Souza": "Maéline Ribeiro de Souza",
}


def _p(name):
    return N.get(name, name)


def _s(**kwargs):
    return {_p(k): v for k, v in kwargs.items()}


def scorers(items):
    return {_p(name): goals for name, goals in items}


MATCHES = [
    dict(key="FFN-ELITEF-2526-TOULON-BORDEAUX-14-15", source=OPENING, a=TOULON, b=BORDEAUX, sa=14, sb=15, q=[[6,2],[2,4],[2,4],[3,3],[1,2]],
         pa=scorers([("Valverde",6),("Burle",5),("Heurtaux",2),("Faye",1)]),
         pb=scorers([("Ben Mouna",4),("Birch",3),("Danet",2),("Jean Michel",2),("Horcholle",2),("Chadly",2),("Faure",1)]), complete={TOULON:True,BORDEAUX:False}),
    dict(key="FFN-ELITEF-2526-NANCY-TAVERNY-17-13", source=OPENING, a=NANCY, b=TAVERNY, sa=17, sb=13, q=[[4,3],[5,3],[2,1],[6,6]],
         pa=scorers([("Benlekbir",6),("De Miranda",3),("Pacheco Herce",3),("Raspo",3),("Süzmeçelik",1),("Hariss",1)]),
         pb=scorers([("Boughrara",5),("F. Bentaleb",3),("Zelenko",2),("Moizant",1),("Mayet Toussaint",1),("Ajem",1)]), complete={NANCY:True,TAVERNY:True}),
    dict(key="FFN-ELITEF-2526-CHOISY-NICE-7-19", source=OPENING, a=CHOISY, b=NICE, sa=7, sb=19, q=[[1,5],[1,4],[2,6],[3,4]],
         pa=scorers([("Picard",2),("El Ayeb",2),("Da Luz",1),("Aissou",1),("Rambecki",1)]),
         pb=scorers([("Accordino",6),("Christl",5),("Barbieux",3),("Delorme",2),("Naneva",1),("Larson",1),("Cutellas",1)]), complete={CHOISY:True,NICE:True}),
    dict(key="FFN-ELITEF-2526-NICE-LILLE-15-14", source=DAY2, a=NICE, b=LILLE, sa=14, sb=15, q=[[1,3],[6,3],[3,6],[4,3]],
         pa=scorers([("Christl",7),("Barbieux",4),("Accordino",2),("Naneva",1)]),
         pb=scorers([("Andres",4),("Vernoux",3),("Pal",2),("Nardini",2),("Lizotte",2),("Kilic-Pegourie",2)]), complete={NICE:True,LILLE:True}),
    dict(key="FFN-ELITEF-2526-TOULON-CHOISY-19-2", source=DAY2, a=TOULON, b=CHOISY, sa=19, sb=2, q=[[4,1],[5,1],[3,0],[7,0]],
         pa=scorers([("Heurtaux",4),("Burle",4),("Faye",3),("Boucif",2),("Bony",2),("Valverde",1),("Touret",1),("Giana",1),("Boughanmi",1)]),
         pb=scorers([("Picard",2)]), complete={TOULON:True,CHOISY:True}),
    dict(key="FFN-ELITEF-2526-BORDEAUX-TAVERNY-26-12", source=DAY2, a=BORDEAUX, b=TAVERNY, sa=26, sb=12, q=[[7,3],[5,0],[7,6],[7,3]],
         pa=scorers([("Birch",8),("Jean Michel",4),("J. Ribes",3),("Ben Mouna",2),("Horcholle",3),("Doucereux",2),("Faure",2),("Chadly",2)]),
         pb=scorers([("Mayet Toussaint",4),("F. Bentaleb",3),("Boughrara",3),("Ajem",1),("Rigault",1)]), complete={BORDEAUX:True,TAVERNY:True}),
    dict(key="FFN-ELITEF-2526-BORDEAUX-NANCY-14-12", source=DAY3, a=BORDEAUX, b=NANCY, sa=14, sb=12, q=[[3,4],[4,1],[3,3],[1,3],[3,1]],
         pa=scorers([("Ben Mouna",3),("Jean Michel",3),("Doucereux",2),("Danet",1),("Currie",1),("Ribes",1),("Faure",1),("Chadly",1),("Birch",1)]),
         pb=scorers([("Benlekbir",5),("Raspo",2),("De Miranda Da Silva",2),("Pacheco Herce",2),("Stauder",1)]), complete={BORDEAUX:True,NANCY:True}),
    dict(key="FFN-ELITEF-2526-LILLE-TOULON-17-8", source=DAY3, a=LILLE, b=TOULON, sa=17, sb=8, q=[[5,0],[5,2],[3,2],[4,4]],
         pa=scorers([("Andres",5),("Vernoux",3),("Di Fraja",4),("Nardini",2),("Pal",1),("Sponza",1),("Kilic-Pegourie",1)]),
         pb=scorers([("Heurtaux",3),("Burle",2),("Valverde",1),("Faye",1),("Fourmont",1)]), complete={LILLE:True,TOULON:True}),
    dict(key="FFN-ELITEF-2526-TAVERNY-CHOISY-24-8", source=DAY3, a=TAVERNY, b=CHOISY, sa=24, sb=8, q=[[8,2],[4,1],[6,1],[6,4]],
         pa=scorers([("Boughrara",6),("Ajem",1),("Mayet Toussaint",4),("Moizant",2),("Lanoëlle",1),("S. Bentaleb",7),("F. Bentaleb",3)]),
         pb=scorers([("Bouloukbachi",2),("Guingan-Beltran",2),("Picard",2),("Aissou",1),("Da Luz",1)]), complete={TAVERNY:True,CHOISY:True}),
    dict(key="FFN-ELITEF-2526-LILLE-BORDEAUX-19-14", source=LILLE_BDX, a=LILLE, b=BORDEAUX, sa=19, sb=14, q=[[7,3],[2,4],[7,4],[3,3]],
         pa=scorers([("Pal",1),("Kilic-Pegourie",6),("Andres",1),("Di Fraja",4),("Nardini",5),("Lizotte",2)]),
         pb=scorers([("Currie",2),("Faure",1),("Jean Michel",2),("Horcholle",4),("Danet",3),("Ben Mouna",1),("Birch",1)]), complete={LILLE:True,BORDEAUX:True}),
    dict(key="FFN-ELITEF-2526-NICE-NANCY-13-14", source=LILLE_BDX, a=NICE, b=NANCY, sa=13, sb=14, q=[[2,2],[3,2],[1,3],[4,3],[3,4]],
         pa=scorers([("Christl",3),("Naneva",2),("Delorme",1),("Barbieux",2),("Larson",3),("Accordino",2)]),
         pb=scorers([("Lima De Freitas",1),("Gurcan",1),("Süzmeçelik",1),("Raspo",1),("Benlekbir",5),("Todoroff",1),("De Miranda Da Silva",1),("Fanara",1),("Pacheco Herce",2)]), complete={NICE:True,NANCY:True}),
    dict(key="FFN-ELITEF-2526-NANCY-LILLE-15-20", source=MIDSEASON, a=NANCY, b=LILLE, sa=15, sb=20, q=[[4,4],[3,4],[3,6],[5,6]],
         pa=scorers([("Gurcan",1),("Süzmeçelik",1),("Raspo",1),("Benlekbir",5),("De Miranda da Silva",4),("Fanara",2),("Pacheco Herce",1)]),
         pb=scorers([("Pal",5),("Kilic-Pegourie",1),("Andres",3),("Sponza",1),("Di Fraja",4),("Nardini",3),("Lizotte",2),("Ribeiro De Souza",1)]), complete={NANCY:True,LILLE:True}),
    dict(key="FFN-ELITEF-2526-BORDEAUX-CHOISY-30-9", source=MIDSEASON, a=BORDEAUX, b=CHOISY, sa=30, sb=9, q=[[8,2],[8,2],[6,3],[8,2]],
         pa=scorers([("Turbeau",1),("Currie",1),("Ribes",2),("Faure",3),("Jean Michel",5),("Chadly",2),("Doucereux",1),("Horcholle",5),("Gharbi",1),("Ben Mouna",3),("Birch",6)]),
         pb=scorers([("El Ayeb R.",5),("Rambecki",2),("Odia",1),("Da Luz",1)]), complete={BORDEAUX:True,CHOISY:True}),
    dict(key="FFN-ELITEF-2526-NICE-TAVERNY-19-4", source=MIDSEASON, a=NICE, b=TAVERNY, sa=19, sb=4, q=[[6,0],[4,2],[4,1],[5,1]],
         pa=scorers([("Cugnart",2),("Christl",3),("Naneva",1),("Delorme",2),("Barbieux",5),("Larson",2),("Nutella’s",3),("Accordino",1)]),
         pb=scorers([("Boughrara",1),("Mayet Toussaint",1),("Moizant",1),("Zelenko",1)]), complete={NICE:True,TAVERNY:True}),
    dict(key="FFN-ELITEF-2526-TAVERNY-BORDEAUX-7-18", source=MARCH8, a=TAVERNY, b=BORDEAUX, sa=7, sb=18, q=[[1,3],[0,5],[3,7],[3,3]],
         pa=scorers([("Rigault",1),("Mayet Toussaint",1),("S. Bentaleb",3),("F. Bentaleb",2)]),
         pb=scorers([("Currie",2),("Faure",1),("Jean Michel",4),("Doucereux",2),("Ben Mouna",2),("Birch",7)]), complete={TAVERNY:True,BORDEAUX:True}),
    dict(key="FFN-ELITEF-2526-CHOISY-TOULON-5-24", source=MARCH8, a=CHOISY, b=TOULON, sa=5, sb=24, q=[[2,6],[2,9],[0,5],[1,4]],
         pa=scorers([("Bouloukbachi",1),("Picard",2),("Rambecki",1),("Velon-Mayet",1)]),
         pb=scorers([("Giana",1),("Boughanmi",1),("bon",5),("Faye",1),("Amcher",2),("Heurtaux",6),("Boucif",1),("Fourmont",1),("Burle",5),("Blaize",1)]), complete={CHOISY:True,TOULON:True}),
    dict(key="FFN-ELITEF-2526-LILLE-NICE-20-11", source=MARCH8, a=LILLE, b=NICE, sa=20, sb=11, q=[[5,3],[5,3],[3,3],[7,2]],
         pa=scorers([("Pal",1),("Kilic-Pegourie",1),("Di Fraja",2),("Nardini",6),("Vernoux",5),("Lizotte",1)]),
         pb=scorers([("Naneva",3),("Delorme",2),("Barbieux",1),("Larson",2),("Accordino",3)]), complete={LILLE:False,NICE:True}),
    dict(key="FFN-ELITEF-2526-CHOISY-TAVERNY-5-18", source=MARCH22, a=CHOISY, b=TAVERNY, sa=5, sb=18, q=[[2,4],[0,2],[2,5],[1,7]],
         pa=scorers([("Bouloukbachi",2),("Aissou",1),("Da Luz",1),("Boutarbouche",1)]),
         pb=scorers([("Boughrara",3),("Mayet Toussaint",6),("Soler",3),("S. Bentaleb",3),("F. Bentaleb",2),("Wasterlain",1)]), complete={CHOISY:True,TAVERNY:True}),
    dict(key="FFN-ELITEF-2526-NANCY-BORDEAUX-17-11", source=MARCH22, a=NANCY, b=BORDEAUX, sa=17, sb=11, q=[[4,4],[5,0],[2,5],[6,2]],
         pa=scorers([("Süzmeçelik",2),("Raspo",2),("Benlekbir",5),("De Miranda Da Silva",4),("Fanara",1),("Pacheco Herce",3)]),
         pb=scorers([("Turbeau",1),("Currie",4),("Doucereux",1),("Ben Mouna",2),("Birch",3)]), complete={NANCY:True,BORDEAUX:True}),
    dict(key="FFN-ELITEF-2526-TOULON-LILLE-9-19", source=MARCH22, a=TOULON, b=LILLE, sa=9, sb=19, q=[[1,4],[4,4],[2,8],[2,3]],
         pa=scorers([("Faye",1),("Heurtaux",4),("Boucif",2),("Burle",1),("Blaize",1)]),
         pb=scorers([("Pal",1),("Kilic-Pegourie",2),("Andres",1),("Sponza",2),("Di Fraja",2),("Nardini",1),("Vernoux",4),("Baringo Romero",3),("Lizotte",3)]), complete={TOULON:True,LILLE:True}),
    dict(key="FFN-ELITEF-2526-LILLE-TAVERNY-25-9", source=MARCH29, a=LILLE, b=TAVERNY, sa=25, sb=9, q=[[6,2],[5,1],[8,3],[6,3]],
         pa=scorers([("Kilic-Pegourie",3),("Andres",1),("Sponza",1),("Di Fraja",3),("Nardini",1),("Vernoux",7),("Baringo Romero",5),("Lizotte",2),("Ribeiro De Souza",2)]),
         pb=scorers([("Boughrara",5),("S. Bentaleb",2),("F. Bentaleb",2)]), complete={LILLE:True,TAVERNY:True}),
    dict(key="FFN-ELITEF-2526-NANCY-NICE-18-13", source=MARCH29, a=NANCY, b=NICE, sa=18, sb=13, q=[[4,3],[5,3],[4,2],[5,5]],
         pa=scorers([("Gurcan",2),("Süzmeçelik",2),("Raspo",2),("Benlekbir",4),("Todoroff",2),("De Miranda Da Silva",3),("Pacheco Herce",3)]),
         pb=scorers([("Christl",3),("Naneva",3),("Delorme",2),("Barbieux",1),("Accordino",3),("Manuel",1)]), complete={NANCY:True,NICE:True}),
    dict(key="FFN-ELITEF-2526-NICE-BORDEAUX-8-7", source=REGULAR_FINAL, a=NICE, b=BORDEAUX, sa=8, sb=7, q=[[0,0],[3,3],[3,2],[2,2]],
         pa=scorers([("Delorme",3),("Barbieux",1),("Accordino",3),("Manuel",1)]),
         pb=scorers([("Currie",1),("Ribes",2),("Birch",4)]), complete={NICE:True,BORDEAUX:True}),
    dict(key="FFN-ELITEF-2526-LILLE-CHOISY-33-4", source=REGULAR_FINAL, a=LILLE, b=CHOISY, sa=33, sb=4, q=[[9,1],[6,1],[9,1],[9,1]],
         pa=scorers([("Kilic-Pegourie",4),("Andrs",2),("Sponza",2),("Di Fraja",5),("Nardini",5),("Vernoux",9),("Baringo Romero",2),("Lizotte",2),("Ribieiro De Souza",2)]),
         pb=scorers([("Guingan-Beltran",2),("Picard",1),("Velon-Mayet",1)]), complete={LILLE:True,CHOISY:True}),
    dict(key="FFN-ELITEF-2526-BRONZE-BORDEAUX-NICE-10-8", source=FINAL, a=BORDEAUX, b=NICE, sa=10, sb=8, q=[[2,1],[5,3],[0,3],[3,1]],
         pa=scorers([("Currie",3),("Faure",1),("Jean Michel",1),("Horcholle",3),("Ben Mouna",2)]),
         pb=scorers([("Naneva",2),("Delorme",1),("Barbieux",2),("Larson",2),("Accordino",1)]), complete={BORDEAUX:True,NICE:True}),
    dict(key="FFN-ELITEF-2526-FINAL-LILLE-NANCY-17-10", source=FINAL, a=LILLE, b=NANCY, sa=17, sb=10, q=[[5,5],[6,2],[2,3],[4,0]],
         pa=scorers([("Kilic-Pegourie",1),("Sponza",2),("Di Fraja",3),("Nardini",7),("Vernoux",2),("Baringo Romero",2)]),
         pb=scorers([("Süzmeçelik",2),("Todoroff",1),("De Miranda Da Silva",3),("Pacheco Herce",4)]), complete={LILLE:True,NANCY:True}),
]


def seed_french_elite_all_teams(db):
    for item in MATCHES:
        row = db.scalar(select(MatchLibraryItem).where(MatchLibraryItem.external_key == item["key"]))
        meta = {
            "_aquametric": {
                "competition_level": 3,
                "source_tier": "federation_official",
                "evidence_scope": "official_goal_list",
                "scorer_list_complete_by_team": item["complete"],
            }
        }
        if not row:
            row = MatchLibraryItem(
                external_key=item["key"], title=f'{item["a"]} vs {item["b"]} — Elite Féminine',
                competition="Elite Féminine", season="2025-2026", entity_type="club",
                team_a=item["a"], team_b=item["b"], score_a=item["sa"], score_b=item["sb"],
                quarter_scores_json=json.dumps(item["q"]), video_url="", video_kind="official_report",
                official_source_url=item["source"], analysis_status="official_public_stats",
                tactical_summary="Official FFN match report with attributed scorer evidence. Missing individual actions remain unknown.",
                team_stats_json=json.dumps(meta, ensure_ascii=False),
            )
            db.add(row)
            db.flush()
        else:
            row.team_a, row.team_b, row.score_a, row.score_b = item["a"], item["b"], item["sa"], item["sb"]
            row.quarter_scores_json = json.dumps(item["q"])
            row.official_source_url = item["source"]
            row.analysis_status = "official_public_stats"
            row.team_stats_json = json.dumps(meta, ensure_ascii=False)
        for team, stats in ((item["a"], item["pa"]), (item["b"], item["pb"])):
            is_complete = item["complete"].get(team, False)
            for player_name, goals in stats.items():
                stat = db.scalar(select(LibraryPlayerMatchStat).where(
                    LibraryPlayerMatchStat.library_match_id == row.id,
                    LibraryPlayerMatchStat.player_name == player_name,
                ))
                note = "Official FFN scorer attribution. " + (
                    "Published scorer total reconciles with the team score."
                    if is_complete else
                    "Published scorer total does not reconcile with the displayed team score; attributed goals remain evidence, confidence is reduced."
                )
                if not stat:
                    db.add(LibraryPlayerMatchStat(
                        library_match_id=row.id, team_name=team, player_name=player_name,
                        goals=goals, source_quality="federation_official", note=note,
                    ))
                else:
                    stat.team_name = team
                    stat.goals = goals
                    stat.source_quality = "federation_official"
                    stat.note = note
    db.commit()
