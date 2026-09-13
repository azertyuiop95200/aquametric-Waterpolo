import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from db import SessionLocal
from main import app
from models import ScoutingTeam
from services.scouting_player_resources import (
    _name_key,
    scouting_player_resources,
    scouting_team_resource_summary,
)


def _register(client):
    email = f"scouting-rich-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "Scouting Resource Test", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_name_linkage_normalizes_accents_and_punctuation():
    assert _name_key("Iva Rožić") == _name_key("Iva Rozic")
    assert _name_key("  ELENA-RUIZ ") == _name_key("Elena Ruiz")


def test_granville_scouting_resources_keep_lineups_separate_from_performance_stats():
    db = SessionLocal()
    try:
        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == "club-fr-granville-w-elite"))
        assert team is not None
        cards = scouting_player_resources(db, team.id)
        assert cards
        rumina = next(card for card in cards if card["name"] == "Rumina Edgerton")
        assert rumina["profile"] is not None
        assert rumina["documented_matches"] == 11
        assert rumina["performance_matches"] == 0
        assert rumina["metric_totals"]["saves"] == 0
        assert rumina["coverage_dimensions"]["matchs"] is True
        assert rumina["coverage_dimensions"]["statistiques"] is False
        summary = scouting_team_resource_summary(cards)
        assert summary["documented_player_matches"] > 0
        assert summary["performance_player_matches"] == 0
        assert summary["leaders"] == []
    finally:
        db.close()


def test_french_elite_scouting_team_surfaces_documented_performance_resources():
    db = SessionLocal()
    try:
        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.name == "Lille UC Métropole Water-Polo"))
        assert team is not None
        cards = scouting_player_resources(db, team.id)
        assert cards
        assert any(card["performance_matches"] > 0 for card in cards)
        assert any(card["metrics_count"] > 0 for card in cards)
        summary = scouting_team_resource_summary(cards)
        assert summary["linked_profiles"] > 0
        assert summary["performance_player_matches"] > 0
        assert summary["metrics"] > 0
    finally:
        db.close()


def test_scouting_pages_render_the_shared_player_resource_backbone():
    client = TestClient(app)
    _register(client)

    index = client.get("/scouting?kind=club")
    assert index.status_code == 200
    assert "SOCLE COMMUN À TOUT SCOUTING" in index.text
    assert "Couverture des preuves" in index.text

    db = SessionLocal()
    try:
        team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.external_key == "club-fr-granville-w-elite"))
        assert team is not None
        team_id = team.id
    finally:
        db.close()

    detail = client.get(f"/scouting/{team_id}")
    assert detail.status_code == 200
    assert "MÊME MOTEUR QUE LA FICHE JOUEUSE" in detail.text
    assert "Fiche joueuse complète" in detail.text
    assert "Rumina Edgerton" in detail.text
    assert "Couverture" in detail.text
