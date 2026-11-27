"""Automatic sports counters update per finished video segment, without invented facts."""
import json
import time
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import VideoActionAnalysis
from services.video_action_runner import normalize_observations, segment_plan
from services.video_action_schema import ActionObservation
from services.live_action_dashboard import _counts


def sign_up(client):
    result=client.post("/register",data={
        "email":f"live-auto-{uuid.uuid4().hex}@example.com",
        "password":"Password123!"},follow_redirects=False)
    assert result.status_code == 303


def source_match(client):
    created=client.post("/analysis/url/create",data={
        "team_name":"Test AquaMetric","opponent":"Adversaire",
        "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU",
        "input_device":"desktop"},follow_redirects=False)
    assert created.status_code == 303
    return int(created.headers["location"].split("/matches/")[1].split("/")[0])


def action(kind,sec=3,side="for",confidence=.92):
    return ActionObservation(second=sec,event_type=kind,side=side,confidence=confidence,
        cap_number=None,evidence="Événement fictif uniquement pour le test du transport",
        team_evidence="Équipe de test visible dans la vidéo simulée").model_dump()


def test_counting_goals_as_shots_once_and_ignoring_uncertain_events():
    rows=[
        {"event_type":"goal","counted":True},
        {"event_type":"shot_on_target","counted":True},
        {"event_type":"shot_off_target","counted":False},
        {"event_type":"turnover","counted":True},
    ]
    result=_counts(rows)
    assert result["goals"]==1
    assert result["shots"]==2
    assert result["efficiency_pct"]==50.0
    assert result["turnovers"]==1
    assert result["actions"]==3


def test_live_api_changes_after_new_minute_without_page_reload(monkeypatch):
    monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    monkeypatch.setenv("GEMINI_API_KEY","synthetic-non-working-key")
    with TestClient(app) as client:
        sign_up(client)
        match_id=source_match(client)
        plan,_=segment_plan(120)
        plan[0]["status"]="complete"
        plan[0]["result"]=normalize_observations(
            {"scene":"water_polo","actions":[action("goal")],"observability":[],
             "summary":"Première minute fictive"},plan[0])
        with SessionLocal() as db:
            run=VideoActionAnalysis(match_id=match_id,fingerprint=uuid.uuid4().hex,
              status="running",model="synthetic-test",source_kind="upload",source_path="/tmp/one-video.mp4",
              segments_json=json.dumps(plan),duration_seconds=120,
              updated_at=time.time(),message="Analyse en cours")
            db.add(run);db.commit();db.refresh(run)
            run_id=run.id
        path=f"/matches/{match_id}/analysis/actions/live"
        first=client.get(path)
        assert first.status_code==200,first.text
        assert first.headers["cache-control"]=="private, no-store"
        first=first.json()
        assert first["scope"]=="automatic_provisional_only"
        assert first["accuracy_verified"] is False
        assert first["verified_events_unchanged"] is True
        assert first["completed"]==1 and first["total"]==2
        assert first["sides"]["for"]["goals"]==1
        assert first["sides"]["for"]["shots"]==1
        assert first["recent_events"][0]["video_part"]==1
        previous_revision=first["revision"]
        with SessionLocal() as db:
            run=db.get(VideoActionAnalysis,run_id)
            plan=json.loads(run.segments_json)
            plan[1]["status"]="complete"
            plan[1]["result"]=normalize_observations(
                {"scene":"water_polo","actions":[action("save",4,side="against")],
                 "observability":[],"summary":"Deuxième minute fictive"},plan[1])
            run.segments_json=json.dumps(plan)
            run.status="complete";run.updated_at=time.time()
            db.commit()
        second=client.get(path).json()
        assert second["completed"]==2
        assert second["sides"]["for"]["goals"]==1
        assert second["sides"]["against"]["saves"]==1
        assert len(second["recent_events"])==2
        assert second["revision"]!=previous_revision
        full_html=client.get(f"/matches/{match_id}/analysis/result")
        assert full_html.status_code==200
        assert 'id="liveAutomaticStats"' in full_html.text
        assert 'live-auto-stats.js' in full_html.text
        js=client.get("/static/live-auto-stats.js")
        assert js.status_code==200
        assert "location.reload()" not in js.text
        assert "cell.dataset.autoField" in js.text
        with TestClient(app) as stranger:
            sign_up(stranger)
            assert stranger.get(path).status_code==404


def test_multiple_quarters_keep_local_timestamps_not_global(monkeypatch):
    monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    monkeypatch.setenv("GEMINI_API_KEY","fake-key")
    with TestClient(app) as client:
        sign_up(client);mid=source_match(client)
        for number in (1,2):
            plan,_=segment_plan(60)
            plan[0]["status"]="complete"
            plan[0]["result"]=normalize_observations(
                {"scene":"water_polo","actions":[action("goal",sec=6)],
                 "observability":[],"summary":"Simulation Q"+str(number)},plan[0])
            with SessionLocal() as db:
                db.add(VideoActionAnalysis(match_id=mid,fingerprint=uuid.uuid4().hex,
                    status="complete",model="fixture",source_kind="upload",
                    source_path="/tmp/quarter-"+str(number)+".mp4",
                    segments_json=json.dumps(plan),duration_seconds=60,updated_at=time.time()))
                db.commit()
        result=client.get(f"/matches/{mid}/analysis/actions/live").json()
        assert result["sides"]["for"]["goals"]==2
        assert result["sides"]["for"]["shots"]==2
        assert result["total"]==2
        assert [x["video_part"] for x in result["recent_events"]]==[1,2]
        assert [x["second"] for x in result["recent_events"]]==[6,6]


def test_regular_upload_triggers_inference_only_when_configured(monkeypatch):
    from services import video_action_provider
    import video_action_routes
    called=[]
    monkeypatch.setattr(video_action_routes,"run_upload_actions",lambda match_id:called.append(match_id))
    monkeypatch.setattr(video_action_provider,"provider_configuration",
        lambda:{"configured":True,"enabled":True,"availability_code":"ready",
                "model":"synthetic","message":"Fixture"})
    with TestClient(app) as client:
        sign_up(client)
        response=client.post("/matches",data={
            "team_name":"AquaMetric Test","opponent":"Autre",
            "category":"Women","competition":"CI",
        },files={"video_file":("short.mp4",b"tiny fake video bytes", "video/mp4")},follow_redirects=False)
        assert response.status_code==303,response.text[:400]
        mid=int(response.headers["location"].split("/matches/")[1].split("/")[0])
        assert called==[mid]
