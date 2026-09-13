import json
import zipfile

from fastapi.testclient import TestClient
from main import app


def test_empty_analysis_has_diagnostic_and_no_fake_zero_in_zip():
    import uuid
    with TestClient(app) as client:
        email = f"empty-export-{uuid.uuid4().hex}@example.com"
        assert client.post("/register", data={"name": "Export test", "email": email,
            "password": "test-password-123"}, follow_redirects=False).status_code == 303
        created = client.post("/analysis/url/create", data={"team_name": "Granville",
            "opponent": "Test", "video_url": "https://youtu.be/Guo_UU282pI"}, follow_redirects=False)
        assert created.status_code == 303
        mid = int(created.headers["location"].split("/matches/")[1].split("/")[0])
        page = client.get(f"/matches/{mid}/analysis/result")
        assert page.status_code == 200
        assert "Analyse sans mesures sportives" in page.text
        assert "Rapport Vision disponible ✓" not in page.text
        from io import BytesIO
        response = client.get(f"/matches/{mid}/analysis/export.zip")
        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            def read(suffix):
                return archive.read(next(n for n in archive.namelist() if n.endswith(suffix))).decode()
            saved = json.loads(read("/analysis.json"))
            assert saved["diagnostics"]["outcome"] == "no_measurements"
            assert saved["ultimate"]["team"]["basic"]["goals"] is None
            assert "goals,0" not in read("/team_kpis.csv")
            assert "<td>Buts</td><td>0</td>" not in read("/report.html")
            assert "Non mesuré" in read("/report.html")
