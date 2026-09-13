"""Deep scouting review layer for priority EU youth prospects.

This layer converts detailed official match reports into low-weight tactical
signals. It deliberately does NOT pretend that a linked full-match video has
been frame-tagged. Video links are stored as review material; only existing
AquaMetric PlayerMatchEvaluation rows count as actual video/tagged evidence.
"""

DIMENSIONS = ("attack", "defence", "decision", "tactics", "transition", "discipline", "technique", "impact")

U16_FINAL = "https://www.worldaquatics.com/news/4551499/greece-denies-spain-u16-womens-golden-double"
U16_SEMI = "https://www.worldaquatics.com/news/4550495/champion-spain-rattles-sabre-ahead-of-gold-medal-clash-with-greece"
U16_GROUP = "https://www.worldaquatics.com/news/4548905/spain-shocked-by-greece-en-route-to-u16-womens-quarterfinals"
U18_D2 = "https://www.worldaquatics.com/news/4561146/spain-and-greece-make-huge-statements"
U18_D3 = "https://www.worldaquatics.com/news/4561792/greece-and-spain-emerge-top-in-u18-major-groups"
U18_SEMI = "https://www.worldaquatics.com/news/4564707/usa-spain-final"
U18_FINAL = "https://www.worldaquatics.com/news/4565141/all-conquering-australia-upsets-spain-with-first-u18-crown"
U20_QF = "https://events.europeanaquatics.org/ewpc-2026-u20/oeiras-2026-hungary-italy-spain-and-netherlands-surge-through-to-semifinals/"
U20_SF = "https://events.europeanaquatics.org/ewpc-2026-u20/oeiras-2026-hungary-and-spain-set-for-another-gold-medal-showdown-at-womens-u20-european-water-polo-championships/"
U20_D3 = "https://events.europeanaquatics.org/ewpc-2026-u20/oeiras-2026-italy-edge-greece-to-reach-quarterfinals-as-dramatic-group-stage-concludes/"

V_U16_FINAL = "https://www.worldaquatics.com/videos/4539420/gold-medal-match-world-aquatics-womens-u16-water-polo-championships-2026"
V_U16_HUN_GRE = "https://www.worldaquatics.com/videos/4539422/hun-vs-gre-semi-final-2-day-6-world-aquatics-womens-u16-water-polo-championships-2026"
V_U18_FINAL = "https://www.worldaquatics.com/videos/4557235/gold-medal-match-world-aquatics-womens-u18-water-polo-championships-2026"
V_U18_ESP_HUN = "https://www.worldaquatics.com/videos/4557224/semi-final-2-day-7-world-aquatics-womens-u18-water-polo-championships-2026"
V_U18_USA_HUN = "https://www.worldaquatics.com/videos/4557231/bronze-medal-match-world-aquatics-womens-u18-water-polo-championships-2026"


def _e(title, report, observations, video=""):
    return {"title": title, "report_url": report, "video_url": video, "observations": observations}


