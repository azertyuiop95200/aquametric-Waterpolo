import cv2
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db import Base
from models import Match, Event, VisionScanEvidence
from services.local_scan_batch import run, plan
from services.vision_scan_evidence import report, export_scans


def test_plan_bounded():
    assert plan(20)==[(0,20)]
    assert plan(1000)==[(116,75),(347,75),(578,75),(809,75)]


def test_real_local_scan_persists_reuses_and_rejects_replacement(tmp_path):
    p=tmp_path/'fixture.avi'
    def make(value):
        w=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'MJPG'),25,(320,180))
        assert w.isOpened()
        for i in range(12):
            f=np.full((180,320,3),(150,100,value),np.uint8)
            cv2.circle(f,(80+i,90),6,(255,255,255),-1)
            w.write(f)
        w.release()
    make(40)
    e=create_engine('sqlite:///:memory:');Base.metadata.create_all(e)
    with Session(e) as db:
        m=Match(id=1,owner_id=1,team_id=1,opponent='fixture',video_source='upload',video_path=p.name)
        db.add(m);db.commit()
        a=run(db,m,p,window_count=1)
        assert a['status']=='experimental_partial' and len(a['persisted_ids'])==2 and not a['failed']
        assert db.query(Event).count()==0
        rows=export_scans(db,m,report(db,m))
        assert all(r['result']['source_sha256_at_execution']==a['source_sha256_at_execution'] for r in rows)
        assert all(r['result']['frames'] and not r['result']['statistical_use_allowed'] for r in rows)
        b=run(db,m,p,window_count=1)
        assert b['reused_runs']==2 and b['persisted_ids']==a['persisted_ids']
        make(70)
        c=run(db,m,p,window_count=1)
        assert c['source_sha256_at_execution']!=a['source_sha256_at_execution'] and c['reused_runs']==0
        assert db.query(VisionScanEvidence).count()==4 and db.query(Event).count()==0
        summary=report(db,m)
        assert summary['stale_count']==2
        assert {r['id'] for r in summary['rows']}==set(c['persisted_ids'])
    e.dispose()
