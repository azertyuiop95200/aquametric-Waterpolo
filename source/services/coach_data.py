from sqlalchemy import select
from intelligence_models import CoachIntelligenceProfile

# Coach records remain season-specific. A previous-season coach is never silently
# promoted into the current season without a new source.
COACH_SEEDS = [
    {
        "name": "Veronika Lapina",
        "team": "Granville Water Polo",
        "team_type": "club",
        "category": "Women Senior",
        "role": "Head coach — N1 Féminine",
        "season": "2025-2026",
        "status": "historical_club_official_pending_2026_27_confirmation",
        "source": "https://www.granvillewaterpolo.com/elite-f%C3%A9minine/",
        "tier": "club_official",
        "confidence": .98,
        "identity": "Granville's official 2025-26 page announced Veronika Lapina as coach of the women's N1 team. The 2026-27 senior assignment is not assumed until the club publishes it.",
        "note": "Performance scoring is intentionally unavailable until match-level coaching evidence is attached. Historical identity is confirmed; current-season continuity is pending.",
    },
    {
        "name": "Tristan Colaço",
        "team": "Union St-Bruno Bordeaux",
        "team_type": "club",
        "category": "Women Senior",
        "role": "Head coach — Elite Féminine",
        "season": "2026-2027 tracking",
        "status": "club_official_current_page_observed_pending_2026_27_match_sheet_confirmation",
        "source": "https://www.saint-bruno.org/water-polo/la-section/les-entraineurs",
        "tier": "club_official",
        "confidence": .90,
        "identity": "Union Saint-Bruno's official water-polo coach page identifies Tristan Colaço as coach of the Elite women's team and states that he has held the role since September 2023.",
        "note": "The club page is current public evidence, but AquaMetric still waits for 2026-27 match-sheet or season-specific confirmation before marking the assignment fully season-confirmed.",
    },
    {
        "name": "Thomas Michaeli",
        "team": "Taverny Sports Nautiques 95",
        "team_type": "club",
        "category": "Women Senior",
        "role": "Head coach — Elite Féminine",
        "season": "2024-2025",
        "status": "historical_club_official_pending_current_season_confirmation",
        "source": "https://haut-niveau.tsn95.fr/index.php/equipe-n1-feminine/",
        "tier": "club_official",
        "confidence": .98,
        "identity": "Taverny SN95's official Elite women page lists Thomas Michaeli in the sporting staff as coach for the displayed 2024-25 season.",
        "note": "This remains historical evidence only. AquaMetric does not carry the assignment into 2026-27 without newer club or federation evidence.",
    },
    {
        "name": "Lorène Derenty",
        "team": "France — Women Senior",
        "team_type": "national_team",
        "category": "Women Senior",
        "role": "Head coach / entraîneure",
        "season": "2026",
        "status": "federation_official_current",
        "source": "https://www.ffnatation.fr/sites/default/files/2026-01/DP%20FUNCHAL%202026_VF.pdf",
        "tier": "federation_official",
        "confidence": .99,
        "identity": "The FFN's official Funchal 2026 dossier lists Lorène Derenty in charge of the France women's senior team and states she has coached the national team since 2023.",
        "note": "Current national-team identity is federation-confirmed. Coaching performance remains unscored until match-level evidence is linked.",
    },
    {
        "name": "Stefania Giuliani",
        "team": "France — Women Senior",
        "team_type": "national_team",
        "category": "Women Senior",
        "role": "Assistant coach",
        "season": "2026",
        "status": "federation_official_current",
        "source": "https://www.ffnatation.fr/sites/default/files/2026-01/DP%20FUNCHAL%202026_VF.pdf",
        "tier": "federation_official",
        "confidence": .99,
        "identity": "The FFN's official Funchal 2026 dossier lists Stefania Giuliani in the France women's senior staff.",
        "note": "Current assistant-coach identity is federation-confirmed; no performance score is inferred from biography alone.",
    },
    {
        "name": "Jordi Valls",
        "team": "Spain — Women Senior",
        "team_type": "national_team",
        "category": "Women Senior",
        "role": "Head coach / seleccionador",
        "season": "2026",
        "status": "federation_official_current",
        "source": "https://rfen.es/noticia/convocatoria-oficial-de-espana-para-el-campeonato-de-europa-de-funchal-355013/",
        "tier": "federation_official",
        "confidence": .99,
        "identity": "RFEN's 2026 European Championship communication identifies Jordi Valls as the coach directing Spain's senior women's national team; July 2026 RFEN coverage confirms continuity toward the World Cup Super Final.",
        "note": "Current assignment is federation-confirmed. Historical results and staff roles are kept in the coach biography with their own sources.",
    },
    {
        "name": "Maurizio Mirarchi",
        "team": "Italy — Women Senior",
        "team_type": "national_team",
        "category": "Women Senior",
        "role": "Head coach / commissario tecnico",
        "season": "2026",
        "status": "federation_official_current",
        "source": "https://www.federnuoto.it/home/pallanuoto/news-pallanuoto/42888-world-cup-il-setterosa-riparte-da-rotterdam.html",
        "tier": "federation_official",
        "confidence": .99,
        "identity": "Federazione Italiana Nuoto announced Maurizio Mirarchi as the new senior women's national-team head coach in April 2026 and continued to list him as CT through the July World Cup campaign.",
        "note": "Current assignment is federation-confirmed. AquaMetric does not inherit results achieved before his appointment into his performance rating.",
    },
]


def seed_coaches(db):
    for seed in COACH_SEEDS:
        row = db.scalar(select(CoachIntelligenceProfile).where(
            CoachIntelligenceProfile.canonical_name == seed["name"],
            CoachIntelligenceProfile.team_name == seed["team"],
            CoachIntelligenceProfile.season == seed["season"],
        ))
        if not row:
            row = CoachIntelligenceProfile(
                canonical_name=seed["name"], team_name=seed["team"], team_type=seed["team_type"],
                category=seed["category"], role=seed["role"], season=seed["season"]
            )
            db.add(row)
        row.status = seed["status"]
        row.source_url = seed["source"]
        row.source_tier = seed["tier"]
        row.confidence_score = seed["confidence"]
        row.tactical_identity = seed["identity"]
        row.note = seed["note"]
    db.commit()
