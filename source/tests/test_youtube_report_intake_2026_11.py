"""YouTube report intake and evidence-level regression tests (November 2026)."""
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from main import app
from db import SessionLocal
from models import Match
from services.video import youtube_embed

ROOT = Path(__file__).resolve().parents[1]


def test_youtube_live_replay_uses_a_valid_single_embed_query():
    embed = youtube_embed("https://www.youtube.com/live/Guo_UU282pI?feature=share")
    assert embed == "https://www.youtube.com/embed/Guo_UU282pI?enablejsapi=1&playsinline=1"
    assert youtube_embed("https://notyoutube.com/live/Guo_UU282pI") is None


def test_user_facing_iframes_do_not_append_second_question_mark():
    library = (ROOT / "templates" / "analysis_library.html").read_text(encoding="utf-8")
    url_page = (ROOT / "templates" / "url_analysis.html").read_text(encoding="utf-8")
    assert 'src="{{row.video_embed}}&rel=0&playsinline=1"' in library
    assert 'src="{{embed}}"' in url_page
    assert 'src="{{embed}}?enablejsapi=1"' not in url_page


def test_capture_page_displays_provider_readiness_without_promising_events():
    capture = (ROOT / "templates" / "browser_capture.html").read_text(encoding="utf-8")
    assert 'id="actionEngineReadiness"' in capture
    assert "fetch('/health/video-actions'" in capture
    assert "Aucune statistique individuelle ne sera inventée" in capture


def test_non_youtube_desktop_link_never_redirects_to_youtube_only_studio():
    with TestClient(app) as client:
        email = f"youtube-intake-{uuid.uuid4().hex}@example.com"
        result = client.post("/register", data={"name": "YouTube report test", "email": email,
                                              "password": "Password123!"}, follow_redirects=False)
        assert result.status_code == 303
        response = client.post("/analysis/url/create",
            data={"team_name": "Club test", "opponent": "Adversaire",
                  "video_url": "https://example.org/replay.mp4",
                  "input_device": "desktop"}, follow_redirects=False)
        assert response.status_code == 303
        location = response.headers["location"]
        assert location.endswith("/analysis/result")
        match_id = int(location.split("/matches/")[1].split("/")[0])
        with SessionLocal() as db:
            match = db.get(Match, match_id)
            assert match.status == "source_link_saved"
        html = client.get(location)
        assert html.status_code == 200
        assert "Vidéo identifiée mais non analysée" in html.text
        assert "Importer un fichier vidéo analysable" in html.text
        assert "Reprendre sur ordinateur" not in html.text


def test_youtube_live_link_still_offers_real_browser_capture_studio():
    with TestClient(app) as client:
        email = f"youtube-live-{uuid.uuid4().hex}@example.com"
        client.post("/register", data={"email": email, "password": "Password123!"},
                    follow_redirects=False)
        response = client.post("/analysis/url/create",
            data={"team_name": "Club test", "opponent": "Adversaire",
                  "video_url": "https://www.youtube.com/live/Guo_UU282pI",
                  "input_device": "desktop"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/analysis/browser-capture?" in response.headers["location"]
