"""EU-eligible women's youth scouting shortlist for summer 2026.

Additive seed used by the Scouting section. Eligibility is conservative: every
included athlete represents an EU member state. No non-EU athlete is included
without a publicly verified EU passport/citizenship. U18 data intentionally
keeps the 18 Aug 2026 snapshot date from the scouting workbook.
"""

from collections import defaultdict
from sqlalchemy import select
from models import ScoutingTeam, ScoutingPlayer

EU_YOUTH_2026_SOURCE_DATE = "2026-08-18"
EU_YOUTH_2026_PLAYER_COUNT = 62

SOURCES = {
    "u16_comp": "https://www.worldaquatics.com/competitions/5138/world-aquatics-women-s-u16-water-polo-championships-2026",
    "u16_final": "https://www.worldaquatics.com/news/4551499/greece-denies-spain-u16-womens-golden-double",
    "u16_d1": "https://www.worldaquatics.com/news/4546750/spain-starts-u16-womens-title-defence-dominating-serbia",
    "u16_d2": "https://www.worldaquatics.com/news/4547135/clinical-spain-and-hungary-secure-second-successive-victories",
    "u16_d3": "https://www.worldaquatics.com/news/4547721/russia-remains-perfect-and-tops-rankings-after-sinking-croatia",
    "u16_d4": "https://www.worldaquatics.com/news/4548905/spain-shocked-by-greece-en-route-to-u16-womens-quarterfinals",
    "u16_qf": "https://www.worldaquatics.com/news/4549711/spain-netherlands-hungary-and-greece-secure-world-u16-womens-semifinal-berths",
    "u16_sf": "https://www.worldaquatics.com/news/4550495/champion-spain-rattles-sabre-ahead-of-gold-medal-clash-with-greece",
    "u18_comp": "https://www.worldaquatics.com/competitions/5140/world-aquatics-women-s-u18-water-polo-championships-2026",
    "u18_d1": "https://www.worldaquatics.com/news/4561040/spain-starts-with-a-flourish-in-u18-womens-defence",
    "u18_d2": "https://www.worldaquatics.com/news/4561146/spain-and-greece-make-huge-statements",
    "u20_d2": "https://events.europeanaquatics.org/ewpc-2026-u20/oeiras-2026-hungary-and-spain-stay-perfect-as-group-stage-action-heats-up-on-day-two/",
    "u20_cross": "https://events.europeanaquatics.org/ewpc-2026-u20/oeiras-2026-great-britain-croatia-greece-and-neutral-athletes-b-secure-quarterfinal-tickets/",
    "u20_qf": "https://events.europeanaquatics.org/ewpc-2026-u20/oeiras-2026-hungary-italy-spain-and-netherlands-surge-through-to-semifinals/",
    "u20_sf": "https://events.europeanaquatics.org/ewpc-2026-u20/oeiras-2026-hungary-and-spain-set-for-another-gold-medal-showdown-at-womens-u20-european-water-polo-championships/",
    "u20_final": "https://events.europeanaquatics.org/ewpc-2026-u20/oeiras-2026-hungary-u20s-crowned-european-champions-after-edging-epic-shootout-with-spain/",
    "u20_mvp": "https://www.instagram.com/p/DbvRVn0jZJo/",
}

COMPETITIONS = {
    "u16-world": dict(age="U16", name="World Aquatics Women's U16 World Championships 2026", status="completed_official_scouting", data="Terminé — Zagreb, 25-31 juillet 2026", source="u16_comp"),
    "u18-world": dict(age="U18", name="World Aquatics Women's U18 World Championships 2026", status="partial_official_reports_through_2026_08_18", data="Données individuelles arrêtées aux comptes rendus J1-J2 du 18 août 2026", source="u18_comp"),
    "u20-europe": dict(age="U20", name="European Aquatics Women's U20 European Championships 2026", status="completed_official_scouting", data="Terminé — Oeiras, 1-7 août 2026", source="u20_final"),
}

