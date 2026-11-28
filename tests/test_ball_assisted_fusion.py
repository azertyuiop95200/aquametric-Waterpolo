import cv2
import numpy as np
import pytest
from services.ball_assisted_fusion import fuse


def inputs():
    frames=[]
    for x in (100,110,120):
        f=np.full((720,1280,3),120,np.uint8)
        cv2.circle(f,(x,300),6,(60,60,60),-1)
        frames.append(f)
    seeds=[dict(frame=1,x=90/1280,y=300/720,reviewed=True),dict(frame=2,x=100/1280,y=300/720,reviewed=True)]
    return frames,seeds


def test_fusion_real_proposal_and_no_promotion():
    frames,seeds=inputs();r=fuse(*frames,frame_index=3,seeds=seeds)
    assert r['candidates'] and abs(r['candidates'][0]['x']*1280-110)<8
    assert not r['confirmed'] and not r['statistical_use_allowed']


def test_fusion_refuses_cut():
    frames,seeds=inputs();frames[0][:]=255
    assert fuse(*frames,frame_index=3,seeds=seeds)['status']=='scene_motion_refused'


def test_no_evidence_no_prediction():
    frames,seeds=inputs();frames=[np.full_like(f,120) for f in frames]
    assert fuse(*frames,frame_index=3,seeds=seeds)['candidates']==[]


def test_seed_gate():
    frames,seeds=inputs();seeds[0]['reviewed']=False
    with pytest.raises(ValueError):fuse(*frames,frame_index=3,seeds=seeds)
