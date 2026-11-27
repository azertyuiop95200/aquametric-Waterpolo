"""Critical Analyze UX: an actual YouTube link OR local MP4 on desktop/mobile.

Ensures the primary user action is visible and cannot submit both inputs, and
a created match opens the measured report (never invented statistics).
"""
import uuid
from fastapi.testclient import TestClient
from main import app

def login(client):
    res=client.post("/register",data={
        "email":f"analysis-input-ux-{uuid.uuid4().hex}@example.com",
        "password":"Password123!"},follow_redirects=False)
    assert res.status_code==303


def test_analyze_screen_shows_youtube_and_file_selections_and_scripts():
    with TestClient(app) as client:
        login(client)
        page=client.get("/matches/new")
        assert page.status_code==200,page.text[:300]
        html=page.text
        for element in ('id="analysisForm"', 'id="desktopSource"', 'id="desktopLinkPanel"',
            'id="desktopFilePanel"', 'id="desktopVideoUrl"', 'id="desktopVideoFile"',
            'id="desktopAnalyzeSubmit"', 'id="desktopFileAnalyzeSubmit"',
            'id="phoneVideoUrl"', 'id="phoneVideoFile"',
            'id="largeUploadVideo"', 'id="largeUploadStart"',
            'id="youtubeDurationMinutes"'):
            assert element in html,element
        assert 'value="link">Coller un lien YouTube' in html
        assert 'value="file">Importer un fichier MP4' in html
        js=client.get("/static/analysis-input-mobile.js")
        assert js.status_code==200
        for snippet in ("$('desktopSource').addEventListener('change', syncSource)",
                        "desktopFile.disabled = !desktopUpload",
                        "desktopUrl.disabled = !desktopLink",
                        "$('youtubeDurationMinutes').disabled = desktopUpload || phoneUpload",
                        "form.requestSubmit(submitter)"):
            assert snippet in js.text,snippet
        assert 'formaction="/matches" formenctype="multipart/form-data"' in html
        assert 'formaction="/analysis/url/create" formenctype="application/x-www-form-urlencoded"' in html
        for video_type in (".mp4",".mov",".webm"):
            assert video_type in html


def test_youtube_link_registers_match_and_report_contains_dynamic_stats_and_pool_map(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    monkeypatch.delenv("AQUAMETRIC_VIDEO_ACTIONS",raising=False)
    with TestClient(app) as client:
        login(client)
        link=client.post("/analysis/url/create",data={
            "team_name":"L'équipe à mesurer","opponent":"Club adverse",
            "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU",
            "youtube_duration_minutes":"82.5","input_device":"phone",
            "category":"Women","scope_mode":"single",
        },follow_redirects=False)
        assert link.status_code==303,link.text[:500]
        location=link.headers["location"]
        assert "/matches/" in location
        report=client.get(location.split("#")[0])
        assert report.status_code==200,report.text[:500]
        assert 'id="liveAutomaticStats"' in report.text
        assert 'id="spatialDashboard"' in report.text
        assert 'id="spatialPitch"' in report.text
        assert 'id="sources"' in report.text
        assert 'id="directYoutubeAnalysis"' in report.text
        assert "Moteur" in report.text or "moteur" in report.text
        match_id=int(location.split("/matches/")[1].split("/")[0])
        progress=client.get(f"/matches/{match_id}/analysis/actions/live")
        assert progress.status_code==200
        payload=progress.json()
        assert payload["counted_events"]==0
        assert payload["configured"] is False
        assert payload["status"]=="unavailable"
        points=client.get(f"/api/matches/{match_id}/shot-map").json()
        assert points["points"]==[]
        assert points["shots_mapped"]==0
        js=client.get("/static/live-auto-stats.js")
        assert js.status_code==200
        assert "setTimeout(refresh,delay)" in js.text
        assert "location.reload()" not in js.text


def test_desktop_file_upload_uses_real_match_route_and_opens_report(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    monkeypatch.delenv("AQUAMETRIC_VIDEO_ACTIONS",raising=False)
    with TestClient(app) as client:
        login(client)
        uploaded=client.post("/matches",data={
            "team_name":"Equipe Vidéo","opponent":"Opposant Vidéo",
            "category":"Women","competition":"Test import MP4",
            "input_device":"desktop",
        },files={"video_file":("quart-temps-1.mp4",b"fake video file for request routing","video/mp4")},
        follow_redirects=False)
        assert uploaded.status_code==303,uploaded.text[:500]
        match_id=int(uploaded.headers["location"].split("/matches/")[1].split("/")[0])
        report=client.get(f"/matches/{match_id}/analysis/result")
        assert report.status_code==200
        assert 'id="liveAutomaticStats"' in report.text
        assert 'id="reviewSegmentPlayer"' in report.text
        assert 'id="spatialDashboard"' in report.text
        api=client.get(f"/api/matches/{match_id}/segments").json()
        assert len(api["segments"])>=1
        assert api["segments"][0]["source_type"]=="upload"
        stats=client.get(f"/matches/{match_id}/analysis/actions/live").json()
        assert stats["counted_events"]==0
        assert stats["status"]=="unavailable"
