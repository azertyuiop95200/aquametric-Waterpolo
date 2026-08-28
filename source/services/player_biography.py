from sqlalchemy import select

from models import ScoutingPlayer, ScoutingTeam

# Curated facts are deliberately narrow: every claim carries a source and a trust tier.
# Unknown former clubs / honours stay unknown rather than being inferred from nationality or age.
FFN_LILLE_2026_TITLE = "https://www.ffnatation.fr/actualites/actu-grand-public/lille-champion-de-france-2026"
FFN_LILLE_RESULTS = "https://www.extranat.fr/waterpolo/cgi-bin/wp_results.php?action=structure&structure=422"
FFN_LILLE_NANCY_2026 = "https://www.ffnatation.fr/actualites/actu-grand-public/lille-simpose-bordeaux-et-nice-font-le-job"
LILLE_PALMARES = "https://lucmwp.wordpress.com/notre-palmares/"
AIFN_CHAMPIONS = "https://www.aifn.fr/water-polo-champion-de-france-dame/"
MVLSZ_ANNA_PAL = "https://waterpolo.hu/adatbank/jatekos/7656"
RFEN_CARMEN_2015 = "https://cdn.rfen.es/sectionFiles/rfen_7Q1U6V5MXK33.pdf"
REAL_CANOE_2023 = "https://www.realcanoe.es/images/CANOE/Noticias/2023/Galardonados_GALA_SOCIAL_Y_DEPORTIVA_2023.pdf"
WORLD_AQUATICS_CARMEN = "https://www.worldaquatics.com/athletes/1051595/carmen-baringo-romero"
RAPALLO_CECILIA = "https://www.teleradiopace.tv/2026/08/13/pallanuoto-a-rapallo-arriva-la-mancina-romana-cecilia-nardini/"


def _fact(kind, title, detail, season, url, trust="official"):
    return {
        "kind": kind,
        "title": title,
        "detail": detail,
        "season": season,
        "url": url,
        "trust": trust,
    }


