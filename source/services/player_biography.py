from sqlalchemy import select

from models import ScoutingPlayer, ScoutingTeam

# Every biography claim must carry a traceable source. Curated facts cover high-value
# history/honours; verified scouting rows are promoted automatically into the career
# timeline so the long tail of profiles does not stay empty.
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

USC_AUSMUS = "https://usctrojans.com/sports/womens-water-polo/roster/emily-ausmus/17964"
USC_AUSMUS_CUTINO = "https://usctrojans.com/news/2026/6/6/womens-water-polo-uscs-emily-ausmus-wins-peter-j-cutino-award"
USA_AUSMUS = "https://usawaterpolo.org/sports/womens-water-polo/roster/emily--ausmus/927"
CNAB_ELENA = "https://www.cnab.cat/elena-ruiz-nueva-incorporacion-del-equipo-femenino/"
WORLD_AQUATICS_ELENA = "https://www.worldaquatics.com/athletes/1530101/wd/medals"
RFEN_2024_SPAIN = "https://cdn.rfen.es/sectionFiles/Zj4gSPHAyx.pdf"
SIS_ROMA_ROZIC = "https://sisroma.it/secondo-acquisto-per-la-sis-roma-iva-rozic-vestira-il-giallorosso-nella-stagione-2026-2027/"
WORLD_AQUATICS_ROZIC = "https://www.worldaquatics.com/athletes/1651260/iva-rozic/profile"
WORLD_AQUATICS_PIRALKOVA = "https://www.worldaquatics.com/athletes/1739911/wd/medals"
RFEN_PIRALKOVA_2025 = "https://cdn.rfen.es/sectionFiles/1761831026_4363.pdf"
RFEN_PIRALKOVA_SCORERS = "https://rfen.es/especialidades/waterpolo/competicion/1511/resumen/"
RFEN_PIRALKOVA_4X4 = "https://rfen.es/noticia/convocatorias-de-espana-para-el-world-aquatics-4x4-open-championships-de-dubrovnik-359123/"
GRANVILLE_RUMINA = "https://www.granvillewaterpolo.com/2025/10/24/effectif-saison-2025-2026/"
GRANVILLE_MORGANE = "https://www.granvillewaterpolo.com/2025/10/26/effectif-saison-2025-2026/"
GRANVILLE_CAPUCINE = "https://www.granvillewaterpolo.com/2025/10/28/effectif-saison-2025-2026/"


def _fact(kind, title, detail, season, url, trust="official"):
    return {"kind": kind, "title": title, "detail": detail, "season": season, "url": url, "trust": trust}


def _append_unique(bucket, fact, seen):
    key = (fact.get("kind"), fact.get("title"), fact.get("season"), fact.get("url"))
    if key not in seen:
        seen.add(key)
        bucket.append(fact)


