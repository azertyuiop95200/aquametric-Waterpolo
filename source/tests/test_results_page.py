import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from main import app


def test_results_page_surfaces_six_womens_championships():
    client = TestClient(app)
    email = f"results-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/register",
        data={"email": email, "password": "ResultsTest123!", "name": "Results Test"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/competitions")
    assert page.status_code == 200
    assert "Championnats suivis" in page.text

    expected = {
        "women-italie": "Italie",
        "women-france": "France",
        "women-allemagne": "Allemagne",
        "women-espagne": "Espagne",
        "women-hongrie": "Hongrie",
        "women-russie": "Russie",
    }
    for anchor, country in expected.items():
        assert f'href="#{anchor}"' in page.text
        assert country in page.text


def test_results_mobile_order_rule_is_present():
    css = open("static/v124.css", encoding="utf-8").read()
    assert 'a[href="#women-italie"]' in css
    assert "section.panel:has([data-results-period])" in css
    assert "order:3" in css
    assert "order:4" in css
