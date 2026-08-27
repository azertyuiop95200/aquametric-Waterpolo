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
