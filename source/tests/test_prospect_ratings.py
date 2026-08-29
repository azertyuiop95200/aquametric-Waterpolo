from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db import Base
from models import PlayerIntelligenceProfile, ScoutingPlayer
from services.prospect_ratings import build_prospect_evaluation, stars_for_score
from services.scouting_eu_2026_runtime import seed_eu_youth_2026_safe


def test_star_scale_keeps_half_stars():
    assert stars_for_score(91) == 5.0
    assert stars_for_score(87) == 4.5
    assert stars_for_score(82) == 4.0
    assert stars_for_score(77) == 3.5
    assert stars_for_score(72) == 3.0


def test_prospect_rating_uses_final_u18_context_without_inventing_video(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'prospects.db'}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        seed_eu_youth_2026_safe(db)
        profile = PlayerIntelligenceProfile(
            canonical_name="Kincso Kenez",
            nationality="HUN",
            role="Field player",
            current_national_team="Hungary — Women U18",
            roster_status="official_tournament_evidence",
            roster_season="2026",
            confidence_score=.90,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        rows = db.scalars(select(ScoutingPlayer).where(ScoutingPlayer.name == "Kincso Kenez")).all()
        evaluation = build_prospect_evaluation(db, profile, rows, user_id=999999)

        assert evaluation is not None
        assert evaluation["overall"] >= 70
        assert evaluation["stars"] >= 3.0
        assert evaluation["context_components"]["recognition"] >= 90
        assert "U18" in evaluation["age_groups"]
        assert evaluation["official_video_sources"]
        assert evaluation["video_analyzed_matches"] == 0
        assert evaluation["dimensions"]["attack"] is not None
        assert evaluation["physical"] is None
