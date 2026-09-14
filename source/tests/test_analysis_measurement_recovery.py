"""Regression tests for the empty match report, including actual OCR pixels."""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from services import scoreboard_ocr as ocr
from services import live_frame_match_analysis as live
from services.analysis_diagnostics import analysis_diagnostics
from services.autonomous_engine import infer_candidates


def test_native_host_falls_back_without_system_tesseract(monkeypatch):
    monkeypatch.setattr(ocr, "tesseract_available", lambda: False)
    monkeypatch.setattr(ocr, "_onnx_engine", lambda: lambda *a, **kw: ([[[], "Q1 7:30 2 1", .98]], []))
    assert ocr.ocr_available()
    assert ocr.ocr_image(np.ones((50, 300, 3), dtype=np.uint8)) == ("Q1 7:30 2 1", .98)


def test_missing_ocr_is_explicit_not_silent_success(monkeypatch):
    monkeypatch.setattr(live, "ocr_available", lambda: False)
    rows, meta = live._focused_ocr_from_live_frames([], [], source_duration=2979,
        playback_rate=2, segments=4, moments=[], max_samples=240)
    assert rows == []
    assert meta["reason"] == "ocr_unavailable"
    assert meta["targets"] == 0


def test_score_samples_cover_whole_match_not_first_visual_peaks():
    plan = live._ocr_plan(2979, [{"second": 20 + n, "score": .9} for n in range(24)], 240)
    assert len(plan) == 240
    assert plan[0] == 0
    assert plan[-1] > 2978
    assert sum(t > 2200 for t in plan) > 50


def test_legacy_complete_with_no_events_is_not_a_success():
    automatic = {"summary": {"visual_samples": 52}, "observations": [],
        "candidates": [{"event_type": "unclassified_action_candidate"}] * 16}
    diagnosis = analysis_diagnostics(automatic, [])
    assert diagnosis["outcome"] == "no_measurements"
    assert diagnosis["goal_candidates"] == 0
    assert diagnosis["unclassified_candidates"] == 16
    assert diagnosis["latest_repeated_score"] is None


def test_duplicate_timestamps_cannot_confirm_a_score():
    row = {"second": 1, "home_score": 2, "away_score": 1, "ocr_confidence": .99}
    assert analysis_diagnostics({"observations": [row, row]}, [])["latest_repeated_score"] is None


