"""PoloIQ Roboflow dataset is not a trained goal-scoring model.

Tests verify parsing of candidates, privacy, and no imaginary sports events.
"""
import io
import uuid
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from main import app
from services import poloiq_vision as ai
from services.quick_tag_analytics import reviewed_match_metrics


def signed_in(client):
    email=f"roboflow-{uuid.uuid4().hex}@example.com"
    signup=client.post("/register",data={"email":email,"password":"Password123!"},follow_redirects=False)
    assert signup.status_code==303


def new_match(client):
    response=client.post("/analysis/url/create",data={
        "team_name":"Vision QA","opponent":"Test Club",
        "competition":"QA uniquement","category":"Women",
        "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU",
        "input_device":"desktop"
    },follow_redirects=False)
    assert response.status_code==303
    return int(response.headers["location"].split("/matches/")[1].split("/")[0])


def test_poloiq_public_data_not_mistaken_for_live_model(monkeypatch):
    monkeypatch.delenv("ROBOFLOW_API_KEY",raising=False)
    monkeypatch.delenv("AQUAMETRIC_POLOIQ_MODEL_ID",raising=False)
    ready=ai.readiness()
    assert not ready["configured"]
    assert ready["dataset"]["public_trained_models"]==0
    assert ready["dataset"]["source_images"]==4865
    assert ready["dataset"]["license"]=="CC BY 4.0"
    assert ready["dataset"]["classes"]==["ball","goal","goalie_red","player_dark","player_white"]
    with TestClient(app) as client:
        response=client.get("/api/poloiq/readiness")
        assert response.status_code==200
        assert response.json()["mode"]=="training_dataset_only"
        assert response.json()["video_events_confirmed_automatically"] is False
        signed_in(client)
        match_id=new_match(client)
        report=client.get(f"/matches/{match_id}/analysis/result")
        assert report.status_code==200
        assert 'id="poloiqVision"' in report.text
        assert 'id="spatialDashboard"' in report.text
        assert 'poloiq-vision-preview.js' in report.text
        blank=client.post(f"/api/matches/{match_id}/poloiq/frame",
                          files={"image":("frame.jpg",b"x", "image/jpeg")})
        assert blank.status_code==503


def test_invalid_model_is_not_considered_deployed(monkeypatch):
    monkeypatch.setenv("ROBOFLOW_API_KEY","test-placeholder")
    monkeypatch.setenv("AQUAMETRIC_POLOIQ_MODEL_ID","https://evil.example/foo/1")
    assert ai.configured() is False
    monkeypatch.setenv("AQUAMETRIC_POLOIQ_MODEL_ID","poloiq-detection/1")
    assert ai.configured() is True


def test_roboflow_boxes_are_candidates_and_do_not_create_map_shots():
    fake={"image":{"width":1000,"height":500},
          "predictions":[
            {"class":"ball","confidence":.93,"x":300,"y":250,"width":50,"height":45},
            {"class":"player_dark","confidence":.88,"x":700,"y":250,"width":100,"height":150},
            {"class":"goal","confidence":.11,"x":500,"y":100,"width":100,"height":80},
            {"class":"made_up_goal_scored","confidence":.999,"x":200,"y":140,"width":12,"height":12},
            {"class":"ball","confidence":.99,"x":float("nan"),"y":4,"width":4,"height":4},
            {"class":"player_white","confidence":.99,"x":12,"y":15,"width":-2,"height":10},
          ]}
    rows=ai.normalized_detections(fake)
    assert len(rows)==2
    assert rows[0]["class"]=="ball"
    assert rows[0]["bbox_normalized"]==[.275,.455,.325,.545]
    assert all(r["status"]=="candidate_object_detection_not_a_sporting_event" for r in rows)
    assert reviewed_match_metrics([], "https://youtu.be/f_WzRHjybgU")["team"]["tagged_goals"]==0


def test_prediction_endpoint_validates_image_and_owner_and_never_records_goals(monkeypatch):
    monkeypatch.setenv("ROBOFLOW_API_KEY","not-a-real-key")
    monkeypatch.setenv("AQUAMETRIC_POLOIQ_MODEL_ID","trained-poloiq/1")

    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"image":{"width":300,"height":200},
            "predictions":[{"class":"ball","confidence":.9,"x":150,"y":90,"width":20,"height":20}]}

    def fake_post(url,**kwargs):
        assert url=="https://detect.roboflow.com/trained-poloiq/1"
        assert kwargs["params"]["api_key"]=="not-a-real-key"
        assert kwargs["timeout"]<=25
        return FakeResponse()

    frame=np.zeros((200,300,3),dtype=np.uint8)
    good,pixels=cv2.imencode(".jpg",frame)
    assert good
    with TestClient(app) as a,TestClient(app) as b:
        signed_in(a);mid=new_match(a)
        signed_in(b)
        other=b.post(f"/api/matches/{mid}/poloiq/frame",
          files={"image":("frame.jpg",pixels.tobytes(),"image/jpeg")})
        assert other.status_code==404
        wrong_type=a.post(f"/api/matches/{mid}/poloiq/frame",
          files={"image":("video.mp4",b"video","video/mp4")})
        assert wrong_type.status_code==415
        with patch("httpx.post",fake_post):
            response=a.post(f"/api/matches/{mid}/poloiq/frame",
              files={"image":("frame.jpg",pixels.tobytes(),"image/jpeg")})
        assert response.status_code==200,response.text
        assert response.json()["count"]==1
        assert response.json()["status"]=="unverified_object_candidates"
        assert response.json()["detections"][0]["class"]=="ball"
        report=a.get(f"/api/matches/{mid}/shot-map").json()
        assert report["points"]==[]
        assert report["events_reviewed"]==0
