import os
import uuid
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import User
from scorer_models import OfficialScorerStanding
from services.scorer_rankings import TRACKED_WOMEN_COMPETITIONS, season_window, build_scorer_groups

client = TestClient(app)


def _login():
    email = f"scorers-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "Scorer Test", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return email


def test_season_window_is_current_plus_three_archives():
    assert season_window(date(2026, 9, 3)) == ["2026-2027", "2025-2026", "2024-2025", "2023-2024"]
    assert season_window(date(2027, 5, 1)) == ["2026-2027", "2025-2026", "2024-2025", "2023-2024"]


def test_tracked_women_cover_france_n1_elite_and_followed_elites():
    pairs = {(row["country"], row["level"]) for row in TRACKED_WOMEN_COMPETITIONS}
    assert ("France", "Elite") in pairs
    assert ("France", "N1") in pairs
    for country in ("Espagne", "Italie", "Hongrie", "Allemagne", "Russie"):
        assert (country, "Elite") in pairs


def test_official_scorer_row_is_ranked_and_exposed_on_competitions_page():
    _login()
    season = season_window()[0]
    player = f"Buteuse Test {uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    try:
        db.add(OfficialScorerStanding(
            competition="Elite Féminine",
            season=season,
            category="Women",
            country="France",
            level="Elite",
            player_name=player,
            team_name="Club Test",
            goals=17,
            matches_played=8,
            goals_per_match=2.125,
            source_url="https://example.com/official-scorers",
            source_quality="official_federation",
            coverage_label="official_published",
        ))
        db.commit()
        payload = build_scorer_groups(db)
        france = next(group for group in payload["groups"] if group["competition"] == "Elite Féminine")
        current = next(block for block in france["seasons"] if block["season"] == season)
        assert current["coverage"] == "official"
        assert current["rows"][0]["player_name"] == player
        assert current["rows"][0]["position"] == 1
    finally:
        db.close()

    page = client.get("/competitions")
    assert page.status_code == 200
    assert "CLASSEMENT BUTEUSES" in page.text
    assert "France · Élite" in page.text
    assert "France · N1" in page.text
    assert "Saison en cours" in page.text
    assert "N-1" in page.text and "N-2" in page.text and "N-3" in page.text
    assert player in page.text
    assert "Classement buteuses" in page.text


def test_scorer_api_keeps_empty_competitions_visible_without_fake_totals():
    _login()
    response = client.get("/api/scorers")
    assert response.status_code == 200
    data = response.json()
    assert len(data["seasons"]) == 4
    n1 = next(group for group in data["groups"] if group["competition"] == "N1 Féminine")
    assert len(n1["seasons"]) == 4
    empty_or_real = n1["seasons"][0]
    assert empty_or_real["coverage"] in {"official", "partial", "awaiting"}
    if empty_or_real["coverage"] == "awaiting":
        assert empty_or_real["rows"] == []
