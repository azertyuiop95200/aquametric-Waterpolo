import uuid

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from sqlalchemy import select

from db import SessionLocal
from main import app
from models import MatchLibraryItem, PlayerIntelligenceProfile, PlayerMatchMetric, User
from services.public_match_ratings import public_profile_evaluations


def _register(client: TestClient):
    email = f"public-evidence-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "Public Evidence Audit", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return email


def test_cecilia_nardini_has_twelve_official_lille_match_records_and_44_goals():
    db = SessionLocal()
    try:
        profile = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == "Cecilia Nardini"))
        assert profile is not None
        rows = db.scalars(
            select(PlayerMatchMetric).where(
                PlayerMatchMetric.profile_id == profile.id,
                PlayerMatchMetric.metric == "goals",
                PlayerMatchMetric.library_match_id.is_not(None),
            )
        ).all()
        ffn_rows = []
        for row in rows:
            match = db.get(MatchLibraryItem, row.library_match_id)
            if match and match.external_key.startswith("FFN-") and match.season == "2025-2026":
                ffn_rows.append(row)
        assert len(ffn_rows) == 12
        assert sum(int(row.value or 0) for row in ffn_rows) == 44
    finally:
        db.close()


def test_goals_only_public_source_rates_attack_and_impact_but_not_unpublished_dimensions():
    db = SessionLocal()
    try:
        profile = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == "Cecilia Nardini"))
        assert profile is not None
        evidence = public_profile_evaluations(db, profile, role=profile.role)
        target = next(row for row in evidence["matches"] if row["match"].external_key == "FFN-ELITEF-2526-FINAL-LILLE-NANCY-17-10")
        assert target["goals"] == 7
        assert target["overall"] is not None
        assert target["dimensions"]["attack"] is not None
        assert target["dimensions"]["impact"] is not None
        for dimension in ("defence", "decision", "tactics", "transition", "discipline", "technique"):
            assert target["dimensions"][dimension] is None
        assert target["coverage"] == 0.25
        assert target["confidence_score"] < 0.60
        assert target["scorer_list_complete"] is True
    finally:
        db.close()


def test_incomplete_official_scorer_list_reduces_confidence_and_stays_labelled():
    db = SessionLocal()
    try:
        profile = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == "Cecilia Nardini"))
        evidence = public_profile_evaluations(db, profile, role=profile.role)
        incomplete = next(row for row in evidence["matches"] if row["match"].external_key == "FFN-ELITEF-2526-LILLE-NICE-20-11")
        complete = next(row for row in evidence["matches"] if row["match"].external_key == "FFN-ELITEF-2526-FINAL-LILLE-NANCY-17-10")
        assert incomplete["scorer_list_complete"] is False
        assert incomplete["confidence_score"] < complete["confidence_score"]
    finally:
        db.close()


def test_player_dossier_renders_public_match_evaluation_with_precision_labels():
    client = TestClient(app)
    _register(client)
    db = SessionLocal()
    try:
        profile = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == "Cecilia Nardini"))
        assert profile is not None
        profile_id = profile.id
    finally:
        db.close()

    response = client.get(f"/profiles/players/{profile_id}")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    assert "Match-by-match evaluation from published statistics" in text
    assert len(soup.select(".public-match-card")) >= 12
    assert "7 goals" in text
    assert "dimension coverage" in text
    assert "Not rated from this source" in text
    assert "Published scorer list is incomplete" in text
