import os, json, subprocess
from pathlib import Path
os.environ["DATABASE_URL"] = "sqlite:///./test_aquametric.db"

from fastapi.testclient import TestClient
from main import app
from services.scoreboard_ocr import parse_scoreboard_text, tesseract_available, ocr_image
from services.autonomous_engine import infer_candidates, infer_periods
from services.audio_whistle import detect_whistle_candidates, ffmpeg_available
import cv2
import numpy as np

client = TestClient(app)


def test_scoreboard_parser_clock_period_and_score():
    p = parse_scoreboard_text("ESP 7  GRE 8   Q4  05:21")
    assert p["period"] == 4
    assert p["clock_seconds"] == 321
    assert p["home_score"] == 7
    assert p["away_score"] == 8


def test_autonomous_score_change_becomes_goal_candidate():
    obs = [
        {"second": 10, "home_score": 7, "away_score": 7, "period": 4, "ocr_confidence": .92},
        {"second": 20, "home_score": 8, "away_score": 7, "period": 4, "ocr_confidence": .91},
    ]
    out = infer_candidates(obs, [])
    goals = [c for c in out if c.event_type == "goal_candidate_home"]
    assert len(goals) == 1
    assert goals[0].confidence_label in {"MODERATE", "HIGH"}


def test_period_inference_never_invents_missing_quarters():
    obs = [{"second": 30, "period": 2, "ocr_confidence": .8}, {"second": 50, "period": 2, "ocr_confidence": .8}]
    periods = infer_periods(obs, 5000)
    assert [p["period"] for p in periods] == [2]


def test_tesseract_can_read_clean_synthetic_scoreboard_when_available():
    if not tesseract_available():
        return
    img = np.zeros((220, 1200, 3), dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (1199, 219), (25,25,25), -1)
    cv2.putText(img, "ESP 07  GRE 08  Q4  05:21", (25, 145), cv2.FONT_HERSHEY_SIMPLEX, 2.15, (255,255,255), 5, cv2.LINE_AA)
    text, conf = ocr_image(img)
    parsed = parse_scoreboard_text(text)
    assert parsed["clock_seconds"] == 321
    assert conf > 0.25


def test_whistle_detector_on_synthetic_audio_video(tmp_path: Path):
    if not ffmpeg_available():
        return
    target = tmp_path / "whistle.mp4"
    # 3 s black video; short 3.4 kHz sine burst between 1.0 and 1.25 s.
    filt = "sine=frequency=3400:sample_rate=16000:duration=0.25,adelay=1000|1000,apad=pad_dur=1.75"
    subprocess.run([
        "ffmpeg","-y","-v","error","-f","lavfi","-i","color=c=blue:s=640x360:d=3:r=25",
        "-f","lavfi","-i",filt,"-shortest","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(target)
    ], check=True)
    rows = detect_whistle_candidates(target)
    assert rows
    assert any(0.7 <= r.second <= 1.5 for r in rows)


def test_new_pages_exist_after_login():
    # Reuse a fresh identity; page availability does not require a video.
    email = "v5pages@example.com"
    client.post('/register', data={'email': email, 'password': 'strongpass123', 'name': 'V5 Tester'}, follow_redirects=True)
    # Existing tests may have created this identity; login if registration conflicts.
    client.post('/login', data={'email': email, 'password': 'strongpass123'}, follow_redirects=True)
    r = client.get('/dashboard')
    assert r.status_code == 200