CURATED = {
    "Cecilia Nardini": {
        "current_club": "Rapallo Pallanuoto",
        "current_club_status": "Arrivée 2026–27 signalée par un média italien spécialisé ; la feuille d’équipe officielle doit encore confirmer l’inscription.",
        "honours": [
            _fact("honour", "Championne de France Elite", "Lille termine la saison 2025–26 invaincu et remporte la finale 17–10 contre Grand Nancy.", "2025–2026", FFN_LILLE_2026_TITLE),
            _fact("honour", "Championne de France", "Cecilia Nardini figure dans l'effectif champion de France 2025 de Lille.", "2024–2025", AIFN_CHAMPIONS, "federation_alumni"),
        ],
        "career": [
            _fact("career", "Lille UC Métropole Water-Polo", "Présence répétée sur les feuilles de match FFN de l'Elite féminine.", "2024–2026", FFN_LILLE_RESULTS),
            _fact("career", "Rapallo Pallanuoto", "Arrivée annoncée pour la saison suivante après son passage à Lille.", "2026–2027", RAPALLO_CECILIA, "media_confirmed"),
        ],
        "highlights": [_fact("performance", "7 buts en finale du championnat 2026", "Meilleure marqueuse de la finale Lille–Grand Nancy remportée 17–10.", "2026", FFN_LILLE_2026_TITLE)],
    },
    "Carmen Baringo Romero": {
        "honours": [
            _fact("honour", "Championne de France Elite", "Lille remporte le titre 2026 après une saison sans défaite ; Carmen marque 2 buts en finale.", "2025–2026", FFN_LILLE_2026_TITLE),
            _fact("honour", "Championne de France", "Carmen figure dans l'effectif lillois champion en 2025.", "2024–2025", AIFN_CHAMPIONS, "federation_alumni"),
            _fact("honour", "Championne de France", "Carmen figure dans l'effectif lillois champion en 2024.", "2023–2024", LILLE_PALMARES, "club_archive"),
        ],
        "career": [
            _fact("former_club", "CN La Latina", "La convocation officielle espagnole U17 pour les Jeux Européens 2015 indique CN La Latina comme club.", "2015", RFEN_CARMEN_2015),
            _fact("former_club", "Real Canoe", "Le palmarès social 2023 du club cite Carmen parmi ses sportives water-polo et l'équipe senior féminine promue en División de Honor.", "2023", REAL_CANOE_2023, "club_official"),
            _fact("career", "Lille UC Métropole Water-Polo", "Présence confirmée sur les feuilles de match FFN 2025–26 et dans les effectifs champions précédents.", "2023–2026", FFN_LILLE_RESULTS),
        ],
        "highlights": [
            _fact("performance", "2 buts en finale du championnat 2026", "Lille bat Grand Nancy 17–10 ; Carmen Baringo Romero inscrit 2 buts.", "2026", FFN_LILLE_2026_TITLE),
            _fact("identity", "Profil World Aquatics", "Fiche internationale World Aquatics : nationalité ESP, discipline water-polo.", "international", WORLD_AQUATICS_CARMEN),
        ],
    },
    "Anna Pal": {
        "honours": [_fact("honour", "Membre du Lille champion 2025–26", "Anna Pal apparaît sur les feuilles de match de la saison du titre ; la finale et le titre sont confirmés par la FFN.", "2025–2026", FFN_LILLE_RESULTS)],
        "career": [
            _fact("former_club", "III. Kerületi TVE", "La base officielle de la fédération hongroise enregistre Anna Pál avec III. Kerületi TVE en championnat et coupe hongroise.", "2020–2022", MVLSZ_ANNA_PAL),
            _fact("career", "Lille UC Métropole Water-Polo", "Feuilles de match FFN Elite féminine 2025–26.", "2025–2026", FFN_LILLE_RESULTS),
        ],
        "highlights": [_fact("performance", "5 buts contre Grand Nancy", "La FFN crédite Anna Pal de 5 buts lors d'une victoire lilloise en 2026.", "2026", FFN_LILLE_NANCY_2026)],
    },
    "Clémence Goulu": {
        "career": [_fact("career", "Lille UC Métropole Water-Polo", "Clémence Goulu apparaît sur plusieurs feuilles de match FFN de l'Elite féminine 2025–26.", "2025–2026", FFN_LILLE_RESULTS)],
        "highlights": [], "honours": [],
    },
    "Emily Ausmus": {
        "birth_year": 2005,
        "current_club": "USC Trojans",
        "current_club_status": "La fiche officielle USC 2026 la liste comme sophomore et attaquante ; son profil USA Water Polo confirme son activité avec l'équipe nationale.",
        "career": [
            _fact("former_club", "SOCAL / Riverside Water Polo", "La biographie officielle USC indique un parcours club à SOCAL et Riverside Water Polo avant l'université.", "formation", USC_AUSMUS, "university_official"),
            _fact("career", "USC Trojans", "Titulaire du roster USC 2026 après une saison freshman 2025 record.", "2025–2026", USC_AUSMUS, "university_official"),
            _fact("national_team", "United States", "Membre de l'équipe nationale senior américaine, avec des campagnes mondiales et olympiques documentées.", "2023–2026", USA_AUSMUS, "federation_official"),
        ],
        "honours": [
            _fact("honour", "Championne NCAA", "USC remporte le championnat national 2026 ; Ausmus est NCAA Tournament MVP.", "2026", USC_AUSMUS, "university_official"),
            _fact("honour", "Peter J. Cutino Award", "Lauréate 2026 du trophée récompensant la meilleure joueuse NCAA Division I.", "2026", USC_AUSMUS_CUTINO, "university_official"),
            _fact("honour", "Championne du monde", "USA Water Polo documente l'or au World Aquatics World Championships de Doha.", "2024", USA_AUSMUS, "federation_official"),
            _fact("honour", "Championne Panaméricaine", "Or avec Team USA aux Jeux Panaméricains de Santiago.", "2023", USA_AUSMUS, "federation_official"),
        ],
        "highlights": [
            _fact("performance", "77 buts et 107 points avec USC", "Leader de USC en buts et points sur la saison 2026.", "2026", USC_AUSMUS, "university_official"),
            _fact("performance", "114 buts, record USC sur une saison", "Record de buts sur une saison comme freshman et joueuse la plus rapide du programme à atteindre 100 buts en carrière.", "2025", USC_AUSMUS, "university_official"),
        ],
    },
    "Elena Ruiz": {
        "current_club": "CN Atlètic-Barceloneta",
        "current_club_status": "Le CN Atlètic-Barceloneta a officiellement annoncé son arrivée dans l'équipe première féminine en août 2026.",
        "career": [
            _fact("former_club", "CN Rubí", "Le CN Atlètic-Barceloneta présente Elena Ruiz comme formée au CN Rubí.", "formation", CNAB_ELENA, "club_official"),
            _fact("former_club", "CN Sabadell", "Le club d'arrivée retrace un passage par le CN Sabadell avant Sant Andreu.", "avant 2024", CNAB_ELENA, "club_official"),
            _fact("former_club", "CN Sant Andreu", "La RFEN la liste avec CN Sant Andreu dans la sélection espagnole 2024 et le CNAB confirme ce passage.", "2024–2026", RFEN_2024_SPAIN, "federation_official"),
            _fact("career", "CN Atlètic-Barceloneta", "Nouvelle incorporation officielle du premier effectif féminin.", "2026–2027", CNAB_ELENA, "club_official"),
        ],
        "honours": [
            _fact("honour", "Championne olympique", "Médaille d'or olympique avec l'Espagne à Paris.", "2024", WORLD_AQUATICS_ELENA, "world_aquatics"),
            _fact("honour", "Vice-championne olympique", "Médaille d'argent olympique avec l'Espagne à Tokyo.", "2021", WORLD_AQUATICS_ELENA, "world_aquatics"),
            _fact("honour", "Deux Champions League de clubs", "Le CNAB crédite Elena d'une Champions League avec Sabadell et d'une avec Sant Andreu.", "carrière", CNAB_ELENA, "club_official"),
            _fact("honour", "Podiums mondiaux", "World Aquatics recense une médaille d'argent mondiale et deux bronzes mondiaux.", "2023–2025", WORLD_AQUATICS_ELENA, "world_aquatics"),
        ],
        "highlights": [_fact("identity", "10 médailles AQUA et olympiques", "World Aquatics recense 3 ors, 5 argents et 2 bronzes sur son profil de médailles.", "carrière internationale", WORLD_AQUATICS_ELENA, "world_aquatics")],
    },
    "Iva Rozic": {
        "birth_year": 2005,
        "current_club": "SIS Roma",
        "current_club_status": "SIS Roma a officiellement annoncé Iva Rožić pour la saison 2026–27.",
        "career": [
            _fact("former_club", "Mladost Zagreb", "SIS Roma indique qu'elle a poursuivi sa formation pendant deux saisons au Mladost Zagreb.", "avant 2025–2026", SIS_ROMA_ROZIC, "club_official"),
            _fact("former_club", "Cosenza", "SIS Roma confirme qu'elle a joué la saison précédente à Cosenza.", "2025–2026", SIS_ROMA_ROZIC, "club_official"),
            _fact("career", "SIS Roma", "Deuxième recrue officiellement annoncée pour le roster 2026–27.", "2026–2027", SIS_ROMA_ROZIC, "club_official"),
            _fact("national_team", "Croatie", "Internationale croate senior et jeunes avec participations européennes et mondiales.", "international", WORLD_AQUATICS_ROZIC, "world_aquatics"),
        ],
        "honours": [_fact("honour", "Conference Cup avec Cosenza", "SIS Roma crédite Rožić d'une contribution à la conquête de la Conference Cup avec Cosenza.", "2025–2026", SIS_ROMA_ROZIC, "club_official")],
        "highlights": [
            _fact("performance", "Meilleure marqueuse des Mondiaux juniors", "Le communiqué officiel SIS Roma cite ce titre individuel obtenu au Brésil.", "junior", SIS_ROMA_ROZIC, "club_official"),
            _fact("performance", "2e meilleure marqueuse aux Européens de Madeira", "Le communiqué SIS Roma cite sa deuxième place au classement des buteuses.", "junior", SIS_ROMA_ROZIC, "club_official"),
        ],
    },
    "Isabel Piralkova": {
        "birth_year": 2005,
        "current_club": "CN Sabadell",
        "current_club_status": "La convocation RFEN du 27 août 2026 pour le World Aquatics 4x4 Open la liste avec le CN Sabadell.",
        "career": [
            _fact("former_club", "CN Terrassa", "Les convocations RFEN 2024–25 et U20 2025 la listent au CN Terrassa.", "2024–2025", RFEN_PIRALKOVA_2025, "federation_official"),
            _fact("career", "CN Sabadell", "La RFEN la liste avec le CN Sabadell dans ses convocations senior 2026.", "2026–2027", RFEN_PIRALKOVA_4X4, "federation_official"),
        ],
        "honours": [
            _fact("honour", "Championne olympique", "Médaille d'or avec l'Espagne aux Jeux de Paris.", "2024", WORLD_AQUATICS_PIRALKOVA, "world_aquatics"),
            _fact("honour", "Bronze mondial", "Médaille de bronze aux Championnats du monde de Doha.", "2024", WORLD_AQUATICS_PIRALKOVA, "world_aquatics"),
            _fact("honour", "Double vice-championne du monde U20", "World Aquatics recense deux médailles d'argent aux Mondiaux U20.", "U20", WORLD_AQUATICS_PIRALKOVA, "world_aquatics"),
        ],
        "highlights": [_fact("performance", "Meilleure buteuse de División de Honor", "La RFEN la classe première avec 50 buts sur la saison 2025–26.", "2025–2026", RFEN_PIRALKOVA_SCORERS, "federation_official")],
    },
    "Rumina Edgerton": {
        "current_club": "Granville Water Polo",
        "current_club_status": "Granville l'a officiellement présentée comme nouvelle gardienne de N1 pour 2025–26 ; le statut 2026–27 reste à confirmer par une source de saison.",
        "career": [
            _fact("former_club", "Mulhouse Water-Polo", "Granville indique trois saisons à Mulhouse en Elite, Eurocup et Ligue des champions.", "environ 2022–2024", GRANVILLE_RUMINA, "club_official"),
            _fact("career", "Canada", "Dernière saison disputée au Canada avant son arrivée à Granville.", "2024–2025", GRANVILLE_RUMINA, "club_official"),
            _fact("career", "Granville Water Polo", "Recrue N1 féminine et gardienne annoncée par le club.", "2025–2026", GRANVILLE_RUMINA, "club_official"),
        ],
        "honours": [
            _fact("honour", "2e aux Jeux Panaméricains U17", "Résultat international junior présenté par Granville dans sa fiche joueuse.", "junior", GRANVILLE_RUMINA, "club_official"),
            _fact("honour", "Vice-championne de France Elite", "Granville recense des deuxièmes places en championnat de France Elite lors de son passage à Mulhouse.", "2022–2024", GRANVILLE_RUMINA, "club_official"),
        ],
        "highlights": [_fact("performance", "Expérience Ligue des champions", "Trois saisons à Mulhouse avec participation à la Ligue des champions et un top 12 européen cité par Granville.", "2022–2024", GRANVILLE_RUMINA, "club_official")],
    },
    "Morgane Le Berre": {
        "current_club": "Granville Water Polo",
        "current_club_status": "Joueuse de N1 présentée officiellement par Granville pour 2025–26 ; continuité 2026–27 à confirmer.",
        "career": [
            _fact("career", "Granville Water Polo", "Parcours de formation au club puis présence en équipe féminine dès sa création en N1.", "formation–2026", GRANVILLE_MORGANE, "club_official"),
            _fact("national_team", "France U16", "Sélection en équipe de France U16 et participation au Mondial U16.", "2024", GRANVILLE_MORGANE, "club_official"),
        ],
        "honours": [_fact("honour", "4e Coupe de France des Ligues U16F", "Quatrième place avec l'équipe Grand Ouest.", "2023", GRANVILLE_MORGANE, "club_official")],
        "highlights": [_fact("performance", "Mondial U16", "Participation aux Championnats du monde U16 en juillet 2024.", "2024", GRANVILLE_MORGANE, "club_official")],
    },
    "Capucine Pillais": {
        "current_club": "Granville Water Polo",
        "current_club_status": "Contre-pointe de N1 présentée officiellement par Granville pour 2025–26 ; continuité 2026–27 à confirmer.",
        "career": [_fact("career", "Granville Water Polo", "Progression documentée de l'équipe mixte vers les U14, U16 puis la N1.", "formation–2026", GRANVILLE_CAPUCINE, "club_official")],
        "honours": [
            _fact("honour", "Championne de France U14", "Titre national U14 avec son parcours granvillais.", "2024", GRANVILLE_CAPUCINE, "club_official"),
            _fact("honour", "3e du Championnat de France U16", "Troisième place nationale U16.", "2025", GRANVILLE_CAPUCINE, "club_official"),
            _fact("honour", "Vice-championne Grand Ouest — CFL", "Deuxième place avec la sélection Grand Ouest.", "2024", GRANVILLE_CAPUCINE, "club_official"),
        ],
        "highlights": [_fact("development", "Présélections Championnats d'Europe", "Granville indique une participation aux présélections européennes la saison précédente.", "2025", GRANVILLE_CAPUCINE, "club_official")],
    },
}


