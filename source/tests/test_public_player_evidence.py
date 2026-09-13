import uuid

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from sqlalchemy import select

from db import SessionLocal
from main import app
from models import MatchLibraryItem, PlayerIntelligenceProfile, PlayerMatchMetric
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


def test_granville_lineups_expand_sample_without_fabricating_player_rating():
    db = SessionLocal()
    try:
        morgane = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == "Morgane Le Berre"))
        rumina = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == "Rumina Edgerton"))
        assert morgane is not None and rumina is not None
        morgane_evidence = public_profile_evaluations(db, morgane, role=morgane.role)
        rumina_evidence = public_profile_evaluations(db, rumina, role=rumina.role)
        granville_morgane = [r for r in morgane_evidence["matches"] if r["match"].external_key.startswith("FFN-N1F-2526-")]
        granville_rumina = [r for r in rumina_evidence["matches"] if r["match"].external_key.startswith("FFN-N1F-2526-")]
        assert len(granville_morgane) == 12
        assert len(granville_rumina) == 11
        assert all(r["appearance_verified"] for r in granville_morgane)
        assert all(r["overall"] is None for r in granville_morgane)
        assert all(r["coverage"] == 0.0 for r in granville_morgane)
        assert all(r["confidence_label"] == "PRESENCE" for r in granville_morgane)
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
    assert "Match-by-match evidence and evaluation" in text
    assert len(soup.select(".public-match-card")) >= 12
    assert "7 goals" in text
    assert "dimension coverage" in text
    assert "Not rated from this source" in text
    assert "Published scorer list is incomplete" in text


def test_granville_dossier_shows_presence_only_precision_message():
    client = TestClient(app)
    _register(client)
    db = SessionLocal()
    try:
        profile = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == "Rumina Edgerton"))
        assert profile is not None
        profile_id = profile.id
    finally:
        db.close()
    response = client.get(f"/profiles/players/{profile_id}")
    assert response.status_code == 200
    text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
    assert "11 official matches documented" in text
    assert "No individual rating from this match sheet" in text
    assert "Presence verified; goals, assists, shots, saves, exclusions and tactical actions remain unknown" in text
