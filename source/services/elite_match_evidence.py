import json
from sqlalchemy import select

from models import MatchLibraryItem, LibraryPlayerMatchStat

# Official FFN / federation-reported match evidence. These records contain only
# statistics explicitly published in the cited source. Missing metrics stay None.
LILLE_MATCHES_2025_26 = [
    {
        "key": "FFN-ELITEF-2526-NICE-LILLE-15-14",
        "title": "Olympic Nice Natation vs Lille UC Métropole Water-Polo — Elite Féminine",
        "competition": "Elite Féminine",
        "season": "2025-2026",
        "team_a": "Olympic Nice Natation", "team_b": "Lille UC Métropole Water-Polo", "score_a": 14, "score_b": 15,
        "quarters": [[1,3],[6,3],[3,6],[4,3]],
        "source": "https://www.ffnatation.fr/actualites/actu-grand-public/une-deuxieme-journee-animee-en-elite-feminine",
        "summary": "Lille wins a one-goal match in Nice. The FFN report publishes the complete Lille scorer list and describes a high-intensity tactical contest.",
        "complete": True, "level": 3,
        "players": {"Lara Andres":4,"Lily Vernoux":3,"Anna Pal":2,"Cecilia Nardini":2,"Myriam Lizotte":2,"Elhyne Kilic-Pegourie":2},
    },
    {
        "key": "FFN-ELITEF-2526-LILLE-TOULON-17-8",
        "title": "Lille UC Métropole Water-Polo vs Toulon Waterpolo — Elite Féminine",
        "competition": "Elite Féminine", "season": "2025-2026",
        "team_a": "Lille UC Métropole Water-Polo", "team_b": "Toulon Waterpolo", "score_a": 17, "score_b": 8,
        "quarters": [[5,0],[5,2],[3,2],[4,4]],
        "source": "https://www.ffnatation.fr/actualites/actu-grand-public/lille-et-bordeaux-toujours-invaincus-le-derby-pour-taverny",
        "summary": "FFN reports a controlled Lille victory built on a strong defensive base, pressing and transition play; the scorer list is complete.",
        "complete": True, "level": 3,
        "players": {"Lara Andres":5,"Lily Vernoux":3,"Lana Di Fraja":4,"Cecilia Nardini":2,"Anna Pal":1,"Giulia Sponza":1,"Elhyne Kilic-Pegourie":1},
    },
    {
        "key": "FFN-ELITEF-2526-TAVERNY-LILLE-6-25",
        "title": "Taverny SN95 vs Lille UC Métropole Water-Polo — Elite Féminine",
        "competition": "Elite Féminine", "season": "2025-2026",
        "team_a": "Taverny Sports Nautiques 95", "team_b": "Lille UC Métropole Water-Polo", "score_a": 6, "score_b": 25,
        "quarters": [[2,4],[0,8],[1,5],[3,8]],
        "source": "https://www.ffnatation.fr/actualites/actu-grand-public/nancy-et-lille-imposent-leur-loi-nice-lemporte-face-toulon",
        "summary": "Lille dominates at Taverny. FFN highlights scoring in transition and set offence and publishes the complete Lille scorer list.",
        "complete": True, "level": 3,
        "players": {"Anna Pal":2,"Elhyne Kilic-Pegourie":4,"Lara Andres":4,"Clémence Goulu":1,"Lana Di Fraja":5,"Cecilia Nardini":6,"Myriam Lizotte":3},
    },
    {
        "key": "FFN-ELITEF-2526-LILLE-BORDEAUX-19-14",
        "title": "Lille UC Métropole Water-Polo vs USB Bordeaux — Elite Féminine",
        "competition": "Elite Féminine", "season": "2025-2026",
        "team_a": "Lille UC Métropole Water-Polo", "team_b": "Union St-Bruno Bordeaux", "score_a": 19, "score_b": 14,
        "quarters": [[7,3],[2,4],[7,4],[3,3]],
        "source": "https://www.ffnatation.fr/actualites/actu-grand-public/lille-assure-nancy-au-bout-du-suspense",
        "summary": "Lille beats Bordeaux in an open Elite match. FFN cites pressing, attacking variety and the accuracy of Nardini and Di Fraja; scorer list complete.",
        "complete": True, "level": 3,
        "players": {"Anna Pal":1,"Elhyne Kilic-Pegourie":6,"Lara Andres":1,"Lana Di Fraja":4,"Cecilia Nardini":5,"Myriam Lizotte":2},
    },
    {
        "key": "FFN-ELITEF-2526-NANCY-LILLE-15-20",
        "title": "Grand Nancy AC vs Lille UC Métropole Water-Polo — Elite Féminine",
        "competition": "Elite Féminine", "season": "2025-2026",
        "team_a": "Grand Nancy Aquatique Club", "team_b": "Lille UC Métropole Water-Polo", "score_a": 15, "score_b": 20,
        "quarters": [[4,4],[3,4],[3,6],[5,6]],
        "source": "https://www.ffnatation.fr/actualites/actu-grand-public/lille-simpose-bordeaux-et-nice-font-le-job",
        "summary": "Lille wins a high-scoring game in Nancy. FFN describes strong power-play conversion, structured attack and a complete scorer list.",
        "complete": True, "level": 3,
        "players": {"Anna Pal":5,"Elhyne Kilic-Pegourie":1,"Lara Andres":3,"Giulia Sponza":1,"Lana Di Fraja":4,"Cecilia Nardini":3,"Myriam Lizotte":2,"Maéline Ribeiro de Souza":1},
    },
    {
        "key": "FFN-ELITEF-2526-LILLE-TAVERNY-25-9",
        "title": "Lille UC Métropole Water-Polo vs Taverny SN95 — Elite Féminine",
        "competition": "Elite Féminine", "season": "2025-2026",
        "team_a": "Lille UC Métropole Water-Polo", "team_b": "Taverny Sports Nautiques 95", "score_a": 25, "score_b": 9,
        "quarters": [[6,2],[5,1],[8,3],[6,3]],
        "source": "https://www.ffnatation.fr/actualites/actualite-grand-public/lille-intouchable-nancy-frappe-fort",
        "summary": "Lille wins 25-9. FFN publishes the complete scorer list.",
        "complete": True, "level": 3,
        "players": {"Elhyne Kilic-Pegourie":3,"Lara Andres":1,"Giulia Sponza":1,"Lana Di Fraja":3,"Cecilia Nardini":1,"Lily Vernoux":7,"Carmen Baringo Romero":5,"Myriam Lizotte":2,"Maéline Ribeiro de Souza":2},
    },
    {
        "key": "FFN-ELITEF-2526-LILLE-NICE-20-11",
        "title": "Lille UC Métropole Water-Polo vs Olympic Nice Natation — Elite Féminine",
        "competition": "Elite Féminine", "season": "2025-2026",
        "team_a": "Lille UC Métropole Water-Polo", "team_b": "Olympic Nice Natation", "score_a": 20, "score_b": 11,
        "quarters": [[5,3],[5,3],[3,3],[7,2]],
        "source": "https://www.ffnatation.fr/actualites/actu-grand-public/lille-confirme-bordeaux-et-toulon-assurent",
        "summary": "Lille beats Nice 20-11. The FFN article publishes several individual scorers but the listed totals do not sum to Lille's final score, so scorer coverage is explicitly marked incomplete.",
        "complete": False, "level": 3,
        "players": {"Anna Pal":1,"Elhyne Kilic-Pegourie":1,"Lana Di Fraja":2,"Cecilia Nardini":6,"Lily Vernoux":5,"Myriam Lizotte":1},
    },
    {
        "key": "FFN-ELITEF-2526-TOULON-LILLE-9-19",
        "title": "Toulon Waterpolo vs Lille UC Métropole Water-Polo — Elite Féminine",
        "competition": "Elite Féminine", "season": "2025-2026",
        "team_a": "Toulon Waterpolo", "team_b": "Lille UC Métropole Water-Polo", "score_a": 9, "score_b": 19,
        "quarters": [[1,4],[4,4],[2,8],[2,3]],
        "source": "https://www.ffnatation.fr/actualites/actualite-grand-public/nancy-revient-sur-le-podium-taveny-et-lille-en-patron",
        "summary": "Lille wins 19-9 in Toulon; FFN publishes the complete Lille scorer list and describes a controlled collective performance.",
        "complete": True, "level": 3,
        "players": {"Anna Pal":1,"Elhyne Kilic-Pegourie":2,"Lara Andres":1,"Giulia Sponza":2,"Lana Di Fraja":2,"Cecilia Nardini":1,"Lily Vernoux":4,"Carmen Baringo Romero":3,"Myriam Lizotte":3},
    },
    {
        "key": "FFN-ELITEF-2526-LILLE-CHOISY-33-4",
        "title": "Lille UC Métropole Water-Polo vs SCN Choisy-le-Roi — Elite Féminine",
        "competition": "Elite Féminine", "season": "2025-2026",
        "team_a": "Lille UC Métropole Water-Polo", "team_b": "SCN Choisy-le-Roi", "score_a": 33, "score_b": 4,
        "quarters": [[9,1],[6,1],[9,1],[9,1]],
        "source": "https://www.ffnatation.fr/actualites/actu-grand-public/nice-soffre-la-deuxieme-place-sur-le-fil",
        "summary": "Lille completes an unbeaten regular season with a 33-4 win; FFN publishes the complete scorer list and describes intense pressing and transition pressure.",
        "complete": True, "level": 3,
        "players": {"Elhyne Kilic-Pegourie":4,"Lara Andres":2,"Giulia Sponza":2,"Lana Di Fraja":5,"Cecilia Nardini":5,"Lily Vernoux":9,"Carmen Baringo Romero":2,"Myriam Lizotte":2,"Maéline Ribeiro de Souza":2},
    },
    {
        "key": "FFN-ELITEF-2526-FINAL-LILLE-NANCY-17-10",
        "title": "Lille UC Métropole Water-Polo vs Grand Nancy AC — 2026 Elite final",
        "competition": "Elite Féminine — Final", "season": "2025-2026",
        "team_a": "Lille UC Métropole Water-Polo", "team_b": "Grand Nancy Aquatique Club", "score_a": 17, "score_b": 10,
        "quarters": [[5,5],[6,2],[2,3],[4,0]],
        "source": "https://www.ffnatation.fr/actualites/actu-grand-public/lille-champion-de-france-2026",
        "summary": "Lille wins the 2026 French Elite title. FFN publishes the complete scorer list and highlights Cecilia Nardini's seven-goal final.",
        "complete": True, "level": 4,
        "players": {"Elhyne Kilic-Pegourie":1,"Giulia Sponza":2,"Lana Di Fraja":3,"Cecilia Nardini":7,"Lily Vernoux":2,"Carmen Baringo Romero":2},
    },
    {
        "key": "FFN-CLW-2526-ALIMOS-LILLE-21-11",
        "title": "Alimos NAC Betsson vs Lille UC — Champions League Women",
        "competition": "Champions League Women", "season": "2025-2026",
        "team_a": "Alimos NAC Betsson", "team_b": "Lille UC Métropole Water-Polo", "score_a": 21, "score_b": 11,
        "quarters": [[6,4],[6,3],[3,2],[6,2]],
        "source": "https://www.ffnatation.fr/actualites/actualite-grand-public/ligue-des-champions-feminine-nancy-et-lille-quittent-la",
        "summary": "European Champions League match reported by FFN. Lille loses 21-11; the published Lille scorer list is complete.",
        "complete": True, "level": 5,
        "players": {"Cecilia Nardini":4,"Lara Andres":2,"Lily Vernoux":2,"Myriam Lizotte":1,"Anna Pal":1,"Elhyne Kilic-Pegourie":1},
    },
    {
        "key": "FFN-CLW-2526-SPANDAU-LILLE-18-12",
        "title": "Spandau 04 Berlin vs Lille UC — Champions League Women",
        "competition": "Champions League Women", "season": "2025-2026",
        "team_a": "Spandau 04 Berlin", "team_b": "Lille UC Métropole Water-Polo", "score_a": 18, "score_b": 12,
        "quarters": [[2,2],[8,2],[3,5],[5,3]],
        "source": "https://www.ffnatation.fr/actualites/actualite-grand-public/ligue-des-champions-feminine-nancy-et-lille-quittent-la",
        "summary": "European Champions League match reported by FFN. Lille wins the third quarter 5-3 but loses 18-12; complete Lille scorer list published.",
        "complete": True, "level": 5,
        "players": {"Myriam Lizotte":3,"Lara Andres":2,"Lily Vernoux":2,"Cecilia Nardini":2,"Anna Pal":1,"Elhyne Kilic-Pegourie":1,"Lana Di Fraja":1},
    },
]


