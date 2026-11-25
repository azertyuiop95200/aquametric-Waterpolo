"""Large video upload: secure 3-GiB multipart ingest without transferring GB in CI.

The S3-compatible provider is mocked: HTTP auth, part validation, database
persistence, browser-facing status and report rendering are exercised normally.
"""
from __future__ import annotations

import math
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from main import app
from db import SessionLocal
from models import Match
from services import large_video_storage as storage


THREE_GIB = 3 * 1024 ** 3 + 117


class MissingObject(Exception):
    response = {"Error": {"Code": "404"}}


class FakeMultipartProvider:
    def __init__(self):
        self.upload_id = "r2-test-multipart-" + uuid.uuid4().hex
        self.key = ""
        self.parts = []
        self.final_size = None
        self.aborted = False
        self.complete_calls = 0
    def create_multipart_upload(self, *, Bucket, Key, ContentType, Metadata):
        assert Bucket == "private-test-bucket"
        assert Key.startswith("videos/user-")
        assert ContentType == "video/mp4"
        assert Metadata["aquametric_owner"]
        self.key = Key
        return {"UploadId":self.upload_id}
    def generate_presigned_url(self, operation, Params, ExpiresIn):
        assert ExpiresIn in (900, 3600)
        assert Params["Bucket"] == "private-test-bucket"
        assert Params["Key"] == self.key
        return "https://private-video-storage.test/" + operation + "?temporary=1"
    def list_parts(self, **kwargs):
        assert kwargs["UploadId"] == self.upload_id
        return {"Parts":self.parts, "IsTruncated":False}
    def head_object(self, *, Bucket, Key):
        if self.final_size is None:
            raise MissingObject()
        return {"ContentLength":self.final_size}
    def complete_multipart_upload(self, *, Bucket, Key, UploadId, MultipartUpload):
        assert [p["PartNumber"] for p in MultipartUpload["Parts"]] == list(range(1,len(self.parts)+1))
        self.final_size = sum(p["Size"] for p in self.parts)
        self.complete_calls += 1
        return {"Key":Key}
    def abort_multipart_upload(self, **kwargs):
        self.aborted = True
        return {}


def login(client, label):
    email=f"large-upload-{label}-{uuid.uuid4().hex}@example.com"
    res=client.post("/register",data={"email":email,"password":"Password123!"},follow_redirects=False)
    assert res.status_code==303
    return client


def configure_storage(monkeypatch, fake):
    monkeypatch.setattr(storage, "client", lambda: fake)
    monkeypatch.setattr(storage, "bucket", lambda: "private-test-bucket")
    monkeypatch.setattr(storage, "configured", lambda: True)


def create_upload(client, *, size=THREE_GIB):
    response=client.post("/api/large-upload/start",json={
        "filename":"Granville-Marseille.mp4","size_bytes":size,
        "team_name":"Granville WP","opponent":"CN Marseille",
        "category":"Women","competition":"Élite féminine","match_date":"2026-11-13",
    })
    assert response.status_code==200, response.text
    return response.json()