# competition, country, ISO3, player, role, score/15, level, total-known,
# peak goals, peak saves, distinction, reference performance, source-key
PROSPECT_ROWS = [
    # U16 World — 22 EU profiles
    ("u16-world","Greece","GRE","Afroditi Bitsakou","Captain / field player",13,"PRIORITÉ A",16,5,0,"MVP officielle + All-Star","5/7 en demi-finale vs Hongrie; 2 buts en finale","u16_final"),
    ("u16-world","Spain","ESP","Julia Teodoro","Goalkeeper",13,"PRIORITÉ A",None,0,10,"Meilleure gardienne + All-Star","10 arrêts contre la Grèce","u16_final"),
    ("u16-world","Spain","ESP","Ivet Sulla","Field player",11,"PRIORITÉ B",None,6,0,"All-Star","6 buts vs Serbie; 4 vs Pays-Bas; 3 en quart; 6 en demi","u16_sf"),
    ("u16-world","Hungary","HUN","Mandula Mihok","Centre",11,"PRIORITÉ B",None,6,0,"All-Star","6/6 vs Roumanie; 5 en quart vs USA; 3 en demi","u16_qf"),
    ("u16-world","Netherlands","NED","Laura Renkers","Field player",9,"PRIORITÉ B",None,4,0,"All-Star","4 buts en quart de finale vs Russie","u16_qf"),
    ("u16-world","Greece","GRE","Sofia Lampropoulou","Field player",8,"À SUIVRE",None,5,0,"","5 buts vs Mexique; 2 en finale","u16_final"),
    ("u16-world","Greece","GRE","Eleni Elmisian","Field player",7,"À SUIVRE",None,4,0,"","4/4 en demi-finale vs Hongrie; 3 vs Brésil","u16_sf"),
    ("u16-world","Greece","GRE","Ifigeneia Manousaki","Field player",7,"À SUIVRE",None,4,0,"","4 vs Mexique; 3 en quart; 2 en finale","u16_final"),
    ("u16-world","Czechia","CZE","Lucie Bakalova","Field player",7,"À SUIVRE",None,5,0,"","5 buts vs Pérou puis 5 vs Zimbabwe","u16_d2"),
    ("u16-world","Czechia","CZE","Lucie Koubova","Captain / field player",7,"À SUIVRE",None,5,0,"","5 buts vs Pérou puis 5 vs Zimbabwe","u16_d2"),
    ("u16-world","Hungary","HUN","Doniz Domsodi","Captain / field player",6,"À SUIVRE",None,4,0,"","4 buts contre le Canada","u16_d4"),
    ("u16-world","Italy","ITA","Gaia Gattuso","Field player",6,"À SUIVRE",None,6,0,"","6 buts contre Israël","u16_qf"),
    ("u16-world","Hungary","HUN","Zsofia Kokany","Field player",6,"À SUIVRE",None,4,0,"","4 buts en quart de finale contre les USA","u16_qf"),
    ("u16-world","Hungary","HUN","Anasztazia Bagossy","Goalkeeper",5,"PROFIL",None,0,7,"","7 arrêts en quart de finale contre les USA","u16_qf"),
    ("u16-world","Spain","ESP","Maria Abarca","Field player",5,"PROFIL",None,3,0,"","3 buts en demi-finale vs Pays-Bas","u16_sf"),
    ("u16-world","Spain","ESP","Paula Pineda","Field player",5,"PROFIL",None,3,0,"","Deux hat-tricks sur les deux premiers matches; 2 vs Grèce","u16_d2"),
    ("u16-world","Hungary","HUN","Reka Tordai","Field player",5,"PROFIL",None,3,0,"","3 buts vs Roumanie puis 3 vs Ukraine","u16_d3"),
    ("u16-world","Romania","ROU","Teodora Grigore","Goalkeeper",5,"PROFIL",None,0,10,"","10 arrêts sur 20 tirs dans un match de groupe","u16_d2"),
    ("u16-world","Greece","GRE","Georgia Lampatou","Field player",4,"PROFIL",None,3,0,"","3 buts dans la victoire 8-5 contre l'Espagne","u16_d4"),
    ("u16-world","Italy","ITA","Thea Costa","Field player",4,"PROFIL",None,3,0,"","3 buts dans une courte défaite 4-6 vs USA","u16_d4"),
    ("u16-world","Czechia","CZE","Vanda Strnadova","Goalkeeper",4,"PROFIL",None,0,9,"","9 arrêts contre le Zimbabwe","u16_d4"),
    ("u16-world","Greece","GRE","Andriana Kontakou","Goalkeeper",3,"PROFIL",None,0,5,"","5 arrêts sur 6 tirs (83,3 %) en une mi-temps vs Brésil","u16_d3"),

    # U18 World — 18 EU profiles, official recaps through 18 Aug 2026
    ("u18-world","Hungary","HUN","Mandula Mihok","Centre",8,"À SUIVRE",4,4,0,"All-Star U16 2026 (autre compétition)","4 buts vs Pays-Bas","u18_d2"),
    ("u18-world","Croatia","CRO","Neli Jankovic","Senior international / field player",8,"À SUIVRE",6,5,0,"","5 buts vs Chine après avoir marqué contre l'Espagne","u18_d2"),
    ("u18-world","Greece","GRE","Afroditi Bitsakou","Field player",7,"À SUIVRE",3,3,0,"MVP U16 2026 (autre compétition)","3 buts contre l'Italie J2","u18_d2"),
    ("u18-world","Italy","ITA","Malika Bovo","Field player",7,"À SUIVRE",9,5,0,"","4 buts vs Hongrie; 5 vs Grèce","u18_d2"),
    ("u18-world","Germany","GER","Maria Sekulic","Goalkeeper",7,"À SUIVRE",None,0,12,"","12 arrêts contre le Canada","u18_d2"),
    ("u18-world","Hungary","HUN","Kincso Kenez","Captain / field player",6,"À SUIVRE",7,4,0,"","3 buts J1 vs Italie; 4 J2 vs Pays-Bas","u18_d2"),
    ("u18-world","Croatia","CRO","Lara Srhoj","Senior international / field player",6,"À SUIVRE",5,3,0,"","2 buts vs Espagne; 3 vs Chine","u18_d2"),
    ("u18-world","Spain","ESP","Marina Munoz","Field player",6,"À SUIVRE",8,4,0,"","4 buts vs Croatie puis 4 vs USA","u18_d2"),
    ("u18-world","Spain","ESP","Ona Jurado","Field player",6,"À SUIVRE",7,4,0,"","4 buts vs Croatie; 3 vs USA","u18_d2"),
    ("u18-world","Spain","ESP","Queralt Anton","Senior international / field player",6,"À SUIVRE",4,3,0,"","3 buts J1; but extérieur au buzzer vs USA","u18_d2"),
    ("u18-world","Hungary","HUN","Adrienn Hetzl","Field player",5,"PROFIL",5,3,0,"","3 buts J1; au moins 2 en J2","u18_d2"),
    ("u18-world","Greece","GRE","Androniki Karagianni","Field player",5,"PROFIL",4,4,0,"","4 buts contre l'Italie","u18_d2"),
    ("u18-world","Spain","ESP","Martina Fernandez","Field player",5,"PROFIL",6,3,0,"","3 buts J1 puis 3 vs USA","u18_d2"),
    ("u18-world","Malta","MLT","Miia Clarke","Goalkeeper",5,"PROFIL",None,0,9,"","9 arrêts dont 3 penalties stoppés vs Allemagne","u18_d1"),
    ("u18-world","Greece","GRE","Emmanouela Kapetopoulou","Field player",4,"PROFIL",3,3,0,"","3 buts contre l'Italie","u18_d2"),
    ("u18-world","Italy","ITA","Laura Ruani","Centre",4,"PROFIL",3,3,0,"","3 buts contre la Hongrie","u18_d1"),
    ("u18-world","Spain","ESP","Marina Pineda","Field player",4,"PROFIL",4,4,0,"","4 buts contre la Croatie","u18_d1"),
    ("u18-world","Germany","GER","Nele Politze","Field player",4,"PROFIL",3,3,0,"","3 buts contre le Canada","u18_d2"),

    # U20 Europe — 22 EU profiles
    ("u20-europe","Hungary","HUN","Kata Hajdu","Field player",13,"PRIORITÉ A",None,5,0,"MVP officielle (communication European Aquatics)","5 buts vs Croatie; 2 en demi; actions clés en finale","u20_mvp"),
    ("u20-europe","Netherlands","NED","Pien Gorter","Field player",9,"PRIORITÉ B",None,7,0,"","6 buts vs France; 7 en quart vs Grèce","u20_qf"),
    ("u20-europe","Croatia","CRO","Jelena Butic","Field player",8,"À SUIVRE",None,6,0,"","6 buts dans le match pour la 7e place","u20_final"),
    ("u20-europe","Spain","ESP","Martina Claveria","Field player",7,"À SUIVRE",None,5,0,"","5 buts en quart vs Grande-Bretagne","u20_qf"),
    ("u20-europe","Greece","GRE","Aspasia Fouraki","Field player",6,"À SUIVRE",None,4,0,"","4 buts contre le Portugal en crossover","u20_cross"),
    ("u20-europe","Italy","ITA","Beatrice Cassara","Captain / centre",6,"À SUIVRE",None,3,0,"","3 buts en quart vs Croatie; hat-trick en demi vs Hongrie","u20_sf"),
    ("u20-europe","Spain","ESP","Carlota Penalver","Field player",6,"À SUIVRE",None,3,0,"","3 buts en demi; plusieurs extras convertis en finale","u20_sf"),
    ("u20-europe","Hungary","HUN","Dominika Kardos","Field player",6,"À SUIVRE",None,3,0,"","3 buts en demi; 1 but + 2 tirs au but en finale","u20_sf"),
    ("u20-europe","Germany","GER","Nele Politze","Field player",6,"À SUIVRE",None,4,0,"","4 buts contre Türkiye dans le match pour la 13e place","u20_final"),
    ("u20-europe","Hungary","HUN","Panna Tiba","Field player",6,"À SUIVRE",None,3,0,"","3 buts en quart; 3 buts d'action au Q3 de la finale + 3 tirs au but","u20_final"),
    ("u20-europe","Spain","ESP","Queralt Anton","Senior international / field player",6,"À SUIVRE",None,2,0,"","Buts importants en demi/finale; dernier tir du shootout","u20_final"),
    ("u20-europe","Greece","GRE","Ariadni Karampetsou","Field player",5,"PROFIL",None,2,0,"","Buts importants contre Espagne et Pays-Bas","u20_qf"),
    ("u20-europe","Czechia","CZE","Lucie Bakalova","Field player",5,"PROFIL",None,5,0,"","5 buts contre l'Irlande","u20_d2"),
    ("u20-europe","Italy","ITA","Malika Bovo","Field player",5,"PROFIL",None,2,0,"","But difficile en demi; contributions répétées","u20_sf"),
    ("u20-europe","Italy","ITA","Eleonora Bianco","Field player",4,"PROFIL",None,1,0,"","But de 6 m remarquable en demi vs Hongrie","u20_sf"),
    ("u20-europe","Hungary","HUN","Eszter Varro","Centre",4,"PROFIL",None,2,0,"","Buts au centre et backhand important en quart","u20_qf"),
    ("u20-europe","Italy","ITA","Lara Bianco","Field player",4,"PROFIL",None,2,0,"","But important en demi et contributions régulières","u20_sf"),
    ("u20-europe","Hungary","HUN","Luca Torma","Goalkeeper",4,"PROFIL",None,0,2,"","Deux arrêts décisifs aux 5e et 9e tours du shootout de la finale","u20_final"),
    ("u20-europe","Spain","ESP","Lucia Rodriguez","Field player",4,"PROFIL",None,2,0,"","Deux buts d'action clés dans le retour espagnol en finale","u20_final"),
    ("u20-europe","Italy","ITA","Nausicaa Magaglio","Centre",4,"PROFIL",None,1,0,"","But au centre pour égaliser 7-7 dans le match pour le bronze","u20_final"),
    ("u20-europe","Hungary","HUN","Zoe Lendvay","Field player",4,"PROFIL",None,2,0,"","Deux buts importants dans le retournement du quart","u20_qf"),
    ("u20-europe","Hungary","HUN","Laura Kardos","Field player",2,"PROFIL",None,2,0,"","2 buts contre la Croatie","u20_d2"),
]


