import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_clean_report_uses_non_measured_instead_of_fake_zero():
    email = f"clean-report-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/register", data={"name": "Clean Report", "email": email, "password": "password123"}, follow_redirects=False)
    assert r.status_code == 303
    r = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Free Women Team",
            "opponent": "Free Opponent",
            "category": "Women",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI",
        },
        follow_redirects=False,
    )
    match_id = int(r.headers["location"].split("/matches/", 1)[1].split("/", 1)[0])
    report = client.get(f"/matches/{match_id}/analysis/result")
    assert report.status_code == 200
    html = report.text
    assert "RAPPORT D’ANALYSE · PREUVES D’ABORD" in html
    assert "Free Women Team" in html
    assert "Free Opponent" in html
    assert "Fémin" not in html or "Women" in html
    assert "— · non mesuré" in html
    assert "Aucun rapport Vision finalisé" in html
    assert "Aucun nom ni numéro fourni manuellement n’est imposé" in html
    assert "Roster de référence" not in html


def test_clean_report_route_has_priority():
    routes = [r for r in app.routes if getattr(r, "path", None) == "/matches/{match_id}/analysis/result" and "GET" in (getattr(r, "methods", set()) or set())]
    assert routes
    assert routes[0].endpoint.__module__ == "analysis_result_clean_v2"
