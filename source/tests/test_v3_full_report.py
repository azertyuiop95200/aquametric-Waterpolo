"""Exercise the real app and its ZIP generator, not a manually assembled snapshot.
Every record in this test is synthetic. No external video, model or paid request.
"""
import json
import os
import runpy
import uuid
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from main import app
from db import SessionLocal
from models import Event, Match
from services.review_reference_import import load
from spatial_review_routes import event_sources

ROOT=Path(__file__).resolve().parents[2]

def register(client):
    r=client.post("/register",data={"name":"QA V3","email":f"qa-v3-{uuid.uuid4().hex}@example.invalid",
        "password":"test-password-123"},follow_redirects=False)
    assert r.status_code==303,r.text

def test_full_reference_and_spatial_report():
    fixture=runpy.run_path(str(ROOT/"tests/test_review_reference_import.py"))["fixture"]
    scene=runpy.run_path(str(ROOT/"tests/test_spatial_replay.py"))["scene"]
    raw=json.dumps(fixture()).encode()
    _,_,digest,_=load(raw)
    with TestClient(app) as owner, TestClient(app) as other:
        register(owner)
        register(other)
        r=owner.post("/analysis/url/create",data={"team_name":"QA SYNTHETIQUE V3",
            "opponent":"ADVERSAIRE FICTIF","video_url":"https://youtu.be/Guo_UU282pI",
            "competition":"Test informatique sans vidéo réelle"},follow_redirects=False)
        assert r.status_code==303,r.text
        mid=int(r.headers["location"].split("/matches/")[1].split("/")[0])
        base=f"/matches/{mid}"
        def send(client, payload, expected=""):
            return client.post(base+"/review-reference",
                files={"reference_file":("fixture.json",payload,"application/json")},
                data={"home_color":"bleus","same_match":"1","expected_digest":expected},
                follow_redirects=False)
        assert send(other,raw).status_code==404
        assert send(owner,raw).status_code==303
        assert owner.get(base+"/review-reference/1.json").status_code==200
        assert other.get(base+"/review-reference/1.json").status_code==404
        with SessionLocal() as db:
            assert db.query(Event).filter_by(match_id=mid).count()==0
        archive=owner.get(base+"/analysis/export.zip")
        assert archive.status_code==200,archive.text
        def read_zip(response):
            with ZipFile(BytesIO(response.content)) as z:
                assert z.testzip() is None
                def read(suffix):
                    return z.read(next(n for n in z.namelist() if n.endswith(suffix)))
                return json.loads(read("/analysis.json")),read("/report.html").decode()
        snapshot, html=read_zip(archive)
        assert snapshot["review_references"][0]["digest"]==digest
        assert snapshot["review_references"][0]["report"]["verified_match_event_count"]==0
        assert snapshot["statistics"]["team"]["basic"]["goals"] is None
        assert "distinctes des statistiques confirmées" in html
        assert "&lt;script&gt;" in html
        changed=fixture()
        changed["reference"]["events"][0]["source_observation"]="Révision synthétique"
        revised=json.dumps(changed).encode()
        assert send(owner,revised).status_code==409
        assert send(owner,revised,digest).status_code==303
        r=owner.post(base+"/events",data={"event_type":"shot_off_target","second":"22",
            "perspective":"for","period":"1","return_to":"report","observed":"1"},follow_redirects=False)
        assert r.status_code==303,r.text
        with SessionLocal() as db:
            match=db.get(Match,mid)
            sources=event_sources(db,match)
            assert len(sources)==1
            event_id,source=next(iter(sources.items()))
        data=scene();data["source_binding"]=source["binding"]
        r=owner.post(base+f"/spatial/{event_id}",json=data)
        assert r.status_code==200,r.text
        assert r.json()["options"][0]["goal_probability"] is None
        assert other.get(base+"/spatial.json").status_code==404
        assert other.get(base+"/analysis/export.zip").status_code==404
        for suffix in ["/analysis/result","/analysis/report.html"]:
            page=owner.get(base+suffix)
            assert page.status_code==200,page.text
            assert 'id="reviewReferences"' in page.text
            assert 'id="spatialDecision"' in page.text
            assert page.text.count('id="shotContext"')==1
            assert page.text.count('id="recoveryReview"')==1
        archive=owner.get(base+"/analysis/export.zip")
        assert archive.status_code==200,archive.text
        snapshot,html=read_zip(archive)
        assert snapshot["statistics"]["team"]["basic"]["shots"]==1
        assert len(snapshot["verified_events"])==1
        assert snapshot["review_references"][0]["revision_count"]==1
        assert str(event_id) in snapshot["spatial_decision"]["reviews"]
        assert "Non calibrée" in html
        assert "Révision synthétique" in html
        assert snapshot["recovery_review"]["status"]=="unavailable"
        assert snapshot["shot_context"]["status"]=="unavailable"
        assert html.count('id="shotContext"')==1
        assert html.count('id="recoveryReview"')==1
        assert html.index('id="coach-tirs"')<html.index('id="shotContext"')<html.index('id="coach-passes"')
        assert html.index('id="coach-phases"')<html.index('id="recoveryReview"')<html.index('id="coach-mouvement"')
        assert 'id="spatialDecision"' in html
        out=os.getenv("AQUAMETRIC_FULL_REPORT_DIR")
        if out:
            folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
            (folder/"QA_SYNTHETIQUE_V3.zip").write_bytes(archive.content)
