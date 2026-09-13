import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

import cv2
import numpy as np
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def _create_match():
    email = f"video-confirm-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": "Video Confirm", "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    response = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville",
            "opponent": "Confirmation Test",
            "competition": "Friendly",
            "match_date": "2026-09-05",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI&t=465s",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    match_id = int(location.split("/matches/", 1)[1].split("/", 1)[0])
    return match_id


def _jpeg_frame() -> bytes:
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:, :] = (120, 90, 35)
    cv2.rectangle(frame, (15, 15), (250, 85), (245, 245, 245), -1)
    cv2.putText(frame, "GWP 2 - 1 TEST 05:42 P2", (25, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (5, 5, 5), 2)
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    assert ok
    return encoded.tobytes()


def test_capture_page_is_truthful_before_video_pixels_are_confirmed():
    match_id = _create_match()
    response = client.get(f"/matches/{match_id}/analysis/browser-capture")
    assert response.status_code == 200
    html = response.text
    assert "Vidéo réelle" in html
    assert "En attente d’une image vidéo décodée côté serveur." in html
    assert "Analyse IA à 0 % tant qu’aucune image vidéo réelle n’a été décodée côté serveur." in html
    assert "En attente de la première image vidéo confirmée côté serveur" in html
    assert "Vidéo réelle reçue par l’IA ✓" in html
    assert "Pré-analyse Vision/OCR démarrée." not in html


def test_session_does_not_claim_ai_analysis_before_a_real_frame_is_decoded():
    match_id = _create_match()
    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "465",
            "source_duration_seconds": "3600",
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    session_id = body["session_id"]
    assert body["video_confirmed"] is False
    assert body["decoded_frame_batches"] == 0
    assert body["analysis_percent"] == 0.0
    assert "attente" in body["video_confirmation"]

    response = client.get(
        f"/matches/{match_id}/analysis/browser-capture/status",
        params={"session_id": session_id},
    )
    assert response.status_code == 200
    progress = response.json()["progress"]
    assert progress["video_confirmed"] is False
    assert progress["analysis_percent"] == 0.0


def test_invalid_progress_image_never_confirms_video():
    match_id = _create_match()
    response = client.post(f"/matches/{match_id}/analysis/browser-capture/session")
    session_id = response.json()["session_id"]

    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/frame",
        data={"session_id": session_id, "wall_second": "3.0"},
        files={"frame": ("not-a-frame.jpg", b"this is not a jpeg", "image/jpeg")},
    )
    assert response.status_code == 400, response.text

    response = client.get(
        f"/matches/{match_id}/analysis/browser-capture/status",
        params={"session_id": session_id},
    )
    progress = response.json()["progress"]
    assert progress["video_confirmed"] is False
    assert progress["decoded_frame_batches"] == 0
    assert progress["analysis_percent"] == 0.0


def test_real_decoded_frame_confirms_video_and_starts_ai_progress():
    match_id = _create_match()
    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/session",
        data={
            "source_start_second": "465",
            "source_duration_seconds": "3600",
            "playback_rate": "2",
            "parallel_segments": "4",
        },
    )
    session_id = response.json()["session_id"]

    response = client.post(
        f"/matches/{match_id}/analysis/browser-capture/frame",
        data={"session_id": session_id, "wall_second": "3.0"},
        files={"frame": ("progress.jpg", _jpeg_frame(), "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    progress = response.json()["progress"]
    assert progress["video_confirmed"] is True
    assert progress["decoded_frame_batches"] >= 1
    assert progress["progressive_samples"] >= 1
    assert progress["analysis_percent"] >= 1.0
    assert progress["first_decoded_wall_second"] == 3.0
    assert progress["video_confirmation"] == "Vidéo réelle reçue par l’IA ✓"
    assert "Vidéo réelle reçue par l’IA ✓" in progress["phase"]

    response = client.get(
        f"/matches/{match_id}/analysis/browser-capture/status",
        params={"session_id": session_id},
    )
    progress = response.json()["progress"]
    assert progress["video_confirmed"] is True
    assert progress["analysis_percent"] >= 1.0
