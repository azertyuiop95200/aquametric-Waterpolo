import io
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db import SessionLocal
from models import Club, Team, Player
from services.video import youtube_embed, is_http_url


def register(client: TestClient, prefix="user"):
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/register",
        data={"name": prefix, "email": email, "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return email


def get_demo_club_id():
    db = SessionLocal()
    try:
        club = db.scalar(select(Club).where(Club.name == "Granville Water Polo"))
        assert club is not None
        return club.id
    finally:
        db.close()


def test_private_routes_redirect_to_login():
    client = TestClient(app)
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_registration_server_validation():
    client = TestClient(app)
    response = client.post("/register", data={"name": "x", "email": "bad", "password": "123"})
    assert response.status_code == 400
    assert "valid email" in response.text

    response = client.post("/register", data={"name": "x", "email": "x@example.com", "password": "123"})
    assert response.status_code == 400
    assert "at least 8" in response.text


def test_club_creation_and_team_creation():
    client = TestClient(app)
    register(client, "clubowner")
    club_name = f"Club {uuid.uuid4().hex[:8]}"
    response = client.post(
        "/clubs",
        data={"name": club_name, "country": "France", "division": "Test Division", "category": "Women"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db = SessionLocal()
    try:
        club = db.scalar(select(Club).where(Club.name == club_name))
        assert club is not None
        club_id = club.id
    finally:
        db.close()

    response = client.post(
        "/teams",
        data={"name": "Senior Women", "club_id": str(club_id), "category": "Women"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get("/teams")
    assert club_name in page.text
    assert "Senior Women" in page.text


def test_event_rejects_player_from_another_team():
    client = TestClient(app)
    register(client, "owner")
    club_id = get_demo_club_id()
    client.post("/teams", data={"name": "Team A", "club_id": str(club_id), "category": "Women"})
    client.post("/teams", data={"name": "Team B", "club_id": str(club_id), "category": "Women"})

    db = SessionLocal()
    try:
        teams = db.scalars(select(Team).where(Team.name.in_(["Team A", "Team B"])).order_by(Team.id.desc())).all()
        team_a = next(t for t in teams if t.name == "Team A")
        team_b = next(t for t in teams if t.name == "Team B")
    finally:
        db.close()

    client.post(f"/teams/{team_b.id}/players", data={"name": "Wrong player", "cap_number": "9"})
    db = SessionLocal()
    try:
        wrong_player = db.scalar(select(Player).where(Player.team_id == team_b.id, Player.name == "Wrong player"))
        assert wrong_player is not None
        wrong_player_id = wrong_player.id
    finally:
        db.close()

    response = client.post(
        "/matches",
        data={"team_id": str(team_a.id), "opponent": "Opponent", "competition": "Cup", "match_date": "", "video_url": ""},
        follow_redirects=False,
    )
    match_id = int(response.headers["location"].rsplit("/", 1)[-1])
    response = client.post(
        f"/matches/{match_id}/events",
        data={"event_type": "goal", "second": "10", "player_id": str(wrong_player_id), "note": ""},
    )
    assert response.status_code == 400
    assert "does not belong" in response.text


def test_uploaded_video_is_owner_protected():
    owner = TestClient(app)
    register(owner, "videoowner")
    club_id = get_demo_club_id()
    team_name = f"Video Team {uuid.uuid4().hex[:8]}"
    owner.post("/teams", data={"name": team_name, "club_id": str(club_id), "category": "Women"})
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == team_name))
        assert team is not None
        team_id = team.id
    finally:
        db.close()

    response = owner.post(
        "/matches",
        data={"team_id": str(team_id), "opponent": "Opponent", "competition": "", "match_date": "", "video_url": ""},
        files={"video_file": ("tiny.mp4", b"fake-mp4-content", "video/mp4")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    match_id = int(response.headers["location"].rsplit("/", 1)[-1])
    own_video = owner.get(f"/matches/{match_id}/video")
    assert own_video.status_code == 200
    assert own_video.content == b"fake-mp4-content"

    stranger = TestClient(app)
    register(stranger, "stranger")
    blocked = stranger.get(f"/matches/{match_id}/video")
    assert blocked.status_code == 404


def test_bad_upload_and_unsafe_url_are_rejected():
    client = TestClient(app)
    register(client, "validation")
    club_id = get_demo_club_id()
    team_name = f"Validation Team {uuid.uuid4().hex[:8]}"
    client.post("/teams", data={"name": team_name, "club_id": str(club_id), "category": "Women"})
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == team_name))
        assert team is not None
        team_id = team.id
    finally:
        db.close()

    response = client.post(
        "/matches",
        data={"team_id": str(team_id), "opponent": "Opponent", "video_url": "javascript:alert(1)"},
    )
    assert response.status_code == 400

    response = client.post(
        "/matches",
        data={"team_id": str(team_id), "opponent": "Opponent", "video_url": ""},
        files={"video_file": ("notvideo.exe", b"x", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_youtube_helpers():
    assert is_http_url("https://example.com/video")
    assert not is_http_url("javascript:alert(1)")
    assert youtube_embed("https://youtu.be/abcdefghijk").startswith("https://www.youtube.com/embed/abcdefghijk")
    assert youtube_embed("https://www.youtube.com/shorts/abcdefghijk").startswith("https://www.youtube.com/embed/abcdefghijk")
    assert youtube_embed("https://evil.example/youtu.be/abcdefghijk") is None


def test_player_profile_and_match_history_pages():
    client = TestClient(app)
    register(client, "profiles")
    club_id = get_demo_club_id()
    team_name = f"Profile Team {uuid.uuid4().hex[:8]}"
    client.post("/teams", data={"name": team_name, "club_id": str(club_id), "category": "Women"})
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == team_name))
        assert team is not None
        team_id = team.id
    finally:
        db.close()
    client.post(f"/teams/{team_id}/players", data={"name": "Profile Player", "cap_number": "4"})
    db = SessionLocal()
    try:
        player = db.scalar(select(Player).where(Player.team_id == team_id, Player.name == "Profile Player"))
        assert player is not None
        player_id = player.id
    finally:
        db.close()
    r = client.get("/players")
    assert r.status_code == 200 and "Profile Player" in r.text
    r = client.get(f"/players/{player_id}")
    assert r.status_code == 200 and "PLAYER PROFILE" in r.text
    r = client.get("/matches")
    assert r.status_code == 200 and "ANALYSIS HISTORY" in r.text


def test_study_media_screenshot_clip_and_download_permissions(tmp_path):
    import subprocess
    from pathlib import Path
    from models import Match, MediaArtifact

    client = TestClient(app)
    register(client, "evidence")
    club_id = get_demo_club_id()
    team_name = f"Evidence Team {uuid.uuid4().hex[:8]}"
    client.post("/teams", data={"name": team_name, "club_id": str(club_id), "category": "Women"})
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == team_name))
        team_id = team.id
    finally:
        db.close()

    sample = tmp_path / "sample.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x180:rate=15:duration=3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(sample)
    ], check=True)

    with sample.open("rb") as fh:
        response = client.post(
            "/matches",
            data={"team_id": str(team_id), "opponent": "Evidence Opponent", "competition": "Test", "match_date": "", "video_url": ""},
            files={"video_file": ("sample.mp4", fh.read(), "video/mp4")},
            follow_redirects=False,
        )
    assert response.status_code == 303
    match_id = int(response.headers["location"].rsplit("/", 1)[-1])

    shot = client.post(
        f"/matches/{match_id}/evidence",
        data={"artifact_type": "screenshot", "analysis_type": "tactic", "second": "1", "title": "Defensive shape", "note": "Study spacing", "downloadable": "1"},
        follow_redirects=False,
    )
    assert shot.status_code == 303

    clip = client.post(
        f"/matches/{match_id}/evidence",
        data={"artifact_type": "clip", "analysis_type": "action", "second": "1.5", "title": "Shot sequence", "before": "0.5", "after": "1", "downloadable": ""},
        follow_redirects=False,
    )
    assert clip.status_code == 303

    db = SessionLocal()
    try:
        artifacts = db.scalars(select(MediaArtifact).where(MediaArtifact.match_id == match_id).order_by(MediaArtifact.id)).all()
        assert len(artifacts) == 2
        screenshot, video_clip = artifacts
        assert screenshot.artifact_type == "screenshot" and screenshot.file_path
        assert video_clip.artifact_type == "clip" and video_clip.file_path
        shot_id, clip_id = screenshot.id, video_clip.id
    finally:
        db.close()

    assert client.get(f"/matches/{match_id}/evidence/{shot_id}").status_code == 200
    assert client.get(f"/matches/{match_id}/evidence/{shot_id}/download").status_code == 200
    assert client.get(f"/matches/{match_id}/evidence/{clip_id}").status_code == 200
    assert client.get(f"/matches/{match_id}/evidence/{clip_id}/download").status_code == 403

    page = client.get(f"/matches/{match_id}")
    assert "Defensive shape" in page.text
    assert "Shot sequence" in page.text