def test_server_without_bucket_explicitly_disables_large_video_upload(monkeypatch):
    for key in ("AQUAMETRIC_OBJECT_BUCKET","AQUAMETRIC_OBJECT_ENDPOINT",
                "AQUAMETRIC_OBJECT_ACCESS_KEY","AQUAMETRIC_OBJECT_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)
    with TestClient(app) as client:
        login(client,"disabled")
        capability=client.get("/api/large-upload/capabilities")
        assert capability.status_code == 200
        assert capability.json()["enabled"] is False
        assert capability.json()["max_gb"] >= 3
        result=client.post("/api/large-upload/start",json={
            "filename":"match.mp4","size_bytes":THREE_GIB,
            "team_name":"Granville","opponent":"Marseille"})
        assert result.status_code==503
        assert "stockage" in result.json()["detail"].lower()


def test_three_gib_multi_part_file_does_not_need_server_disk(monkeypatch):
    cloud=FakeMultipartProvider()
    configure_storage(monkeypatch,cloud)
    with TestClient(app) as client:
        login(client,"3gb")
        start=create_upload(client)
        assert start["total_bytes"]==THREE_GIB
        assert start["part_bytes"]==16*1024*1024
        assert start["total_parts"]==math.ceil(THREE_GIB/start["part_bytes"])
        upload_id=start["upload_id"]
        sign=client.post(f"/api/large-upload/{upload_id}/sign",json={"number":1})
        assert sign.status_code==200
        assert "private-video-storage.test" in sign.json()["url"]
        assert client.post(f"/api/large-upload/{upload_id}/sign",json={"number":start["total_parts"]+1}).status_code==400

        # Simulate a genuine large upload's provider-side part inventory without
        # ever allocating its 3 GB of bytes in memory or local disk.
        chunk=start["part_bytes"]
        cloud.parts=[
          {"PartNumber":i+1, "ETag":f'"part-{i+1}"',
           "Size":min(chunk,THREE_GIB-i*chunk)}
          for i in range(start["total_parts"])
        ]
        status=client.get(f"/api/large-upload/{upload_id}/status")
        assert status.status_code==200
        assert len(status.json()["completed_parts"]) == start["total_parts"]
        assert status.json()["uploaded_bytes"]==THREE_GIB
        completed=client.post(f"/api/large-upload/{upload_id}/complete")
        assert completed.status_code==200,completed.text
        assert completed.json()["status"]=="complete"
        url=completed.json()["match_url"]
        assert cloud.complete_calls==1
        # Client retry is idempotent: one match and one object only.
        again=client.post(f"/api/large-upload/{upload_id}/complete")
        assert again.status_code==200
        assert again.json()["match_url"]==url
        assert cloud.complete_calls==1
        match_id=int(url.split("/matches/")[1].split("/")[0])
        with SessionLocal() as db:
            match=db.get(Match,match_id)
            assert match.video_source=="cloud"
            assert match.video_path==cloud.key
            assert match.status=="cloud_video_received"
            assert match.competition=="Élite féminine"
        playback=client.get(f"/matches/{match_id}/video",follow_redirects=False)
        assert playback.status_code==307
        assert "private-video-storage.test" in playback.headers["location"]
        report=client.get(url)
        assert report.status_code==200
        assert 'id="cloudVideoReceived"' in report.text
        assert 'id="reviewSegmentPlayer"' in report.text
        assert "Aucun tir, but ou événement individuel" in report.text
        portable=client.get(url.replace("/result","/report.html"))
        assert portable.status_code==200
        assert "Vidéo volumineuse sauvegardée" in portable.text


def test_partial_or_wrong_sized_transfer_cannot_create_match(monkeypatch):
    cloud=FakeMultipartProvider()
    configure_storage(monkeypatch,cloud)
    with TestClient(app) as client:
        login(client,"incomplete")
        initiated=create_upload(client,size=storage.PART_BYTES+15)
        uid=initiated["upload_id"]
        assert client.post(f"/api/large-upload/{uid}/complete").status_code==409
        cloud.parts=[{"PartNumber":1,"ETag":'"p1"',"Size":storage.PART_BYTES-1},
                     {"PartNumber":2,"ETag":'"p2"',"Size":16}]
        assert client.post(f"/api/large-upload/{uid}/complete").status_code==409
        cloud.parts=[{"PartNumber":1,"ETag":'"p1"',"Size":storage.PART_BYTES},
                     {"PartNumber":2,"ETag":'"p2"',"Size":15}]
        assert client.post(f"/api/large-upload/{uid}/complete").status_code==200


def test_only_owner_can_access_presigned_parts_or_cancel(monkeypatch):
    cloud=FakeMultipartProvider()
    configure_storage(monkeypatch,cloud)
    with TestClient(app) as original,TestClient(app) as stranger:
        login(original,"owner")
        created=create_upload(original,size=100 * 1024**2)
        login(stranger,"stranger")
        session_id=created["upload_id"]
        for method,path in [
            ("GET",f"/api/large-upload/{session_id}/status"),
            ("POST",f"/api/large-upload/{session_id}/sign"),
            ("POST",f"/api/large-upload/{session_id}/complete"),
            ("DELETE",f"/api/large-upload/{session_id}"),
        ]:
            response=stranger.request(method,path,json={"number":1} if method=="POST" and path.endswith("sign") else None)
            assert response.status_code==404
        assert original.request("DELETE",f"/api/large-upload/{session_id}").status_code==200
        assert cloud.aborted
        assert original.post(f"/api/large-upload/{session_id}/sign",json={"number":1}).status_code==409


def test_file_limits_and_browser_controls(monkeypatch):
    cloud=FakeMultipartProvider()
    configure_storage(monkeypatch,cloud)
    with TestClient(app) as client:
        login(client,"limits")
        forbidden=client.post("/api/large-upload/start",json={
            "filename":"malicious.exe","size_bytes":1024,"team_name":"A","opponent":"B"})
        assert forbidden.status_code==400
        huge=client.post("/api/large-upload/start",json={
            "filename":"game.mp4","size_bytes":storage.MAX_BYTES+1,"team_name":"A","opponent":"B"})
        assert huge.status_code==413
    js=(Path(__file__).resolve().parents[1]/"static"/"large-video-upload.js").read_text(encoding="utf-8")
    markup=(Path(__file__).resolve().parents[1]/"templates"/"match_new.html").read_text(encoding="utf-8")
    assert "Math.min(3,todo.length)" in js
    assert "file.slice(first,last)" in js
    assert "largeUploadVideo" in markup and "large-video-upload.js" in markup