REVIEWS = {
    "Afroditi Bitsakou": {
        "summary": "Capitaine à fort impact, capable de produire sur extra, penalty et tir extérieur. Son tournoi U16 montre surtout une capacité à prendre le contrôle des grands matches sans dépendre d'un volume de tirs maximal.",
        "strengths": ["Impact élevé dans les matches à élimination", "Variété de finition: extra, penalty, tir du haut", "Leadership et progression U16→U18", "Bonne capacité à maintenir la production au sein d'une attaque très partagée"],
        "risks": ["Deux penalties manqués en finale U16: la gestion de certaines situations de forte pression reste à suivre", "La défense individuelle doit encore être confirmée par tagging vidéo joueur par joueur"],
        "dimensions": {"attack": 88, "decision": 82, "tactics": 82, "technique": 84, "impact": 92, "discipline": 76},
        "evidence": [
            _e("U16 demi-finale vs Hongrie", U16_SEMI, "Buts consécutifs du haut, penalty, présence dans le run qui fait basculer la demi-finale.", V_U16_HUN_GRE),
            _e("U16 finale vs Espagne", U16_FINAL, "Ouvre sur extra, ajoute un penalty; participe à l'écart 8-3 de la première mi-temps. MVP du tournoi.", V_U16_FINAL),
            _e("U18 vs Italie", U18_D2, "Trois buts dans une victoire où la Grèce domine extra, steals et efficacité globale."),
        ],
    },
    "Julia Teodoro": {
        "summary": "Gardienne de référence du Mondial U16. Son meilleur signal n'est pas le volume brut sur une seule rencontre mais la capacité à maintenir l'Espagne dans des matches où l'attaque est moins efficace.",
        "strengths": ["10 arrêts contre la Grèce en phase de groupes", "Meilleure gardienne officielle et All-Star", "Valeur élevée dans des matches à faible marge"],
        "risks": ["Les pourcentages d'arrêts par zone et sous pression ne sont pas disponibles dans les rapports", "Besoin de tagging vidéo pour sorties, relance et lecture du 5v6"],
        "dimensions": {"defence": 91, "decision": 82, "technique": 87, "impact": 88, "tactics": 80},
        "evidence": [_e("U16 Espagne-Grèce phase de groupes", U16_GROUP, "10 arrêts, meilleure joueuse espagnole du match."), _e("U16 finale vs Grèce", U16_FINAL, "Gardienne de l'équipe finaliste face à une Grèce à 46% au tir.", V_U16_FINAL)],
    },
    "Mandula Mihok": {
        "summary": "Centre très complète pour son âge: finition dos au but, backhand avec feinte, jeu au poteau, rebond offensif et capacité à voler un ballon au centre. Son profil est plus riche que son simple total de buts.",
        "strengths": ["Technique de centre avancée", "Capacité à marquer sur plusieurs types de réception", "Production U16 et U18", "Impact dans les fins de match"],
        "risks": ["Exclusion très coûteuse à 22 secondes de la fin du match pour le bronze U18", "Discipline et gestion du contact à contrôler dans les fins de match"],
        "dimensions": {"attack": 86, "decision": 78, "tactics": 83, "technique": 90, "impact": 85, "discipline": 61, "defence": 74},
        "evidence": [
            _e("U16 demi-finale vs Grèce", U16_SEMI, "Marque sur extra; reste une menace intérieure malgré la domination grecque.", V_U16_HUN_GRE),
            _e("U16 bronze vs Pays-Bas", U16_FINAL, "Quatre buts, dont des finitions au centre; All-Star du tournoi."),
            _e("U18 Hongrie-Grèce", U18_D3, "Rebond offensif, deux buts au poteau sur cross-pass puis interception au centre conclue par un but."),
            _e("U18 bronze vs USA", U18_FINAL, "Backhand de centre avec feinte; exclusion tardive après contact avec la gardienne.", V_U18_USA_HUN),
        ],
    },
    "Kincso Kenez": {
        "summary": "Capitaine hongroise capable de scorer du périmètre, sur 6 m, penalty et extra. Son profil combine volume, responsabilité et répétition contre des adversaires du top 8.",
        "strengths": ["Variété de tirs", "Responsabilité sur penalties", "Production régulière dans les matches serrés", "All-Star U18"],
        "risks": ["Un penalty arrêté contre la Grèce", "La création pour les autres et la défense hors ballon restent sous-documentées"],
        "dimensions": {"attack": 86, "decision": 83, "tactics": 81, "technique": 86, "impact": 89, "discipline": 78},
        "evidence": [
            _e("U18 vs Pays-Bas", U18_D2, "Deux buts dans le premier quart, penalty plus tard; quatre buts au total dans un match gagné 13-10."),
            _e("U18 vs Grèce", U18_D3, "Penalty arrêté puis réponse immédiate sur extra; continue à produire malgré le déficit."),
            _e("U18 bronze vs USA", U18_FINAL, "But de 6 m et penalty; deux buts dans une défaite d'un but. Termine All-Star.", V_U18_USA_HUN),
        ],
    },
    "Nefeli Krassa": {
        "summary": "Capitaine grecque polyvalente dans les zones de finition: tir profond à droite, lob et transition. Son total de 15 buts est soutenu par une présence régulière dans les séquences qui lancent les runs grecs.",
        "strengths": ["Finition multi-zones", "Transition et contre-attaque", "Leadership", "All-Star U18"],
        "risks": ["Les responsabilités défensives individuelles sont difficiles à isoler à partir des seules statistiques équipe", "Pas encore de tracking vidéo attribué dans AquaMetric"],
        "dimensions": {"attack": 84, "decision": 82, "transition": 88, "tactics": 82, "technique": 83, "impact": 88},
        "evidence": [
            _e("U18 Hongrie-Grèce", U18_D3, "Tir profond validé VAR puis lob; contribue au break grec avant la mi-temps."),
            _e("U18 classement vs Pays-Bas", U18_SEMI, "Trois buts, dont un en contre, dans une séquence où la Grèce accélère fortement."),
            _e("U18 match pour la 5e place", U18_FINAL, "Double scoreuse du premier quart, 15 buts au tournoi et All-Star."),
        ],
    },
    "Marjolein de Gier": {
        "summary": "Menace offensive très adaptable: réception au centre, tirs du haut et production élevée jusqu'au dernier match. Elle garde de l'impact même lorsque les Pays-Bas subissent collectivement.",
        "strengths": ["23 buts au Mondial U18", "Peut marquer du centre et du périmètre", "Réponse immédiate après les temps faibles", "All-Star U18"],
        "risks": ["La création, les passes décisives et la défense ne sont pas suffisamment publiées", "Profil à vérifier vidéo pour distinguer volume de tir et vraie création d'avantage"],
        "dimensions": {"attack": 91, "decision": 79, "technique": 86, "impact": 88, "tactics": 77},
        "evidence": [
            _e("U18 vs Hongrie", U18_D2, "Hat-trick et maintien du contact dans un match où les Pays-Bas reviennent plusieurs fois."),
            _e("U18 vs Grèce", U18_SEMI, "Réception au centre puis tir du haut; reste productive dans une lourde défaite."),
            _e("U18 7e place vs Chine", U18_FINAL, "Six buts, 23 au tournoi; plusieurs finitions depuis le haut."),
        ],
    },
    "Queralt Anton": {
        "summary": "Profil senior précoce, capitaine et joueuse de responsabilité. Elle peut finir sur extra, du haut et dans une situation improvisée proche du but, ce qui suggère une bonne lecture des secondes balles.",
        "strengths": ["Responsabilité dans les grands matches", "Variété de finition", "Expérience senior", "Capacité à produire sous pression"],
        "risks": ["La finale U18 montre une Espagne à seulement 18,5% au tir: les choix de tir collectifs sous pression doivent être revus en vidéo", "Besoin de données individuelles sur pertes de balle et création"],
        "dimensions": {"attack": 84, "decision": 85, "tactics": 85, "technique": 85, "impact": 88, "discipline": 80},
        "evidence": [
            _e("U18 vs USA", U18_D2, "Buzzer-beater extérieur qui ferme le troisième quart lors du renversement espagnol."),
            _e("U18 finale vs Australie", U18_FINAL, "Scoop sur ballon libre à cinq mètres et tir puissant du haut sur extra; deux buts.", V_U18_FINAL),
            _e("U20 demi-finale vs Pays-Bas", U20_SF, "But d'action puis conversion en 6v5 dans la séquence qui tue le match."),
        ],
    },
    "Ona Jurado": {
        "summary": "Scorer régulière au U18 avec bonne présence sur extra et capacité à répondre lorsque l'Espagne traverse une période difficile.",
        "strengths": ["Régularité sur plusieurs matches", "Finition sur extra", "Capacité à casser une série adverse"],
        "risks": ["Moins de données sur création et défense individuelle", "À distinguer en vidéo: tirs créés par elle-même vs tirs servis par la structure espagnole"],
        "dimensions": {"attack": 84, "decision": 78, "tactics": 80, "technique": 82, "impact": 82},
        "evidence": [_e("U18 vs USA", U18_D2, "Deux buts rapprochés pour garder l'Espagne au contact avant le renversement."), _e("U18 finale vs Australie", U18_FINAL, "Deux buts, dont une finition du haut sur extra.", V_U18_FINAL)],
    },
    "Malika Bovo": {
        "summary": "Volume offensif très robuste sur l'ensemble du Mondial U18, y compris contre la Grèce et dans le dernier match. Elle produit même quand l'Italie ne contrôle pas le match.",
        "strengths": ["20 buts au tournoi U18", "Production contre plusieurs niveaux d'opposition", "Finition sur extra et action", "Résilience offensive dans les défaites"],
        "risks": ["Le ratio tirs/buts individuel n'est pas publié", "Défense et discipline encore sous-documentées"],
        "dimensions": {"attack": 89, "decision": 78, "technique": 84, "impact": 84, "tactics": 76},
        "evidence": [_e("U18 Grèce-Italie", U18_D2, "Cinq buts, dont extra et action, face à une défense grecque dominante."), _e("U18 Italie-Croatie", U18_FINAL, "Quatre buts, termine meilleure marqueuse italienne avec 20.")],
    },
    "Neli Jankovic": {
        "summary": "Internationale senior déjà capable de varier les zones de tir: 6 m, extra, penalty et tirs extérieurs. Son profil garde de la production même quand la Croatie subit fortement.",
        "strengths": ["Expérience senior", "Variété de tir", "Capacité à produire dans les défaites", "Responsabilité offensive"],
        "risks": ["Une partie de la production vient des penalties/extra: la création en jeu placé doit être séparée en vidéo", "Croatie concède de lourdes séquences défensives; responsabilité individuelle à isoler"],
        "dimensions": {"attack": 87, "decision": 81, "technique": 86, "impact": 84, "tactics": 79},
        "evidence": [_e("U18 Croatie-Chine", U18_D2, "6 m, extra et penalty; cinq buts."), _e("U18 Croatie-Nouvelle-Zélande", U18_SEMI, "Finition sur cross-pass et trois buts."), _e("U18 Croatie-Italie", U18_FINAL, "Cinq buts, dont deux rockets extérieurs sur extra; 16 au tournoi.")],
    },
    "Lara Srhoj": {
        "summary": "Joueuse dynamique capable de battre une défenseuse depuis une position très large, d'attaquer le but et de produire sur penalty/extra. Profil intéressant de création individuelle.",
        "strengths": ["Un-contre-un et attaque du but", "Polyvalence action/extra/penalty", "17 buts au tournoi", "Expérience senior"],
        "risks": ["Dépendance possible aux penalties dans certains matches", "Défense et pertes de balle à documenter"],
        "dimensions": {"attack": 88, "decision": 80, "transition": 82, "technique": 86, "impact": 83},
        "evidence": [_e("U18 Croatie-Chine", U18_D2, "Action, extra et penalty; trois buts."), _e("U18 Croatie-Nouvelle-Zélande", U18_SEMI, "Tourne sa défenseuse depuis large droite et attaque le but; cinq buts."), _e("U18 Croatie-Italie", U18_FINAL, "Hat-trick dans le dernier quart; 17 buts au tournoi.")],
    },
    "Pien Gorter": {
        "summary": "Le quart de finale contre la Grèce montre un profil de takeover: penalty, tirs d'action, réponse immédiate et conduite de contre-attaque. Elle transforme un 6-8 en victoire néerlandaise.",
        "strengths": ["Création de momentum", "Transition", "Tirs sous pression", "Capacité à enchaîner plusieurs possessions décisives"],
        "risks": ["Carton rouge en demi-finale contre l'Espagne: discipline à examiner", "Il faut vérifier en vidéo l'apport défensif et la qualité de sélection des tirs sur un échantillon plus large"],
        "dimensions": {"attack": 92, "decision": 84, "transition": 91, "tactics": 82, "technique": 88, "impact": 93, "discipline": 57},
        "evidence": [_e("U20 quart vs Grèce", U20_QF, "Sept buts; penalty, action, conduite de contre et quatre buts consécutifs dans la phase décisive."), _e("U20 demi vs Espagne", U20_SF, "Expulsée sur carton rouge alors que les Pays-Bas sont déjà sous forte pression.")],
    },
    "Kata Hajdu": {
        "summary": "MVP U20 et joueuse de responsabilité. Les rapports la placent régulièrement dans les séquences importantes plutôt que dans du simple scoring de volume.",
        "strengths": ["MVP du tournoi", "Impact en demi-finale", "Responsabilité dans les grands matches", "Expérience senior récente"],
        "risks": ["Les rapports U20 publient moins de statistiques individuelles complètes que World Aquatics", "Besoin de séquences vidéo taggées pour séparer création, tir et travail défensif"],
        "dimensions": {"attack": 87, "decision": 86, "tactics": 86, "technique": 84, "impact": 93, "discipline": 80},
        "evidence": [_e("U20 demi-finale vs Italie", U20_SF, "Deux buts dans une demi-finale serrée où la Hongrie use progressivement l'Italie."), _e("U20 tournoi complet", U20_SF, "MVP du championnat, signal fort de valeur globale au-delà du total de buts.")],
    },
    "Panna Tiba": {
        "summary": "Très forte dans les séquences de bascule: tirs du périmètre, production dans le troisième quart de la finale et responsabilités au shootout.",
        "strengths": ["Impact en phase finale", "Tir du périmètre", "Gestion des moments de pression", "Répétition quart/finale"],
        "risks": ["Peu de données individuelles défensives publiées", "À confirmer sur vidéo pour la prise de décision hors scoring"],
        "dimensions": {"attack": 86, "decision": 85, "tactics": 82, "technique": 86, "impact": 91},
        "evidence": [_e("U20 quart vs NAB", U20_QF, "Trois buts dans le comeback hongrois."), _e("U20 finale", U20_SF, "Production de périmètre et responsabilités dans les séquences décisives du tournoi.")],
    },
    "Beatrice Cassara": {
        "summary": "Centre/capitaine qui donne à l'Italie une vraie menace intérieure dans les matches à élimination. Son apport est visible dans des matches où l'Italie doit jouer sous pression.",
        "strengths": ["Jeu de centre", "Leadership", "Production en quart et demi", "Capacité à marquer dans des matches serrés"],
        "risks": ["Besoin de quantifier exclusions gagnées et pertes au centre", "Défense individuelle non publiée"],
        "dimensions": {"attack": 84, "decision": 79, "tactics": 84, "technique": 86, "impact": 84},
        "evidence": [_e("U20 quart vs Croatie", U20_QF, "Trois buts et présence au centre dans une victoire obtenue après un départ difficile."), _e("U20 demi vs Hongrie", U20_SF, "Hat-trick depuis le centre et forte présence dans un match perdu seulement 10-8.")],
    },
}


