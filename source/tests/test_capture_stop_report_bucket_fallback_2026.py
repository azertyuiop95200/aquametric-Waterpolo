"""Regression: the coach can stop YouTube, get a report, and import MP4
without buying a bucket. UI controls are real route targets, not decoration.
"""
import uuid
from fastapi.testclient import TestClient
from main import app


def register(client):
    response=client.post("/register",data={
        "email":f"analyse-stop-{uuid.uuid4().hex}@example.com",
        "password":"Password123!"
    },follow_redirects=False)
    assert response.status_code==303


def create_youtube(client):
    response=client.post("/analysis/url/create",data={
        "team_name":"Equipe Stop Test","opponent":"Equipe Opposante",
        "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU",
        "input_device":"phone",
    },follow_redirects=False)
    assert response.status_code==303,response.text[:500]
    return int(response.headers["location"].split("/matches/")[1].split("/")[0])


def test_studio_has_permanent_stop_and_report_actions_even_without_capture():
    with TestClient(app) as client:
        register(client)
        match_id=create_youtube(client)
        page=client.get(f"/matches/{match_id}/analysis/browser-capture")
        assert page.status_code==200,page.text[:200]
        html=page.text
        for required in (
            'id="finishCaptureAnytime"', 'id="viewCaptureReport"',
            'id="stopCapture"', 'id="stopCaptureLive"',
            "Terminer le visionnage et voir mon rapport",
            "if(!recorder||recorder.state!=='recording')",
            "reportUrl+'?capture_not_started=1'",
            "finishAnytimeBtn.addEventListener('click',requestStop)",
            "f.append('client_finish_reason',observed>=99.5?'normal':'manual_stop')",
            "f.append('client_read_percent',String(observed))",
            "stoppedReadPercent=localReadPercent()",
            ".capture-shell.studio-live .capture-quick-exit",
        ):
            assert required in html,required
        # In absence of a permitted capture, this is still a valid report,
        # but it must never invent detected goals or successful coverage.
        report=client.get(f"/matches/{match_id}/analysis/result?capture_not_started=1")
        assert report.status_code==200
        assert 'id="matchAnalysisReadiness"' in report.text
        assert 'id="reportQuickActions"' in report.text
        assert 'id="quickTagMatch"' in report.text
        assert 'id="quickShowStatistics"' in report.text
        assert 'id="quickAddPart"' in report.text
        assert 'id="quickDownloadReport"' in report.text
        assert "Le visionnage a été terminé sans capture vidéo enregistrée" in report.text
        assert 'href="#annotation"' in report.text
        assert 'href="#liveAutomaticStats"' in report.text
        assert 'href="#sources"' in report.text
        stats=client.get(f"/matches/{match_id}/analysis/actions/live").json()
        assert stats["counted_events"]==0
        assert stats["accuracy_verified"] is False
        html_report=client.get(f"/matches/{match_id}/analysis/report.html")
        assert html_report.status_code==200


def test_analyze_home_prominent_link_file_report_buttons():
    with TestClient(app) as client:
        register(client)
        page=client.get("/matches/new")
        assert page.status_code==200
        html=page.text
        for marker in (
            'id="quickYoutubeAnalysis"','id="quickFileAnalysis"',
            'id="quickReports"', 'href="/analysis-history"',
            'id="largeUploadLocalFallback"', 'id="chooseRegularUpload"',
            'id="desktopSource"', 'id="desktopFileAnalyzeSubmit"',
            'name="return_to_report" value="1"',
            'id="desktopVideoFile"'
        ):
            assert marker in html,marker
        js=client.get("/static/analysis-input-mobile.js").text
        assert "quickOpen('youtube')" in js
        assert "quickOpen('file')" in js
        assert "selector.dispatchEvent(new Event('change'" in js
        cloud=client.get("/static/large-video-upload.js").text
        assert "cloudControls.hidden = true" in cloud
        assert "localFallback.hidden = false" in cloud
        assert "const quarterFile = $('addMatchPartForm')?.querySelector" in cloud


def test_standard_mp4_analyze_goes_to_report_and_quarters_are_available(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    monkeypatch.delenv("AQUAMETRIC_VIDEO_ACTIONS",raising=False)
    with TestClient(app) as client:
        register(client)
        response=client.post("/matches",data={
            "team_name":"MP4 Sans Bucket","opponent":"Adversaire",
            "return_to_report":"1","competition":"Test UX",
        },files={"video_file":("quart-temps-1.mp4",b"fake fixture for routing","video/mp4")},
        follow_redirects=False)
        assert response.status_code==303,response.text[:600]
        assert response.headers["location"].endswith("/analysis/result")
        match_id=int(response.headers["location"].split("/matches/")[1].split("/")[0])
        result=client.get(response.headers["location"])
        assert result.status_code==200
        for marker in ('id="sources"','id="addMatchPartForm"',
                'id="matchAnalysisReadiness"','id="liveAutomaticStats"',
                'id="reportQuickActions"','id="largeUploadLocalFallback"',
                'id="chooseRegularUpload"','id="quickAddPart"'):
            assert marker in result.text,marker
        assert 'name="video_file"' in result.text
        assert client.get(f"/matches/{match_id}/analysis/actions/live").json()["counted_events"]==0
        # Old external integrations that POST to /matches still retain
        # the historical destination without return_to_report.
        legacy=client.post("/matches",data={
            "team_name":"MP4 Legacy","opponent":"Adversaire",
        },files={"video_file":("video.mp4",b"fake video","video/mp4")},follow_redirects=False)
        assert legacy.status_code==303
        assert not legacy.headers["location"].endswith("/analysis/result")


def test_unavailable_cloud_only_disables_large_upload_not_standard_import(monkeypatch):
    from services import large_video_storage
    monkeypatch.setattr(large_video_storage,"configured",lambda:False)
    with TestClient(app) as client:
        register(client)
        capabilities=client.get("/api/large-upload/capabilities")
        assert capabilities.status_code==200
        assert capabilities.json()["enabled"] is False
        new=client.get("/matches/new")
        assert new.status_code==200
        assert 'id="desktopFileAnalyzeSubmit"' in new.text
        assert 'id="largeUploadLocalFallback"' in new.text
