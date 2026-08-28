import json
from sqlalchemy import select

from models import MatchLibraryItem, LibraryPlayerMatchStat

FFN_GRANVILLE_RESULTS = "https://www.extranat.fr/waterpolo/cgi-bin/wp_results.php?action=structure&structure=3021"

# Senior Nationale 1 Féminine 2025-26 only. FFN publishes score, quarter scores and
# official team composition. Individual goals/saves are not exposed on this page,
# so these rows deliberately record APPEARANCE ONLY and must never create a /100 rating.
GRANVILLE_N1_2025_26 = [
    dict(key="FFN-N1F-2526-GRA-SJDA-16-14", date="2025-10-04", opponent="NC Saint Jean d'Angely", home=True, gf=16, ga=14, q=[[6,4],[1,5],[2,4],[7,1]], players=["Maëlle Hequin","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Carmen Sourdrille-Arnal","Sofia Dan","Veronika Lapina","Clémence Letourneur","Mauranne Cosnefroy","Hanae Pezres","Mariia Lytvyniuk"]),
    dict(key="FFN-N1F-2526-MONT-GRA-7-14", date="2025-11-08", opponent="AS Montgeron Water Polo", home=False, gf=14, ga=7, q=[[3,2],[0,3],[2,5],[2,4]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Carmen Sourdrille-Arnal","Sofia Dan","Clémence Letourneur","Mauranne Cosnefroy","Mariia Lytvyniuk","Maëlle Hequin","Amandine Laîné"]),
    dict(key="FFN-N1F-2526-GRA-ARRAS-10-12", date="2025-11-15", opponent="RC Arras Water-Polo", home=True, gf=10, ga=12, q=[[1,2],[2,4],[5,1],[2,5]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Sofia Dan","Clémence Letourneur","Mauranne Cosnefroy","Hanae Pezres","Mariia Lytvyniuk","Maëlle Hequin","Amandine Laîné"]),
    dict(key="FFN-N1F-2526-GRA-LIM-23-10", date="2025-12-06", opponent="ASPTT Limoges", home=True, gf=23, ga=10, q=[[5,1],[5,2],[4,3],[9,4]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Sofia Dan","Clémence Letourneur","Mauranne Cosnefroy","Maëva Murie","Maëlle Hequin"]),
    dict(key="FFN-N1F-2526-PAR-GRA-10-11", date="2026-01-17", opponent="Libellule Paris - RCF", home=False, gf=11, ga=10, q=[[3,2],[1,1],[1,3],[3,2]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Amandine Laîné","Sofia Dan","Eleni Bovali","Clémence Letourneur","Mauranne Cosnefroy","Sofia Kolovou","Maëlle Hequin"]),
    dict(key="FFN-N1F-2526-GRA-LAVAL-16-12", date="2026-01-31", opponent="Laval Water Polo", home=True, gf=16, ga=12, q=[[3,2],[4,4],[6,4],[3,2]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Amandine Laîné","Sofia Dan","Clémence Letourneur","Mauranne Cosnefroy","Maëlle Hequin"]),
    dict(key="FFN-N1F-2526-SJDA-GRA-13-5", date="2026-02-07", opponent="NC Saint Jean d'Angely", home=False, gf=5, ga=13, q=[[4,3],[5,1],[2,0],[2,1]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Amandine Laîné","Sofia Dan","Eleni Bovali","Clémence Letourneur","Mauranne Cosnefroy","Sofia Kolovou","Maëlle Hequin"]),
    dict(key="FFN-N1F-2526-GRA-MONT-18-5", date="2026-03-14", opponent="AS Montgeron Water Polo", home=True, gf=18, ga=5, q=[[6,1],[5,2],[2,1],[5,1]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Amandine Laîné","Sofia Dan","Hanae Pezres","Clémence Letourneur","Mauranne Cosnefroy","Maëlle Hequin"]),
    dict(key="FFN-N1F-2526-LIM-GRA-4-14", date="2026-03-21", opponent="ASPTT Limoges", home=False, gf=14, ga=4, q=[[2,4],[2,2],[0,1],[0,7]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Sofia Dan","Clémence Letourneur","Mauranne Cosnefroy","Maëlle Hequin"]),
    dict(key="FFN-N1F-2526-ARRAS-GRA-9-13", date="2026-03-28", opponent="RC Arras Water-Polo", home=False, gf=13, ga=9, q=[[2,4],[5,1],[2,3],[0,5]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Sofia Dan","Eleni Bovali","Clémence Letourneur","Mauranne Cosnefroy","Sofia Kolovou","Maëlle Hequin"]),
    dict(key="FFN-N1F-2526-GRA-PAR-11-9", date="2026-04-25", opponent="Libellule Paris - RCF", home=True, gf=11, ga=9, q=[[1,3],[2,2],[3,1],[5,3]], players=["Luce Berthonneau","Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Amandine Laîné","Sofia Dan","Eleni Bovali","Clémence Letourneur","Mauranne Cosnefroy","Hanae Pezres","Maëlle Hequin"]),
    dict(key="FFN-N1F-2526-LAVAL-GRA-14-15", date="2026-05-09", opponent="Laval Water Polo", home=False, gf=15, ga=14, q=[[1,2],[4,2],[3,2],[2,4]], players=["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Amandine Laîné","Sofia Dan","Verlaine Germanicus","Clémence Letourneur","Mauranne Cosnefroy","Hanae Pezres","Maëlle Hequin"]),
]


def seed_granville_match_evidence(db):
    for item in GRANVILLE_N1_2025_26:
        team_a = "Granville Water Polo" if item["home"] else item["opponent"]
        team_b = item["opponent"] if item["home"] else "Granville Water Polo"
        score_a = item["gf"] if item["home"] else item["ga"]
        score_b = item["ga"] if item["home"] else item["gf"]
        row = db.scalar(select(MatchLibraryItem).where(MatchLibraryItem.external_key == item["key"]))
        meta = {"_aquametric": {"competition_level": 2, "source_tier": "federation_official", "evidence_scope": "official_match_sheet_lineup", "individual_stats_available": False, "match_date": item["date"]}}
        if not row:
            row = MatchLibraryItem(
                external_key=item["key"], title=f"{team_a} vs {team_b} — Nationale 1 Féminine",
                competition="Nationale 1 Féminine", season="2025-2026", entity_type="club",
                team_a=team_a, team_b=team_b, score_a=score_a, score_b=score_b,
                quarter_scores_json=json.dumps(item["q"]), video_url="", video_kind="official_match_sheet",
                official_source_url=FFN_GRANVILLE_RESULTS, analysis_status="official_lineup_only",
                tactical_summary="Official FFN result and team composition. Individual goals, saves and event statistics are not published in this source and are not inferred.",
                team_stats_json=json.dumps(meta),
            )
            db.add(row); db.flush()
        else:
            row.team_stats_json = json.dumps(meta)
            row.official_source_url = FFN_GRANVILLE_RESULTS
            row.analysis_status = "official_lineup_only"
        for player_name in item["players"]:
            stat = db.scalar(select(LibraryPlayerMatchStat).where(
                LibraryPlayerMatchStat.library_match_id == row.id,
                LibraryPlayerMatchStat.player_name == player_name,
            ))
            if not stat:
                db.add(LibraryPlayerMatchStat(
                    library_match_id=row.id, team_name="Granville Water Polo", player_name=player_name,
                    source_quality="official_match_sheet",
                    note=f"Official FFN team composition for {item['date']}. Presence is verified; individual performance statistics are not published on this source.",
                ))
            else:
                stat.source_quality = "official_match_sheet"
                stat.note = f"Official FFN team composition for {item['date']}. Presence is verified; individual performance statistics are not published on this source."
    db.commit()
