"""One-click YouTube match setup must be safe, prefilled and never fabricate."""
import uuid
from urllib.parse import quote

from fastapi.testclient import TestClient

import main
from main import app


VIDEO = "https://www.youtube.com/watch?v=f_WzRHjybgU"


def test_youtube_quickstart_validates_destination():
    encoded = quote(VIDEO, safe="")
    assert main._demo_analysis_destination(f"/matches/new?video_url={encoded}") == (
        "/matches/new?video_url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Df_WzRHjybgU"
    )
    assert main._demo_analysis_destination("https://evil.test/") == "/my-team"
    assert main._demo_analysis_destination("//evil.test/matches/new") == "/my-team"
    assert main._demo_analysis_destination("/matches/new?video_url=javascript:alert(1)") == "/my-team"
    assert main._demo_analysis_destination("/matches/new?video_url=https%3A%2F%2Fevil.test%2Fwatch%3Fv%3Df_WzRHjybgU") == "/my-team"


def test_authenticated_match_form_prefills_exact_source_without_autostart():
    with TestClient(app) as client:
        email = f"youtube-link-{uuid.uuid4().hex}@example.com"
        response = client.post("/register", data={"email": email, "password": "Password123!"}, follow_redirects=False)
        assert response.status_code == 303
        page = client.get("/matches/new?video_url=" + quote(VIDEO, safe=""))
        assert page.status_code == 200
        assert page.text.count('value="https://www.youtube.com/watch?v=f_WzRHjybgU"') == 2
        assert "Équipe à analyser" in page.text and "Adversaire" in page.text
        # No game report is manufactured merely by opening the prefilled page.
        assert "Démarrer l’analyse dans cet onglet" not in page.text


def test_demo_user_redirect_to_prefilled_page(monkeypatch):
    monkeypatch.setattr(main, "WEB_DEMO_MODE", True)
    with TestClient(app) as client:
        jump = "/matches/new?video_url=" + quote(VIDEO, safe="")
        response = client.get("/demo-login?next=" + quote(jump, safe=""), follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == jump
        form = client.get(response.headers["location"])
        assert form.status_code == 200
        assert VIDEO in form.text