CURATED = {
    "Cecilia Nardini": {
        "current_club": "Rapallo Pallanuoto",
        "current_club_status": "2026–27 arrival reported by Italian media; official team sheet still to confirm registration.",
        "honours": [
            _fact("honour", "Championne de France Elite", "Lille termine la saison 2025–26 invaincu et remporte la finale 17–10 contre Grand Nancy.", "2025–2026", FFN_LILLE_2026_TITLE),
            _fact("honour", "Championne de France", "Cecilia Nardini figure dans l'effectif champion de France 2025 de Lille.", "2024–2025", AIFN_CHAMPIONS, "federation_alumni"),
        ],
        "career": [
            _fact("career", "Lille UC Métropole Water-Polo", "Présence répétée sur les feuilles de match FFN de l'Elite féminine.", "2024–2026", FFN_LILLE_RESULTS),
            _fact("career", "Rapallo Pallanuoto", "Arrivée annoncée pour la saison suivante après son passage à Lille.", "2026–2027", RAPALLO_CECILIA, "media_confirmed"),
        ],
        "highlights": [
            _fact("performance", "7 buts en finale du championnat 2026", "Meilleure marqueuse de la finale Lille–Grand Nancy remportée 17–10.", "2026", FFN_LILLE_2026_TITLE),
        ],
    },
    "Carmen Baringo Romero": {
        "honours": [
            _fact("honour", "Championne de France Elite", "Lille remporte le titre 2026 après une saison sans défaite; Carmen marque 2 buts en finale.", "2025–2026", FFN_LILLE_2026_TITLE),
            _fact("honour", "Championne de France", "Carmen figure dans l'effectif lillois champion en 2025.", "2024–2025", AIFN_CHAMPIONS, "federation_alumni"),
            _fact("honour", "Championne de France", "Carmen figure dans l'effectif lillois champion en 2024.", "2023–2024", LILLE_PALMARES, "club_archive"),
        ],
        "career": [
            _fact("former_club", "CN La Latina", "La convocation officielle espagnole U17 pour les Jeux Européens 2015 indique CN La Latina comme club.", "2015", RFEN_CARMEN_2015),
            _fact("former_club", "Real Canoe", "Le palmarès social 2023 du club cite Carmen parmi ses sportives water-polo et l'équipe senior féminine promue en División de Honor.", "2023", REAL_CANOE_2023, "club_official"),
            _fact("career", "Lille UC Métropole Water-Polo", "Présence confirmée sur les feuilles de match FFN 2025–26 et dans les effectifs champions précédents.", "2023–2026", FFN_LILLE_RESULTS),
        ],
        "highlights": [
            _fact("performance", "2 buts en finale du championnat 2026", "Lille bat Grand Nancy 17–10; Carmen Baringo Romero inscrit 2 buts.", "2026", FFN_LILLE_2026_TITLE),
            _fact("identity", "Profil World Aquatics", "Fiche internationale World Aquatics: nationalité ESP, discipline water-polo.", "international", WORLD_AQUATICS_CARMEN),
        ],
    },
    "Anna Pal": {
        "honours": [
            _fact("honour", "Membre du Lille champion 2025–26", "Anna Pal apparaît sur les feuilles de match de la saison du titre; la finale et le titre sont confirmés par la FFN.", "2025–2026", FFN_LILLE_RESULTS),
        ],
        "career": [
            _fact("former_club", "III. Kerületi TVE", "La base officielle de la fédération hongroise enregistre Anna Pál avec III. Kerületi TVE en championnat et coupe hongroise.", "2020–2022", MVLSZ_ANNA_PAL),
            _fact("career", "Lille UC Métropole Water-Polo", "Feuilles de match FFN Elite féminine 2025–26.", "2025–2026", FFN_LILLE_RESULTS),
        ],
        "highlights": [
            _fact("performance", "5 buts contre Grand Nancy", "La FFN crédite Anna Pal de 5 buts lors d'une victoire lilloise en 2026.", "2026", FFN_LILLE_NANCY_2026),
        ],
    },
    "Clémence Goulu": {
        "career": [
            _fact("career", "Lille UC Métropole Water-Polo", "Clémence Goulu apparaît sur plusieurs feuilles de match FFN de l'Elite féminine 2025–26.", "2025–2026", FFN_LILLE_RESULTS),
        ],
        "highlights": [],
        "honours": [],
    },
}


def player_biography_context(db, profile, scout_rows=None):
    scout_rows = list(scout_rows or db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.name == profile.canonical_name)).all())
    history = []
    seen = set()
    for row in scout_rows:
        team = db.get(ScoutingTeam, row.scouting_team_id)
        if not team:
            continue
        key = (team.name, row.source_season)
        if key in seen:
            continue
        seen.add(key)
        history.append({
            "team": team.name,
            "season": row.source_season or team.season_label,
            "status": row.current_status,
            "role": row.role,
            "birth_year": row.birth_year,
            "source_url": row.source_url or team.source_url,
            "source_quality": row.source_quality,
        })

    curated = CURATED.get(profile.canonical_name, {})
    career = list(curated.get("career", []))
    honours = list(curated.get("honours", []))
    highlights = list(curated.get("highlights", []))
    former_clubs = [x for x in career if x["kind"] == "former_club"]

    gaps = []
    if not former_clubs:
        gaps.append("Former water-polo clubs are not yet verified from a reliable source.")
    if not honours:
        gaps.append("No individual or team honour has been attached with sufficient evidence yet.")
    if not highlights:
        gaps.append("More official match reports are needed for performance highlights.")
    if "pending" in (profile.roster_status or "") or "historical" in (profile.roster_status or ""):
        gaps.append("Current-season registration still needs a fresh official roster or match sheet.")

    primary = scout_rows[0] if scout_rows else None
    return {
        "bio": {
            "current_club": curated.get("current_club") or profile.current_club,
            "current_club_status": curated.get("current_club_status") or profile.roster_status.replace("_", " "),
            "birth_year": primary.birth_year if primary else None,
            "honours": honours,
            "career": career,
            "former_clubs": former_clubs,
            "highlights": highlights,
            "scout_history": history,
            "research_gaps": gaps,
        }
    }
