"""Cloud 5 GiB sports extraction must stream bounded clips, not full video bytes."""
import json
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import Match, LargeVideoUpload, VideoActionAnalysis
from services import cloud_video_actions as cloud
from services import large_video_storage as store
from services.video_action_schema import ActionObservation


def setup_user(client):
    result=client.post("/register",data={
        "email":f"cloud-analysis-{uuid.uuid4().hex}@example.com",
        "password":"Password123!"},follow_redirects=False)
    assert result.status_code==303


def match_with_cloud_file(client):
    result=client.post("/analysis/url/create",data={
        "team_name":"Cloud WP","opponent":"Test WP",
        "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU",
        "input_device":"phone"},follow_redirects=False)
    assert result.status_code==303
    mid=int(result.headers["location"].split("/matches/")[1].split("/")[0])
    with SessionLocal() as db:
        match=db.get(Match,mid)
        key=f"videos/user-{match.owner_id}/{uuid.uuid4()}.mp4"
        db.add(LargeVideoUpload(id=str(uuid.uuid4()),owner_id=match.owner_id,
            object_key=key,upload_id="complete-in-test",
            filename="waterpolo.mp4",mime_type="video/mp4",
            total_bytes=3*1024**3,part_bytes=16*1024**2,metadata_json="{}",
            status="complete",match_id=mid))
        match.video_source="cloud"
        match.video_url=""
        match.video_path=key
        db.commit()
    return mid,key


def fake_action(kind,sec,side):
    return ActionObservation(second=sec,event_type=kind,side=side,confidence=.9,
        evidence="Action sportive fictive : test technique sans match réel.",
        team_evidence="La tenue fictive identifie le camp durant le test.").model_dump()


def test_large_cloud_video_analyzed_by_ranges_with_checkpoints(monkeypatch):
    monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    monkeypatch.setenv("GEMINI_API_KEY","fake-only")
    monkeypatch.setattr(store,"configured",lambda:True)
    monkeypatch.setattr(store,"signed_video_url",lambda key:"https://private-storage.test/object?sig=temporary")
    calls=[]
    monkeypatch.setattr(cloud,"_probe_remote_mp4",lambda key:{"duration":125.0,"width":1920,"height":1080})
    def fake_encode(key,segment,path):
        assert Path(path).name=="clip.mp4"
        assert 0<segment["end"]-segment["start"]<=60
        calls.append((key,segment["index"],segment["start"]))
        path.write_bytes(b"independent short range only")
    monkeypatch.setattr(cloud,"_encode_remote_segment",fake_encode)
    def fake_inference(path,*,team,opponent,timeout):
        assert path.stat().st_size < 1000
        # Every source-range is independently passed; never the 3 GiB body.
        return {"scene":"water_polo",
            "actions":[fake_action("goal" if len(calls)==1 else "save",4,
                 "for" if len(calls)==1 else "against")],
            "observability":[],"summary":"Observations fictives de test"}
    monkeypatch.setattr(cloud,"analyze_video_segment",fake_inference)
    with TestClient(app) as client:
        setup_user(client)
        mid,key=match_with_cloud_file(client)
        cloud.run_cloud_video_actions(mid,key)
        assert len(calls)==3
        assert [x[2] for x in calls]==[0,60,120]
        with SessionLocal() as db:
            match=db.get(Match,mid)
            assert not match.events
            run=db.scalar(select(VideoActionAnalysis).where(
                VideoActionAnalysis.match_id==mid))
            assert run.status=="complete"
            assert run.source_kind=="cloud"
            assert run.source_path==key
            assert run.duration_seconds==125
        progress=client.get(f"/matches/{mid}/analysis/actions/live").json()
        assert progress["completed"]==3
        assert progress["sides"]["for"]["goals"]==1
        assert progress["sides"]["against"]["saves"]==2
        from services.video_action_report import action_report
        with SessionLocal() as db:
            match=db.get(Match,mid)
            run=db.get(VideoActionAnalysis,run.id)
            first=action_report(db,match,run=run)["events"][0]["key"]
        direct=client.get(f"/matches/{mid}/analysis/actions/{run.id}/{first}/clip",follow_redirects=False)
        assert direct.status_code==307
        assert "private-storage.test" in direct.headers["location"]
        assert "#t=4" in direct.headers["location"]
        # Completed work is idempotent.
        cloud.run_cloud_video_actions(mid,key)
        assert len(calls)==3
        with TestClient(app) as stranger:
            setup_user(stranger)
            assert stranger.get(f"/matches/{mid}/analysis/actions/live").status_code==404
            assert stranger.get(f"/matches/{mid}/analysis/actions/{run.id}/{first}/clip",follow_redirects=False).status_code==404


def test_cloud_worker_refuses_unsigned_or_other_user_object(monkeypatch):
    monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    monkeypatch.setenv("GEMINI_API_KEY","fake-only")
    monkeypatch.setattr(store,"configured",lambda:True)
    probed=[]
    monkeypatch.setattr(cloud,"_probe_remote_mp4",lambda key:probed.append(key))
    with TestClient(app) as client:
        setup_user(client);mid,key=match_with_cloud_file(client)
        cloud.run_cloud_video_actions(mid,"videos/private/other.mp4")
        assert not probed
        with SessionLocal() as db:
            row=db.scalar(select(LargeVideoUpload).where(LargeVideoUpload.object_key==key))
            row.status="uploading"
            db.commit()
        cloud.run_cloud_video_actions(mid,key)
        assert not probed


def test_remote_probe_uses_ffprobe_only_and_validates_real_duration(monkeypatch):
    monkeypatch.setattr(cloud.shutil,"which",lambda name:"/usr/bin/ffprobe")
    monkeypatch.setattr(store,"signed_video_url",lambda key:"https://storage.test/owned?signature=private")
    seen=[]
    def fake_run(cmd,**kwargs):
        seen.append(cmd)
        return SimpleNamespace(returncode=0,stdout=json.dumps({
            "streams":[{"width":1920,"height":1080}],
            "format":{"duration":"135.25"}}),stderr="")
    monkeypatch.setattr(cloud.subprocess,"run",fake_run)
    meta=cloud._probe_remote_mp4("videos/user-5/test.mp4")
    assert meta["duration"]==135.25
    assert seen[0][-1].startswith("https://storage.test/")
    assert "135.25" not in str(seen[0])
