"""Direct public-YouTube to provider, local clip timestamps, resumed stats, auth."""
import json
import time
import uuid
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from db import SessionLocal
from models import VideoActionAnalysis
from services import youtube_direct_actions as yt
from services.video_action_schema import ActionObservation, SegmentObservation
from services.video_action_runner import normalize_observations


def login(client):
    email=f"youtube-direct-{uuid.uuid4().hex}@example.com"
    signed=client.post("/register",data={"email":email,"password":"Password123!"},follow_redirects=False)
    assert signed.status_code==303


def create_match(client):
    created=client.post("/analysis/url/create",data={
        "team_name":"Club de test","opponent":"Adversaire de test",
        "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU",
        "input_device":"phone"},follow_redirects=False)
    assert created.status_code==303
    return int(created.headers["location"].split("/matches/")[1].split("/")[0])


def observation(kind="goal",second=12,side="for"):
    return ActionObservation(second=second,event_type=kind,side=side,confidence=.94,
        evidence="Action synthétique utilisée pour valider le transport API uniquement.",
        team_evidence="La tenue du joueur permet de déterminer l'équipe de test.").model_dump()


def test_youtube_url_allowlist_no_ssrf_and_no_timestamp_loss():
    ok=[
      "https://www.youtube.com/watch?v=f_WzRHjybgU&t=40",
      "https://youtu.be/f_WzRHjybgU",
      "https://m.youtube.com/watch?v=f_WzRHjybgU",
      "https://www.youtube.com/live/f_WzRHjybgU",
    ]
    assert all(yt.canonical_public_youtube(x)=="https://www.youtube.com/watch?v=f_WzRHjybgU" for x in ok)
    for url in [
      "http://www.youtube.com/watch?v=f_WzRHjybgU",
      "https://youtube.com.evil.test/watch?v=f_WzRHjybgU",
      "https://www.youtube.com@evil.test/watch?v=f_WzRHjybgU",
      "https://www.youtube.com/watch?v=f_WzRHjybgU&v=other_id1",
      "https://www.youtube.com/watch?v=../../private",
      "https://127.0.0.1/watch?v=f_WzRHjybgU",
    ]:
        with pytest.raises(ValueError):
            yt.canonical_public_youtube(url)
    plans=yt.action_plan(125)
    assert [(s["start"],s["end"]) for s in plans]==[(0,60),(60,120),(120,125)]
    with pytest.raises(ValueError):
        yt.action_plan(4*3600+1)
    with pytest.raises(ValueError):
        yt.action_plan(float("nan"))


def test_gemini_youtube_request_uses_clipped_video_uri_and_validated_events(monkeypatch):
    monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    monkeypatch.setenv("GEMINI_API_KEY","fake-for-unit-test")
    observed=[]
    def transport(request):
        observed.append(json.loads(request.content))
        return httpx.Response(200,json={"status":"completed","steps":[{
            "type":"model_output","content":[{"type":"text",
             "text":SegmentObservation(scene="water_polo",actions=[
                ActionObservation.model_validate(observation(second=8))],
                observability=[],summary="Action fictive de test").model_dump_json()}]}]})
    original=httpx.Client
    with patch("httpx.Client",side_effect=lambda **kwargs:original(
        transport=httpx.MockTransport(transport),**kwargs)):
        clip={"index":1,"start":60,"end":120,"clip_start":60,"clip_end":120}
        result=yt.analyze_public_youtube_segment("https://youtu.be/f_WzRHjybgU",clip,
              team="Équipe A",opponent="Équipe B")
    assert result["actions"][0]["second"]==68
    sent=observed[0]
    assert sent["input"][0]["uri"]=="https://www.youtube.com/watch?v=f_WzRHjybgU"
    assert sent["input"][0]["processing"]["start_offset"]=="60s"
    assert sent["input"][0]["processing"]["end_offset"]=="120s"
    assert sent["model"]=="gemini-3.8-flash"
    assert "fake-for-unit-test" not in json.dumps(sent)


