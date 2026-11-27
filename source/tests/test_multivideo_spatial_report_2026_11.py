"""Match with four replays: precise spatial points, secure ownership and report.

All shots in these tests are synthetic annotations used only in the CI database;
they are never claims about the real Granville-Marseille match.
"""
from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi.testclient import TestClient
from main import app
from db import SessionLocal
from models import EventPosition, Match, MatchVideoSegment
from services.spatial_match_analysis import spatial_match_dashboard
from match_video_segments_routes import segment_rows

BASE="/matches"

def register(client):
    response=client.post("/register",data={
        "email":f"quarter-{uuid.uuid4().hex}@example.com",
        "password":"Password123!"},follow_redirects=False)
    assert response.status_code==303

def create_match(client):
    response=client.post("/analysis/url/create",data={
        "team_name":"Equipe X","opponent":"Equipe Y","category":"Women",
        "competition":"QA-test","input_device":"desktop",
        "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU",
    },follow_redirects=False)
    assert response.status_code==303, response.text[:500]
    return int(response.headers["location"].split("/matches/")[1].split("/")[0])

def append_link(client, match_id, period, link):
    res=client.post(f"{BASE}/{match_id}/segments", data={
        "period":str(period),"label":f"Q{period}","video_url":link
    },follow_redirects=False)
    assert res.status_code==303,res.text
    return res

def confirmed(client,match_id,*,event_type,point=None,segment_id=None,period=1,second=80,perspective="for"):
    data={"event_type":event_type,"second":str(second),"perspective":perspective,
          "phase_tag":"even_attack","period":str(period),
          "return_to":"report","observed":"1"}
    if point is not None:
        data.update({"coord_x":str(point[0]),"coord_y":str(point[1])})
    if segment_id is not None:
        data["segment_id"]=str(segment_id)
    return client.post(f"{BASE}/{match_id}/events",data=data,follow_redirects=False)

def test_four_quarter_links_in_one_match_with_exact_shot_points():
    with TestClient(app) as client:
        register(client)
        mid=create_match(client)
        # First video from the historical URL is treated as Q1 without migration.
        for p,video in enumerate([
            "https://www.youtube.com/watch?v=abc123XYZ_2",
            "https://www.youtube.com/watch?v=abc123XYZ_3",
            "https://www.youtube.com/watch?v=abc123XYZ_4"],start=2):
            append_link(client,mid,p,video)
        response=client.get(f"/api/matches/{mid}/segments")
        assert response.status_code==200
        segments=response.json()["segments"]
        assert len(segments)==4
        assert [s["period"] for s in segments]==[1,2,3,4]
        assert len(set(s["video_url"] for s in segments))==4
        assert segments[0]["id"] is None
        q2=segments[1]["id"]
        q3=segments[2]["id"]
        assert confirmed(client,mid,event_type="goal",point=(11.25,30.5),period=1,second=62).status_code==303
        assert confirmed(client,mid,event_type="shot_off_target",point=(72,45),
                         segment_id=q2,period=1,second=18.4).status_code==303
        assert confirmed(client,mid,event_type="goal",point=(62,30),
                         segment_id=q3,period=8,second=22,perspective="against").status_code==303
        assert confirmed(client,mid,event_type="shot_on_target",segment_id=q3,second=90).status_code==303
        result=client.get(f"/api/matches/{mid}/shot-map")
        assert result.status_code==200,result.text
        stats=result.json()
        assert stats["shots_reviewed"]==4
        assert stats["shots_mapped"]==3
        assert stats["unlocated_shots"]==1
        assert stats["xg_available"] is False
        points=stats["points"]
        assert [(p["x"],p["y"],p["period"]) for p in points]==[
            (11.25,30.5,1),(72,45,2),(62,30,3)]
        assert points[1]["second"]==18.4
        assert "abc123XYZ_2" in points[1]["proof_url"]
        assert "t=18s" in points[1]["proof_url"]
        assert [p for p in stats["periods"] if p["period"]==3][0]["against"]==1
        assert stats["shot_zones"]["for"][0]["shots"]==1
        assert stats["shot_zones"]["for"][0]["goals"]==1
        report=client.get(f"/matches/{mid}/analysis/result")
        assert report.status_code==200,report.text[:400]
        for marker in ('id="spatialDashboard"', 'id="spatialPitch"', 'id="sources"',
                       'id="reviewSegmentSelect"', 'id="coordX"', 'id="coordY"',
                       'value="2"', 'id="mapPeriod"', 'id="mapPlayer"',
                       "heatmap", "3 / 4"):
            assert marker in report.text,marker
        assert "f_WzRHjybgU" in report.text
        reportjson=client.get(f"/matches/{mid}/analysis/report.html")
        assert reportjson.status_code==200

def test_reject_invalid_coordinates_and_other_match_segment():
    with TestClient(app) as client:
        register(client);a=create_match(client);b=create_match(client)
        append_link(client,b,2,"https://youtu.be/ZXY987abc12")
        foreign_id=client.get(f"/api/matches/{b}/segments").json()["segments"][-1]["id"]
        assert confirmed(client,a,event_type="goal",point=(101,30)).status_code==400
        assert confirmed(client,a,event_type="goal",point=(float("nan"),30)).status_code==400
        assert confirmed(client,a,event_type="goal",segment_id=foreign_id).status_code==404
        assert client.get(f"/api/matches/{a}/shot-map").json()["events_reviewed"]==0
        assert client.post(f"/matches/{a}/segments",data={
            "period":"9","video_url":"https://youtu.be/abcABC12345"},follow_redirects=False).status_code==400

def test_reject_cross_owner_segments_even_same_video():
    with TestClient(app) as a,TestClient(app) as b:
        register(a);first=create_match(a)
        register(b);second=create_match(b)
        assert b.get(f"/api/matches/{first}/shot-map").status_code==404
        assert b.get(f"/api/matches/{first}/segments").status_code==404
        assert b.post(f"/matches/{first}/segments",
                      data={"period":"2","video_url":"https://youtu.be/abc123XYZ_9"},
                      follow_redirects=False).status_code==404
        assert a.get(f"/api/matches/{second}/shot-map").status_code==404

def test_no_fabricated_map_from_youtube_title():
    with TestClient(app) as client:
        register(client)
        mid=create_match(client)
        stats=client.get(f"/api/matches/{mid}/shot-map").json()
        assert stats["points_count"]==0
        assert stats["shots_mapped"]==0
        assert stats["shots_reviewed"]==0
        assert stats["events_reviewed"]==0
        assert stats["periods"]==[]
