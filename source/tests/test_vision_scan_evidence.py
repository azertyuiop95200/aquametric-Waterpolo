from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db import Base
from models import Match, MatchVideoSegment, VisionScanEvidence, Event
from services.vision_scan_evidence import save_scan, report, read_scan, export_scans

def test_persist_anonymous_scan_and_exclude_replaced_segment(tmp_path):
    e=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    source=tmp_path/"test.mp4";source.write_bytes(b"synthetic fixture")
    with Session(e) as db:
        m=Match(id=1,owner_id=1,team_id=1,opponent="fixture",video_source="upload",video_path="main.mp4")
        seg=MatchVideoSegment(id=2,match_id=1,period=1,source_type="upload",video_path="test.mp4")
        db.add_all([m,seg]);db.commit()
        data={"engine":"fixture","first_frame":10,"end_frame_exclusive":12,
              "frames":[{"second":.4}],"tracklets_total":2,"tracklets_at_least_3":0,
              "identity_verified":False,"metrics_validated":False,"statistical_use_allowed":False}
        row=save_scan(db,m,seg,"tracklets",data,source)
        assert save_scan(db,m,seg,"tracklets",data,source).id==row.id
        assert db.query(VisionScanEvidence).count()==1
        assert db.query(Event).count()==0
        assert read_scan(row)["result"]==data
        s=report(db,m)
        assert s["rows"][0]["tracklets"]==2 and s["rows"][0]["period"]==1
        assert not s["statistical_use_allowed"]
        exported=export_scans(db,m,s)
        assert len(exported)==1 and exported[0]["result"]==data
        assert exported[0]["digest"]==s["rows"][0]["digest"]
        seg.video_path="replacement.mp4";db.commit()
        assert report(db,m)["rows"]==[]
        assert report(db,m)["stale_count"]==1
        assert export_scans(db,m,report(db,m))==[]
    e.dispose()


def test_corrupt_payload_is_not_exported(tmp_path):
    e=create_engine("sqlite:///:memory:");Base.metadata.create_all(e)
    source=tmp_path/"test.mp4";source.write_bytes(b"fixture")
    with Session(e) as db:
        m=Match(id=1,owner_id=1,team_id=1,opponent="fixture",video_source="upload",video_path="test.mp4")
        db.add(m);db.commit()
        row=save_scan(db,m,None,"tracklets",{"frames":[]},source)
        summary=report(db,m)
        row.payload_json='{"result":{"tracks":[]}}';db.commit()
        assert report(db,m)["stale_count"]==1
        assert export_scans(db,m,summary)==[]
    e.dispose()
