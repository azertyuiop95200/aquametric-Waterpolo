from sqlalchemy import select

from db import SessionLocal
from models import MatchLibraryItem, PlayerIntelligenceProfile, PlayerMatchMetric
from services.public_match_ratings import public_profile_evaluations

TEAMS = {
    "Lille UC Métropole Water-Polo",
    "Union St-Bruno Bordeaux",
    "Olympic Nice Natation",
    "Grand Nancy Aquatique Club",
    "Toulon Waterpolo",
    "Taverny Sports Nautiques 95",
    "Sporting Club des Nageurs de Choisy le Roi",
}


def _profile(db, name):
    row = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == name))
    assert row is not None, name
    return row


def _goal_total(db, name):
    profile = _profile(db, name)
    rows = db.scalars(select(PlayerMatchMetric).where(
        PlayerMatchMetric.profile_id == profile.id,
        PlayerMatchMetric.metric == "goals",
        PlayerMatchMetric.library_match_id.is_not(None),
    )).all()
    return int(sum(r.value or 0 for r in rows))


def test_official_elite_corpus_covers_every_seeded_french_team():
    db = SessionLocal()
    try:
        rows = db.scalars(select(MatchLibraryItem).where(
            MatchLibraryItem.external_key.like("FFN-ELITEF-2526-%")
        )).all()
        assert len(rows) >= 26
        seen = set()
        for row in rows:
            if row.team_a in TEAMS:
                seen.add(row.team_a)
            if row.team_b in TEAMS:
                seen.add(row.team_b)
        assert seen == TEAMS
    finally:
        db.close()


def test_major_scorers_from_each_team_have_multi_match_official_goal_evidence():
    db = SessionLocal()
    try:
        expected_minimums = {
            "Cecilia Nardini": 44,
            "Elizabeth Grace Estelle Birch": 33,
            "Kahena Benlekbir": 30,
            "Caroline Christl": 21,
            "Valentine Heurtaux": 19,
            "Jade Boughrara": 23,
            "Annaelle Picard": 9,
        }
        for name, minimum in expected_minimums.items():
            assert _goal_total(db, name) >= minimum, name
    finally:
        db.close()


def test_scorer_completeness_is_applied_per_team_not_per_match():
    db = SessionLocal()
    try:
        toulon = _profile(db, "Clémentine Valverde")
        bordeaux = _profile(db, "Elizabeth Grace Estelle Birch")
        toulon_rows = public_profile_evaluations(db, toulon, role=toulon.role)["matches"]
        bordeaux_rows = public_profile_evaluations(db, bordeaux, role=bordeaux.role)["matches"]
        key = "FFN-ELITEF-2526-TOULON-BORDEAUX-14-15"
        t = next(r for r in toulon_rows if r["match"].external_key == key)
        b = next(r for r in bordeaux_rows if r["match"].external_key == key)
        assert t["scorer_list_complete"] is True
        assert b["scorer_list_complete"] is False
        assert t["confidence_score"] > b["confidence_score"]
    finally:
        db.close()


def test_goals_only_rule_remains_strict_for_every_team():
    db = SessionLocal()
    try:
        birch = _profile(db, "Elizabeth Grace Estelle Birch")
        rows = public_profile_evaluations(db, birch, role=birch.role)["matches"]
        sample = next(r for r in rows if r["match"].external_key == "FFN-ELITEF-2526-BORDEAUX-TAVERNY-26-12")
        assert sample["goals"] == 8
        assert sample["dimensions"]["attack"] is not None
        assert sample["dimensions"]["impact"] is not None
        for dimension in ("defence", "decision", "tactics", "transition", "discipline", "technique"):
            assert sample["dimensions"][dimension] is None
        assert sample["coverage"] == 0.25
    finally:
        db.close()
