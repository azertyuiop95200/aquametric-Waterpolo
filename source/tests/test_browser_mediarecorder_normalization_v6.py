import os
import shutil
import subprocess
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aquametric.db")

import cv2

from services.browser_capture_media import ffprobe_video, normalize_browser_capture


def _make_streaming_webm(path: Path, seconds: int = 4) -> None:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "ffmpeg required"
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=20:duration={seconds}",
        "-c:v", "libvpx-vp9", "-b:v", "900k", "-an",
        # live/webm intentionally resembles a MediaRecorder stream whose duration
        # metadata can be missing or less seek-friendly than an ordinary ffmpeg file.
        "-f", "webm", "-live", "1", str(path),
    ]
    subprocess.run(cmd, check=True, timeout=60)
    assert path.exists() and path.stat().st_size > 64 * 1024


def test_streaming_webm_is_normalized_to_seekable_video(tmp_path):
    source = tmp_path / "mediarecorder-like.webm"
    _make_streaming_webm(source)
    original_probe = ffprobe_video(source)

    normalized, info = normalize_browser_capture(source, tmp_path / "derived")
    assert normalized.exists()
    assert info["normalization"] in {"not_needed", "remux_genpts", "reencode_h264"}
    assert info["duration"] > 3.0
    assert info["width"] == 640
    assert info["height"] == 360

    cap = cv2.VideoCapture(str(normalized))
    assert cap.isOpened()
    cap.set(cv2.CAP_PROP_POS_MSEC, 2500)
    ok, frame = cap.read()
    cap.release()
    assert ok and frame is not None
    assert frame.shape[1] == 640
    assert frame.shape[0] == 360

    # Keep the original probe in the assertion path: this test remains useful
    # whether this ffmpeg build writes duration for live WebM or not.
    assert isinstance(original_probe["ok"], bool)
