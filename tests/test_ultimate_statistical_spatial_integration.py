"""HTTP/DB boundary tests for the private spatial review using only synthetic rows."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from jinja2 import Environment, FileSystemLoader, select_autoescape
from db import Base, get_db
from models import User, Club, Team, Match, Event, MatchVideoSegment, EventPosition
from spatial_review_routes import router, report_snapshot, event_sources
from test_spatial_replay import scene

class SpatialIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([User(id=1,email="owner@example.invalid",password_hash="test"),
                        User(id=2,email="other@example.invalid",password_hash="test")])
            db.flush()
            db.add(Club(id=1,name="QA",owner_id=1))
            db.flush()
            db.add(Team(id=1,name="Blanc",club_id=1,owner_id=1))
            db.flush()
            db.add(Match(id=1,owner_id=1,team_id=1,opponent="Bleu",video_source="upload",video_path="synthetic.mp4"))
            db.flush()
            db.add_all([Event(id=1,match_id=1,event_type="shot_off_target",second=22,confidence="CONFIRMED"),
                        Event(id=2,match_id=1,event_type="goal",second=22,confidence="CANDIDATE")])
            db.commit()
        app=FastAPI()
        @app.middleware("http")
        async def test_session(request:Request, call_next):
            # Synthetic authentication harness, never installed in the application.
            uid=request.headers.get("x-test-user")
            request.scope["session"]={"user_id":int(uid)} if uid else {}
            return await call_next(request)
        def session():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_db]=session
        app.include_router(router)
        self.client=TestClient(app)
        self.addCleanup(self.client.close)
        self.owner={"x-test-user":"1"}
        self.other={"x-test-user":"2"}

    def observation(self):
        with Session(self.engine) as db:
            source=event_sources(db,db.get(Match,1))[1]
        data=scene();data["source_binding"]=source["binding"]
        return data

    def test_owner_review_and_report(self):
        url="/matches/1/spatial/1"
        self.assertEqual(self.client.post(url,json=scene()).status_code,401)
        self.assertEqual(self.client.post(url,json=scene(),headers=self.other).status_code,404)
        self.assertEqual(self.client.post("/matches/1/spatial/2",json=scene(),headers=self.owner).status_code,404)
        response=self.client.post(url,json=self.observation(),headers=self.owner)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.headers["cache-control"],"private, no-store")
        self.assertIsNone(response.json()["options"][0]["goal_probability"])
        self.assertEqual(self.client.get("/matches/1/spatial.json",headers=self.other).status_code,404)
        data=self.client.get("/matches/1/spatial.json",headers=self.owner).json()
        self.assertEqual(data["eligible_count"],1)
        self.assertEqual(list(data["reviews"]),["1"])
        with Session(self.engine) as db:
            s=report_snapshot(db,db.get(Match,1))
        env=Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parents[1]/"source/templates")),autoescape=select_autoescape(["html"]))
        match=SimpleNamespace(id=1)
        html=env.get_template("spatial_decision_section.html").render(snapshot={"spatial_decision":s},match=match)
        self.assertIn("Non calibrée",html)
        self.assertIn("Action #1",html)
        self.assertNotIn("/sandbox",html)
        live=env.get_template("spatial_decision_section.html").render(snapshot={"spatial_decision":s},match=match,interactive_report=True)
        self.assertIn("/sandbox",live)

    def test_segment_guard_and_time_bound(self):
        data=self.observation();data["decision_second"]=23
        self.assertEqual(self.client.post("/matches/1/spatial/1",json=data,headers=self.owner).status_code,422)
        with Session(self.engine) as db:
            db.add(MatchVideoSegment(match_id=1,source_type="upload",video_path="second.mp4"))
            db.commit()
            self.assertEqual(report_snapshot(db,db.get(Match,1))["status"],"no_bound_actions")
        self.assertEqual(self.client.post("/matches/1/spatial/1",json=scene(),headers=self.owner).status_code,404)
        self.assertEqual(self.client.get("/matches/1/spatial.json",headers=self.owner).json()["reviews"],{})

    def test_local_segment_time_binding_and_source_change(self):
        with Session(self.engine) as db:
            db.add(MatchVideoSegment(id=10,match_id=1,period=1,part_index=1,source_type="upload",video_path="first.mp4"))
            db.add(MatchVideoSegment(id=11,match_id=1,period=2,part_index=2,source_type="upload",video_path="second.mp4",duration_seconds=100))
            db.add(EventPosition(event_id=1,segment_id=11,period=2,segment_second=30,provenance="manual_verified"))
            db.commit()
            e=event_sources(db,db.get(Match,1))[1]
            self.assertEqual(e["second"],30)
            self.assertEqual(e["period"],2)
            self.assertEqual(e["play_url"],"/matches/1/segments/11/video")
        url="/matches/1/spatial/1"
        data=self.observation()
        data["decision_second"]=29
        self.assertEqual(self.client.post(url,json=scene(),headers=self.owner).status_code,422)
        self.assertEqual(self.client.post(url,json=data,headers=self.owner).status_code,200)
        report=self.client.get("/matches/1/spatial.json",headers=self.owner).json()
        self.assertEqual(report["reviews"]["1"]["video_source"]["segment_id"],11)
        self.assertEqual(report["reviews"]["1"]["video_source"]["second"],30)
        with Session(self.engine) as db:
            db.get(MatchVideoSegment,11).video_path="replacement.mp4"
            db.commit()
        self.assertEqual(self.client.post(url,json=data,headers=self.owner).status_code,422)
        self.assertEqual(self.client.get("/matches/1/spatial.json",headers=self.owner).json()["reviews"],{})
        with Session(self.engine) as db:
            p=db.query(EventPosition).filter_by(event_id=1).one()
            p.period=1
            db.commit()
            self.assertEqual(event_sources(db,db.get(Match,1)),{})

if __name__=="__main__":unittest.main()
