GRANVILLE_LAPINA = "https://www.granvillewaterpolo.com/caf/"
USB_COLACO = "https://www.saint-bruno.org/water-polo/la-section/les-entraineurs"
TAVERNY_MICHAELI = "https://haut-niveau.tsn95.fr/index.php/equipe-n1-feminine/"


def _fact(kind, title, detail, season, url, trust="club_official"):
    return {"kind": kind, "title": title, "detail": detail, "season": season, "url": url, "trust": trust}


COACH_CURATED = {
    "Veronika Lapina": {
        "career": [
            _fact("player_pathway", "Kirishi / Russie", "Formation dans l'école russe de Kirishi puis parcours international junior russe.", "formation–2019", GRANVILLE_LAPINA),
            _fact("coach", "Sporting Club Alexandria — académie", "Responsable et Head Coach de l'académie du club à Alexandrie.", "2019", GRANVILLE_LAPINA),
            _fact("player_pathway", "Lille Métropole Water-Polo", "Joueuse professionnelle à Lille depuis 2020 selon le CAF de Granville.", "2020–2025", GRANVILLE_LAPINA),
            _fact("coach", "Lille Métropole Water-Polo U14", "Coach de l'équipe U14 lilloise.", "2023–2025", GRANVILLE_LAPINA),
            _fact("coach", "Granville Water Polo — CAF", "Encadrement du centre d'accession et de formation, avec mission de développement des jeunes joueuses.", "2025–2026", GRANVILLE_LAPINA),
        ],
        "honours": [
            _fact("honour", "Vainqueure Women's Euroleague", "Palmarès international de joueuse présenté par Granville.", "2017–2018", GRANVILLE_LAPINA),
            _fact("honour", "Vainqueure Super Coupe d'Europe", "Super Coupe d'Europe remportée à Budapest à 18 ans.", "2017–2018", GRANVILLE_LAPINA),
            _fact("honour", "5× championne de France", "Granville recense cinq titres de championne de France sur la période 2020–2025.", "2020–2025", GRANVILLE_LAPINA),
            _fact("honour", "5× Coupe de France", "Granville recense cinq Coupes de France sur la période 2021–2025.", "2021–2025", GRANVILLE_LAPINA),
        ],
    },
    "Tristan Colaço": {
        "career": [
            _fact("player_pathway", "Blois", "Débute le water-polo à 11 ans dans sa ville natale.", "formation", USB_COLACO),
            _fact("player_pathway", "Laval", "Rejoint Laval à 15 ans pour évoluer au niveau national.", "formation", USB_COLACO),
            _fact("player_pathway", "Saint-Jean-d’Angély", "Joue en deuxième division nationale et se familiarise avec le rôle d'entraîneur pendant cinq saisons.", "2018–2023", USB_COLACO),
            _fact("coach", "Nouvelle-Aquitaine", "Sélectionneur d'équipes féminines régionales.", "avant 2023", USB_COLACO),
            _fact("coach", "Union Saint-Bruno Bordeaux", "Entraîne l'Élite féminine, les U14 féminines et les U16 féminines.", "depuis 2023", USB_COLACO),
        ],
        "honours": [
            _fact("honour", "Champion de France D2 féminine", "Titre remporté comme entraîneur avec l'équipe première.", "carrière coach", USB_COLACO),
            _fact("honour", "Vice-champion de France U17 féminin", "Deuxième place nationale obtenue comme entraîneur.", "carrière coach", USB_COLACO),
            _fact("honour", "3e Coupe de France des Ligues U15", "Troisième place avec la sélection féminine Nouvelle-Aquitaine.", "2022", USB_COLACO),
        ],
    },
    "Thomas Michaeli": {
        "career": [
            _fact("coach", "Taverny Sports Nautiques 95", "Le site officiel du pôle haut niveau le liste entraîneur de l'équipe Elite féminine.", "2024–2025", TAVERNY_MICHAELI),
        ],
        "honours": [
            _fact("honour", "Champion de France avec Taverny", "La page officielle indique que le dernier match 2024–25 permet à l'équipe féminine de conserver le titre de championne de France.", "2024–2025", TAVERNY_MICHAELI),
        ],
    },
}


def coach_biography_for(coach):
    curated = COACH_CURATED.get(coach.canonical_name, {})
    career = list(curated.get("career", []))
    honours = list(curated.get("honours", []))
    source_urls = {x["url"] for x in career + honours if x.get("url")}
    if coach.source_url:
        source_urls.add(coach.source_url)
    score = 20
    if career:
        score += 35
    if honours:
        score += 25
    score += min(20, len(source_urls) * 5)
    gaps = []
    if not career:
        gaps.append("Parcours antérieur non encore documenté par une source fiable.")
    if not honours:
        gaps.append("Aucun palmarès directement attribuable à ce coach n'est encore attaché.")
    if coach.evaluation_overall is None:
        gaps.append("La performance de coaching reste non notée tant que suffisamment de matchs ne sont pas reliés au profil.")
    return {
        "career": career,
        "honours": honours,
        "research_gaps": gaps,
        "completeness": min(100, score),
        "verified_fact_count": len(career) + len(honours),
    }