def test_youtube_evidence_is_bookmark_not_downloaded():
    from models import Match, MediaArtifact

    client = TestClient(app)
    register(client, "youtubeevidence")
    club_id = get_demo_club_id()
    team_name = f"YouTube Team {uuid.uuid4().hex[:8]}"
    client.post("/teams", data={"name": team_name, "club_id": str(club_id), "category": "Women"})
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == team_name))
        team_id = team.id
    finally:
        db.close()
    response = client.post(
        "/matches",
        data={"team_id": str(team_id), "opponent": "Remote Opponent", "competition": "", "match_date": "", "video_url": "https://youtu.be/abcdefghijk"},
        follow_redirects=False,
    )
    match_id = int(response.headers["location"].rsplit("/", 1)[-1])
    r = client.post(
        f"/matches/{match_id}/evidence",
        data={"artifact_type": "clip", "analysis_type": "tactic", "second": "42", "title": "Power play", "downloadable": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db = SessionLocal()
    try:
        artifact = db.scalar(select(MediaArtifact).where(MediaArtifact.match_id == match_id))
        assert artifact.artifact_type == "bookmark"
        assert artifact.file_path == ""
        assert artifact.is_downloadable is False
        assert "t=42s" in artifact.external_url
    finally:
        db.close()


def test_auto_study_pack_uses_verified_events_for_remote_video():
    from models import MediaArtifact

    client = TestClient(app)
    register(client, "autopack")
    club_id = get_demo_club_id()
    team_name = f"Auto Pack Team {uuid.uuid4().hex[:8]}"
    client.post("/teams", data={"name": team_name, "club_id": str(club_id), "category": "Women"})
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == team_name))
        team_id = team.id
    finally:
        db.close()
    response = client.post(
        "/matches",
        data={"team_id": str(team_id), "opponent": "Opponent", "video_url": "https://youtu.be/abcdefghijk"},
        follow_redirects=False,
    )
    match_id = int(response.headers["location"].rsplit("/", 1)[-1])
    client.post(f"/matches/{match_id}/events", data={"event_type": "goal", "second": "55", "player_id": "", "note": "Cross pass finish"})
    response = client.post(f"/matches/{match_id}/evidence/auto", follow_redirects=False)
    assert response.status_code == 303
    db = SessionLocal()
    try:
        artifact = db.scalar(select(MediaArtifact).where(MediaArtifact.match_id == match_id, MediaArtifact.source == "auto_from_event"))
        assert artifact is not None
        assert artifact.artifact_type == "bookmark"
        assert artifact.analysis_type == "action"
        assert "t=55s" in artifact.external_url
    finally:
        db.close()