def test_autostart_youtube_direct_without_capture_and_resume_idempotently(monkeypatch):
    monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    monkeypatch.setenv("GEMINI_API_KEY","fake-for-test")
    invoked=[]
    def provider(url,segment,*,team,opponent,timeout):
        invoked.append(segment["index"])
        return normalize_observations({"scene":"water_polo","actions":[observation(
            kind="goal" if segment["index"]==0 else "save",second=11,
            side="for" if segment["index"]==0 else "against")],
            "observability":[],"summary":"Clip synthétique de test"},
            segment)
    monkeypatch.setattr(yt,"analyze_public_youtube_segment",provider)
    with TestClient(app) as coach:
        login(coach)
        match_id=create_match(coach)
        before=coach.get(f"/matches/{match_id}/analysis/actions/live").json()
        assert before["counted_events"]==0
        with patch.object(yt,"analyze_public_youtube_segment",provider):
            start=coach.post(f"/matches/{match_id}/analysis/youtube/direct",
                data={"duration_minutes":"2"},follow_redirects=False)
        assert start.status_code==303,start.text
        assert sorted(invoked)==[0,1]
        result=coach.get(f"/matches/{match_id}/analysis/actions/live").json()
        assert result["completed"]==2 and result["total"]==2
        assert result["sides"]["for"]["goals"]==1
        assert result["sides"]["for"]["shots"]==1
        assert result["sides"]["against"]["saves"]==1
        assert result["sources"][0]["coverage_percent"]==100
        assert len(result["recent_events"])==2
        with SessionLocal() as db:
            from models import Match
            match=db.get(Match,match_id)
            assert not match.events
            run=db.query(VideoActionAnalysis).filter(
                VideoActionAnalysis.match_id==match_id).first()
            assert run.source_kind=="youtube_direct"
        report=coach.get(f"/matches/{match_id}/analysis/result")
        assert report.status_code==200
        assert 'id="directYoutubeAnalysis"' in report.text
        # Repeated submit cannot re-request/charge already completed intervals.
        again=coach.post(f"/matches/{match_id}/analysis/youtube/direct",
            data={"duration_minutes":"2"},follow_redirects=False)
        assert again.status_code==303 and sorted(invoked)==[0,1]
        url=coach.get(f"/matches/{match_id}/analysis/actions/{run.id}/{result['recent_events'][0].get('key','irrelevant')}/clip",follow_redirects=False)
        # Above UI doesn't expose the action key; get an actual one from report.
        from services.video_action_report import action_report
        with SessionLocal() as db:
            match=db.get(Match,match_id)
            key=action_report(db,match,run=db.get(VideoActionAnalysis,run.id))["events"][0]["key"]
        clip=coach.get(f"/matches/{match_id}/analysis/actions/{run.id}/{key}/clip",follow_redirects=False)
        assert clip.status_code==307
        assert "youtube.com/watch" in clip.headers["location"]
        assert "t=11s" in clip.headers["location"]
        with TestClient(app) as outsider:
            login(outsider)
            assert outsider.post(f"/matches/{match_id}/analysis/youtube/direct",
                data={"duration_minutes":"2"},follow_redirects=False).status_code==404
            assert outsider.get(f"/matches/{match_id}/analysis/actions/live").status_code==404


def test_direct_youtube_without_provider_never_fabricates_stats(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    with TestClient(app) as coach:
        login(coach);mid=create_match(coach)
        not_ready=coach.post(f"/matches/{mid}/analysis/youtube/direct",
            data={"duration_minutes":"80"},follow_redirects=False)
        assert not_ready.status_code==503
        empty=coach.get(f"/matches/{mid}/analysis/actions/live").json()
        assert empty["counted_events"]==0
        assert empty["sides"]["for"]["goals"]==0
        assert empty["accuracy_verified"] is False