def _auto_career_from_scouting(profile, scout_rows, curated_current_club):
    facts, seen = [], set()
    current = (curated_current_club or profile.current_club or "").strip().lower()
    for row in scout_rows:
        team = getattr(row, "_aquametric_team", None)
        if not team:
            continue
        source_url = row.source_url or team.source_url
        if not source_url:
            continue
        season = row.source_season or team.season_label or "season not specified"
        kind = "career"
        if current and team.team_type == "club" and team.name.strip().lower() != current:
            kind = "former_club"
        _append_unique(facts, _fact(
            kind, team.name,
            f"Présence dans un roster/une source d'effectif traçable ({row.current_status or 'status documented'}).",
            season, source_url, row.source_quality or "roster_source",
        ), seen)
    return facts


def _completeness(profile, current_club, career, honours, highlights, scout_history):
    score = 0
    if profile.nationality:
        score += 10
    if profile.role:
        score += 10
    if current_club:
        score += 15
    if career:
        score += 25
    if honours:
        score += 15
    if highlights:
        score += 10
    source_urls = {x.get("url") for x in (career + honours + highlights) if x.get("url")}
    source_urls.update(x.get("source_url") for x in scout_history if x.get("source_url"))
    score += min(15, len(source_urls) * 3)
    return min(100, score), len(career) + len(honours) + len(highlights)