def star_text(stars):
    full = int(stars)
    half = stars - full >= .5
    return "★" * full + ("½" if half else "") + "☆" * (5 - full - (1 if half else 0))


def stars_for(score):
    if score is None: return 0.0
    if score >= 90: return 5.0
    if score >= 85: return 4.5
    if score >= 80: return 4.0
    if score >= 75: return 3.5
    if score >= 70: return 3.0
    if score >= 65: return 2.5
    if score >= 60: return 2.0
    if score >= 55: return 1.5
    return 1.0


def enrich_with_deep_review(evaluation):
    """Blend official play-by-play evidence conservatively into an evaluation.

    This is deliberately low weight (15%). It is richer than goals-only context,
    but it is not a substitute for frame-tagged video evidence.
    """
    review = REVIEWS.get(evaluation.get("name"))
    if not review:
        evaluation["deep_review"] = None
        return evaluation

    dims = evaluation.setdefault("dimensions", {})
    sources = evaluation.setdefault("dimension_sources", {})
    for dim, signal in review["dimensions"].items():
        old = dims.get(dim)
        dims[dim] = round(signal if old is None else old * .85 + signal * .15, 1)
        sources.setdefault(dim, []).append("official play-by-play review")

    report_values = list(review["dimensions"].values())
    report_overall = round(sum(report_values) / len(report_values), 1) if report_values else None
    if report_overall is not None and evaluation.get("overall") is not None:
        evaluation["overall"] = round(evaluation["overall"] * .85 + report_overall * .15, 1)
        evaluation["stars"] = stars_for(evaluation["overall"])
        evaluation["star_text"] = star_text(evaluation["stars"])

    video_links = [e for e in review["evidence"] if e.get("video_url")]
    evaluation["deep_review"] = {
        **review,
        "report_overall": report_overall,
        "evidence_count": len(review["evidence"]),
        "linked_video_count": len(video_links),
        "video_status": "official videos linked; no frame-level score unless AquaMetric tagged evaluation exists",
    }
    evaluation["evidence_count"] = int(evaluation.get("evidence_count", 0)) + len(review["evidence"])
    return evaluation