def test_native_ocr_runs_during_capture_and_is_throttled(tmp_path, monkeypatch):
    import capture_turbo_routes as capture
    import capture_turbo_routes_v5 as banners

    monkeypatch.setattr(ocr, "tesseract_available", lambda: False)
    capture._write_state(tmp_path, {"status": "running", "parallel_segments": 1,
                                  "playback_rate": 1, "source_duration_seconds": 60})
    frame = np.full((360, 640, 3), (160, 90, 20), dtype=np.uint8)
    frame[:80] = 255
    cv2.putText(frame, "Q1 7:30 2 1", (12, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3)
    state = capture._progressive_frame_analysis(tmp_path, frame, 0.)
    assert state["progressive_ocr_hits"] == 1
    assert "7:30" in state["latest_live_ocr"][0]
    state = banners._observe_match_banners(tmp_path, frame, 0.,
        SimpleNamespace(team=SimpleNamespace(name="Test home"), opponent="Test away"))
    assert state["banner_text_samples"][0]["second"] == 0
    assert "7:30" in state["banner_text_samples"][0]["text"]

    def unexpected_ocr(*args, **kwargs):
        pytest.fail("A throttled frame must not run OCR again, including after timestamp zero")
    monkeypatch.setattr(capture, "ocr_image", unexpected_ocr)
    monkeypatch.setattr(banners, "ocr_image", unexpected_ocr)
    assert capture._progressive_frame_analysis(tmp_path, frame, 1.)["progressive_ocr_hits"] == 1
    assert len(banners._observe_match_banners(tmp_path, frame, 1.,
        SimpleNamespace(team=SimpleNamespace(name="Test home"), opponent="Test away"))["banner_text_samples"]) == 1


def test_real_onnx_pixels_create_score_observations_and_goal_candidate(tmp_path, monkeypatch):
    import rapidocr_onnxruntime  # Required in CI: do not silently skip the real backend.
    # Deliberately disable Tesseract: exercise the backend needed on the native host.
    monkeypatch.setattr(ocr, "tesseract_available", lambda: False)
    records = []
    for index, (clock, home) in enumerate((("7:30", 0), ("7:20", 1), ("7:10", 1))):
        frame = np.full((100, 640, 3), 255, dtype=np.uint8)
        cv2.putText(frame, f"Q1 {clock} {home} 0", (12, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.7, (0, 0, 0), 3)
        path = tmp_path / f"frame-{index:04d}.jpg"
        assert cv2.imwrite(str(path), frame)
        records.append({"index": index, "wall_second": index * 10., "path": path})
    monkeypatch.setattr(live, "_ocr_plan", lambda *args: [0., 10., 20.])
    rows, meta = live._focused_ocr_from_live_frames(records,
        [SimpleNamespace(x=0, y=0, w=1, h=1, name="score")], source_duration=30,
        playback_rate=1, segments=1, moments=[], max_samples=3, budget_seconds=30)
    assert [(r["home_score"], r["away_score"]) for r in rows] == [(0, 0), (1, 0), (1, 0)]
    assert [r["second"] for r in rows] == [0, 10, 20]
    goals = [c for c in infer_candidates(rows, []) if c.event_type == "goal_candidate_home"]
    assert len(goals) == 1
    assert goals[0].evidence["before"] == [0, 0]
    assert goals[0].evidence["after"] == [1, 0]
    diagnosis = analysis_diagnostics({"observations": rows, "candidates": [c.to_dict() for c in goals]}, [])
    assert diagnosis["latest_repeated_score"] == {"left": 1, "right": 0, "second": 20}
    assert diagnosis["goal_candidates"] == 1
    # No blind promotion to verified match/player statistics.
    assert diagnosis["verified_events"] == 0
    assert meta["targets"] == 3

    # Continue through real persistence and the saved report, not just OCR.
    import json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from db import Base
    from models import User, Club, Team, Match, AutonomousAnalysis, AutonomousEventCandidate
    from services.analysis_product import analysis_snapshot, _html_report
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from pathlib import Path
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="ocr-test@example.com", password_hash="test-only")
        club = Club(name="Test club")
        db.add_all([user, club]); db.flush()
        team = Team(name="Test team", club_id=club.id, owner_id=user.id)
        db.add(team); db.flush()
        match = Match(owner_id=user.id, team_id=team.id, opponent="Test opponent")
        db.add(match); db.flush()
        auto = AutonomousAnalysis(match_id=match.id, observations_json=json.dumps(rows),
            summary_json=json.dumps({"scoreboard_observations": len(rows)}), status="partial", ocr_available=True)
        db.add(auto); db.flush()
        for goal in goals:
            db.add(AutonomousEventCandidate(analysis_id=auto.id, match_id=match.id,
                second=goal.second, event_type=goal.event_type, confidence_score=goal.confidence,
                confidence_label=goal.confidence_label, summary=goal.summary,
                evidence_json=json.dumps(goal.evidence), source="test-pixels"))
        db.commit(); db.expire_all()
        snapshot = analysis_snapshot(db, match)
        assert snapshot["diagnostics"]["goal_candidates"] == 1
        assert len(snapshot["automatic"]["observations"]) == 3
        assert snapshot["ultimate"]["team"]["basic"]["goals"] is None
        report = _html_report(match, snapshot)
        assert "Lectures du score" in report and "Q1 7:20" in report
        assert "<td>Non mesuré</td>" in report
        env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parents[1] / "templates"), autoescape=select_autoescape())
        fragment = env.get_template("analysis_scoreboard_evidence.html").render(snapshot=snapshot)
        assert "1–0" in fragment
        assert "3 lectures du score" in fragment
    engine.dispose()
