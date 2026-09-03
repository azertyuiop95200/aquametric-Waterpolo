from pathlib import Path

from main import app
from tactical_media_routes import sequence_review

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_tactical_study_pack_route_is_registered():
    routes = [(getattr(r, "path", ""), set(getattr(r, "methods", set()) or set())) for r in app.routes]
    assert any(path == "/matches/{match_id}/intelligence/study-pack" and "POST" in methods for path, methods in routes)


def test_match_intelligence_exposes_micro_clips_and_key_frames():
    template = read("templates/match_intelligence.html")
    assert "/intelligence/study-pack" in template
    assert "review-media" in template
    assert "s.clip_url" in template
    assert "s.screenshot_url" in template
    assert "review.clip_full" in template
    assert "review.frame_full" in template


def test_tactical_sequence_review_is_phase_specific_and_evidence_bound():
    review = sequence_review({
        "phase": "power_play",
        "passes": 5,
        "shots_for": 1,
        "goals_for": 1,
        "losses_for": 0,
        "goals_against": 0,
        "time_to_first_shot": 7.2,
    })
    assert "Zone+" in review["objective"]
    assert "7.2" in review["tempo"]
    assert "5 passes" in review["outcome"]
    assert review["question"]


def test_third_party_video_copying_is_not_enabled():
    routes = read("tactical_media_routes.py")
    assert 'match.video_source == "upload"' in routes
    assert "timestamped_video_url" in routes
    assert 'artifact_type="bookmark"' in routes
    assert "create_clip(source_path" in routes
    # Local file generation must sit inside the user-upload branch; external
    # sources are represented as bookmarks/timestamps rather than downloads.
    external_branch = routes.split("elif match.video_url:", 1)[1]
    assert "create_clip(" not in external_branch
    assert "create_screenshot(" not in external_branch


def test_five_locales_cover_video_review_controls():
    i18n = read("static/i18n-v125.js")
    for lang in ("en", "fr", "it", "es", "ru"):
        assert f"\n{lang}:{{" in i18n
    for key in ("review.prepare", "review.objective", "review.watch", "review.risk", "review.question"):
        assert i18n.count("'" + key + "'") >= 5
