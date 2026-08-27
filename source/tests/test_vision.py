import os
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import Club, Team, VisionAnalysis
from services.vision_baseline import scan_local_video


def make_synthetic_pool_video(path: Path, seconds: int = 8, fps: int = 10):
    w, h = 640, 360
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    assert writer.isOpened()
    for i in range(seconds * fps):
        # Broad cyan/blue water scene.
        frame = np.full((h, w, 3), (190, 135, 35), dtype=np.uint8)
        # Persistent scoreboard-like overlay at top left.
        cv2.rectangle(frame, (15, 12), (220, 62), (18, 18, 18), -1)
        cv2.putText(frame, f"ESP {i//25}  GRE {i//40}", (25, 45), cv2.FONT_HERSHEY_SIMPLEX, .72, (255,255,255), 2)
        # Moving players / ball surrogate.
        x = 60 + (i * 7) % 500
        cv2.circle(frame, (x, 180), 18, (250, 250, 250), -1)
        cv2.circle(frame, (w-x, 230), 16, (20, 30, 220), -1)
        cv2.circle(frame, (x + 35 if x < 560 else x - 35, 155), 6, (30, 220, 240), -1)
        writer.write(frame)
    writer.release()
    assert path.exists() and path.stat().st_size > 1000


def register_and_team(client: TestClient):
    email = f"vision-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post('/register', data={'name':'Vision','email':email,'password':'password123'}, follow_redirects=False)
    assert r.status_code == 303
    db = SessionLocal()
    try:
        club = db.scalar(select(Club).where(Club.name == 'Granville Water Polo'))
        club_id = club.id
    finally:
        db.close()
    name = f"Vision Team {uuid.uuid4().hex[:7]}"
    client.post('/teams', data={'name':name,'club_id':str(club_id),'category':'Women'})
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == name))
        return team.id
    finally:
        db.close()


def test_visual_baseline_reads_real_frames(tmp_path):
    video = tmp_path / 'synthetic_pool.mp4'
    make_synthetic_pool_video(video)
    result = scan_local_video(video, tmp_path / 'evidence', target_samples=24)
    assert 7.5 <= result.duration_seconds <= 8.5
    assert result.width == 640 and result.height == 360
    assert len(result.samples) >= 8
    assert result.avg_pool_ratio > 0.35
    assert result.avg_motion_score > 0
    assert result.contact_sheet_file
    assert (tmp_path / 'evidence' / result.contact_sheet_file).exists()
    assert result.scoreboard_candidates
    assert result.interesting_moments
    assert 'candidate' in result.video_type


def test_vision_lab_route_scans_uploaded_video(tmp_path):
    video = tmp_path / 'route_pool.mp4'
    make_synthetic_pool_video(video, seconds=6)
    client = TestClient(app)
    team_id = register_and_team(client)
    with video.open('rb') as fh:
        r = client.post('/matches', data={'team_id':str(team_id),'opponent':'Greece','competition':'Vision Test','match_date':'2026-08-26','video_url':''},
                        files={'video_file':('route_pool.mp4', fh.read(), 'video/mp4')}, follow_redirects=False)
    assert r.status_code == 303
    match_id = int(r.headers['location'].split('/')[-1])
    page = client.get(f'/matches/{match_id}/vision')
    assert page.status_code == 200 and 'VISION LAB' in page.text
    scan = client.post(f'/matches/{match_id}/vision/scan', follow_redirects=False)
    assert scan.status_code == 303
    page = client.get(f'/matches/{match_id}/vision')
    assert page.status_code == 200
    assert 'What the scanner actually saw' in page.text
    assert 'Scoreboard ROI candidates' in page.text
    contact = client.get(f'/matches/{match_id}/vision/contact-sheet')
    assert contact.status_code == 200 and contact.headers['content-type'].startswith('image/jpeg')
    db = SessionLocal()
    try:
        analysis = db.scalar(select(VisionAnalysis).where(VisionAnalysis.match_id == match_id).order_by(VisionAnalysis.id.desc()))
        assert analysis is not None and analysis.sample_count >= 8
    finally:
        db.close()