def seed_elite_match_evidence(db):
    for item in LILLE_MATCHES_2025_26:
        row = db.scalar(select(MatchLibraryItem).where(MatchLibraryItem.external_key == item["key"]))
        metadata = {
            "_aquametric": {
                "competition_level": item["level"],
                "source_tier": "federation_official",
                "evidence_scope": "official_goal_list",
                "scorer_list_complete": item["complete"],
            }
        }
        if not row:
            row = MatchLibraryItem(
                external_key=item["key"], title=item["title"], competition=item["competition"],
                season=item["season"], entity_type="club", team_a=item["team_a"], team_b=item["team_b"],
                score_a=item["score_a"], score_b=item["score_b"],
                quarter_scores_json=json.dumps(item["quarters"]), video_url="", video_kind="official_report",
                official_source_url=item["source"], analysis_status="official_public_stats",
                tactical_summary=item["summary"], team_stats_json=json.dumps(metadata),
            )
            db.add(row); db.flush()
        else:
            # Upgrade metadata without rewriting user-created/private data.
            row.team_stats_json = json.dumps(metadata)
            row.tactical_summary = item["summary"]
            row.official_source_url = item["source"]
            row.analysis_status = "official_public_stats"
        for player_name, goals in item["players"].items():
            stat = db.scalar(select(LibraryPlayerMatchStat).where(
                LibraryPlayerMatchStat.library_match_id == row.id,
                LibraryPlayerMatchStat.player_name == player_name,
            ))
            note = "Official FFN scorer list. " + ("Published scorer totals reconcile with team score." if item["complete"] else "Published scorer list is incomplete relative to the final team score; individual listed goals remain official evidence.")
            if not stat:
                db.add(LibraryPlayerMatchStat(
                    library_match_id=row.id, team_name="Lille UC Métropole Water-Polo",
                    player_name=player_name, goals=goals, source_quality="federation_official", note=note,
                ))
            else:
                stat.goals = goals
                stat.source_quality = "federation_official"
                stat.note = note
    db.commit()