def player_biography_context(db, profile, scout_rows=None):
    scout_rows = list(scout_rows or db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.name == profile.canonical_name)).all())
    history, seen_history = [], set()
    for row in scout_rows:
        team = db.get(ScoutingTeam, row.scouting_team_id)
        if not team:
            continue
        row._aquametric_team = team
        key = (team.name, row.source_season)
        if key in seen_history:
            continue
        seen_history.add(key)
        history.append({
            "team": team.name, "season": row.source_season or team.season_label,
            "status": row.current_status, "role": row.role, "birth_year": row.birth_year,
            "source_url": row.source_url or team.source_url, "source_quality": row.source_quality,
        })

    curated = CURATED.get(profile.canonical_name, {})
    career, honours, highlights = [], [], []
    career_seen, honours_seen, highlights_seen = set(), set(), set()
    for fact in curated.get("career", []):
        _append_unique(career, fact, career_seen)
    for fact in _auto_career_from_scouting(profile, scout_rows, curated.get("current_club")):
        _append_unique(career, fact, career_seen)
    current_club = curated.get("current_club") or profile.current_club
    has_current_fact = any((x.get("title") or "").strip().lower() == (current_club or "").strip().lower() for x in career)
    if current_club and profile.primary_source_url and not has_current_fact:
        _append_unique(career, _fact(
            "career", current_club, "Current-club assignment carried by the canonical profile source.",
            profile.roster_season or "current", profile.primary_source_url, "profile_primary_source",
        ), career_seen)
    for fact in curated.get("honours", []):
        _append_unique(honours, fact, honours_seen)
    for fact in curated.get("highlights", []):
        _append_unique(highlights, fact, highlights_seen)

    former_clubs = [x for x in career if x["kind"] == "former_club"]
    gaps = []
    if not former_clubs:
        gaps.append({"key": "profile.gap.former_clubs", "text": "No earlier club has been verified yet; the career timeline only shows traceable evidence."})
    if not honours:
        gaps.append({"key": "profile.gap.honours", "text": "No individual or team honour has been attached with sufficient evidence yet."})
    if not highlights:
        gaps.append({"key": "profile.gap.highlights", "text": "More official match reports are needed for performance highlights."})
    if "pending" in (profile.roster_status or "") or "historical" in (profile.roster_status or ""):
        gaps.append({"key": "profile.gap.current_roster", "text": "Current-season registration still needs a fresh official roster or match sheet."})

    primary = scout_rows[0] if scout_rows else None
    completeness, verified_fact_count = _completeness(profile, current_club, career, honours, highlights, history)
    return {"bio": {
        "current_club": current_club,
        "current_club_status": curated.get("current_club_status") or (profile.roster_status or "research_required").replace("_", " "),
        "birth_year": curated.get("birth_year") or (primary.birth_year if primary else None),
        "honours": honours, "career": career, "former_clubs": former_clubs, "highlights": highlights,
        "scout_history": history, "research_gaps": gaps,
        "completeness": completeness, "verified_fact_count": verified_fact_count,
    }}