def _status_for(level):
    return {"PRIORITÉ A":"eu_priority_a","PRIORITÉ B":"eu_priority_b","À SUIVRE":"eu_watch","PROFIL":"eu_profile"}.get(level,"eu_profile")


def _player_note(total, peak_goals, peak_saves, distinction, performance, score, level):
    bits = [
        f"Indice scouting {score}/15 — {level}.",
        "Éligibilité UE: représente un État membre de l’Union européenne; aucun passeport supplémentaire n’est déduit.",
    ]
    if distinction:
        bits.append(f"Distinction: {distinction}.")
    if total is not None:
        bits.append(f"Total connu à date: {total}.")
    if peak_goals:
        bits.append(f"Pic buts/match: {peak_goals}.")
    if peak_saves:
        bits.append(f"Pic arrêts/match: {peak_saves}.")
    if performance:
        bits.append(f"Référence: {performance}.")
    return " ".join(bits)


def seed_eu_youth_2026(db):
    grouped = defaultdict(list)
    for row in PROSPECT_ROWS:
        grouped[(row[0], row[1], row[2])].append(row)

    for (competition_key, country, nationality), players in grouped.items():
        cfg = COMPETITIONS[competition_key]
        slug = country.lower().replace(" ", "-")
        external_key = f"eu-youth-2026-{competition_key}-{slug}"
        top_score = max(p[5] for p in players)
        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == external_key))
        if not team:
            team = ScoutingTeam(external_key=external_key)
            db.add(team)
            db.flush()

        team.name = f"{country} — Women {cfg['age']} · EU Scout 2026"
        team.team_type = "national_team"
        team.category = "Women"
        team.age_group = cfg["age"]
        team.country = country
        team.competition = cfg["name"]
        team.season_label = "Summer 2026"
        team.roster_status = cfg["status"]
        team.source_url = SOURCES[cfg["source"]]
        team.source_note = (
            f"EU-eligible youth scouting shortlist · {len(players)} profils · meilleur indice {top_score}/15. "
            f"{cfg['data']}. Filtre conservateur: sélection d’un État membre de l’UE; aucune double nationalité supposée."
        )
        team.priority = 85 + top_score

        existing = {p.name: p for p in db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.scouting_team_id == team.id)).all()}
        for row in players:
            _, _, _, name, role, score, level, total, peak_goals, peak_saves, distinction, performance, source_key = row
            player = existing.get(name)
            if not player:
                player = ScoutingPlayer(scouting_team_id=team.id, name=name)
                db.add(player)
            player.cap_number = None
            player.birth_year = None
            player.nationality = nationality
            player.role = f"{role} · {level} · {score}/15"
            player.source_season = "Summer 2026"
            player.source_url = SOURCES[source_key]
            player.source_quality = "official_tournament_report"
            player.current_status = _status_for(level)
            player.note = _player_note(total, peak_goals, peak_saves, distinction, performance, score, level)

    db.commit()


def install_scouting_seed_patch():
    """Wrap the existing seed so the shortlist is loaded automatically."""
    import services.scouting_data as base
    if getattr(base.seed_scouting, "_eu_youth_2026_patch", False):
        return
    original_seed = base.seed_scouting

    def seed_with_eu_youth(db):
        original_seed(db)
        seed_eu_youth_2026(db)

    seed_with_eu_youth._eu_youth_2026_patch = True
    base.seed_scouting = seed_with_eu_youth
