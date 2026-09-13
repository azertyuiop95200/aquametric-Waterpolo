from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import capture_turbo_routes_v15 as v15
from services.vision_baseline import VisionBaselineError


def _write_state(root: Path, **values) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "progress.json").write_text(json.dumps(values), encoding="utf-8")


def test_capture_duration_hint_uses_source_geometry(tmp_path):
    root = tmp_path / "session"
    media = root / "derived_v14" / "capture-normalized.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"video")
    _write_state(
        root,
        source_start_second=60.0,
        source_duration_seconds=3660.0,
        playback_rate=2.0,
        parallel_segments=4,
    )

    assert v15._capture_duration_hint(media) == pytest.approx(450.0)


def test_probe_recovers_when_only_duration_metadata_is_missing(tmp_path, monkeypatch):
    root = tmp_path / "session"
    media = root / "capture.webm"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"video")
    _write_state(
        root,
        source_start_second=0.0,
        source_duration_seconds=2400.0,
        playback_rate=2.0,
        parallel_segments=4,
    )

    def missing_duration(_path):
        raise VisionBaselineError("Parallel capture duration could not be determined.")

    class FakeCapture:
        def __init__(self, _path):
            self.path = _path

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == v15.cv2.CAP_PROP_FPS:
                return 30.0
            if prop == v15.cv2.CAP_PROP_FRAME_COUNT:
                return 0.0
            if prop == v15.cv2.CAP_PROP_FRAME_WIDTH:
                return 1280.0
            if prop == v15.cv2.CAP_PROP_FRAME_HEIGHT:
                return 720.0
            return 0.0

        def read(self):
            return True, np.ones((8, 8, 3), dtype=np.uint8)

        def release(self):
            return None

    monkeypatch.setattr(v15, "_ORIGINAL_MOSAIC_PROBE", missing_duration)
    monkeypatch.setattr(v15.cv2, "VideoCapture", FakeCapture)

    fps, frames, width, height, duration = v15._probe_with_capture_hint(media)
    assert fps == pytest.approx(30.0)
    assert frames == 0
    assert (width, height) == (1280, 720)
    assert duration == pytest.approx(300.0)


def test_durable_marker_rescues_even_if_progress_reverted_to_running(tmp_path):
    root = tmp_path / "session"
    root.mkdir()
    v15._write_start_marker(root, 100.0)

    assert not v15._marker_should_rescue(root, "running", now=134.9)
    assert v15._marker_should_rescue(root, "running", now=135.0)
    assert not v15._marker_should_rescue(root, "complete", now=999.0)


def test_v15_removes_historical_two_minute_false_failure():
    html = "before " + v15._LEGACY_TWO_MINUTE_FAILURE + " after"
    patched = v15._patch_legacy_timeout(html, 42)

    assert "La consolidation dépasse 2 minutes" not in patched
    assert "Finalisation prolongée" in patched
    assert "/matches/42/analysis/result" in patched
    assert "rescueAttempt<60" in patched
