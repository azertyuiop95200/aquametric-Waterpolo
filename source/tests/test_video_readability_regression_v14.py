import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

import services.browser_capture_media as media


def _probe_ok() -> dict:
    return {
        "ok": True,
        "duration": 120.0,
        "width": 1920,
        "height": 1080,
        "fps": 25.0,
    }


def test_metadata_does_not_bypass_failed_decode_check(monkeypatch, tmp_path: Path):
    """A duration/size from ffprobe must not imply random-seek readability."""
    source = tmp_path / "metadata-only.webm"
    source.write_bytes(b"x" * 8192)

    monkeypatch.setattr(media, "ffprobe_video", lambda _path: _probe_ok())
    monkeypatch.setattr(
        media,
        "opencv_readability",
        lambda _path, _duration=0.0: {
            "ok": False,
            "checked": True,
            "decoded": 1,
            "attempted": 4,
            "seekable": False,
        },
    )
    monkeypatch.setattr(media.shutil, "which", lambda _name: None)

    normalized, info = media.normalize_browser_capture(source, tmp_path / "derived")

    assert normalized == source
    assert info["normalization"] == "ffmpeg_unavailable"
    assert info["decode_ok"] is False
    assert info["seekable"] is False


def test_verified_decode_can_keep_original(monkeypatch, tmp_path: Path):
    source = tmp_path / "healthy.mp4"
    source.write_bytes(b"x" * 8192)

    monkeypatch.setattr(media, "ffprobe_video", lambda _path: _probe_ok())
    monkeypatch.setattr(
        media,
        "opencv_readability",
        lambda _path, _duration=0.0: {
            "ok": True,
            "checked": True,
            "decoded": 4,
            "attempted": 4,
            "seekable": True,
        },
    )

    normalized, info = media.normalize_browser_capture(source, tmp_path / "derived")

    assert normalized == source
    assert info["normalization"] == "not_needed"
    assert info["decode_ok"] is True
    assert info["decoded_checks"] == 4
