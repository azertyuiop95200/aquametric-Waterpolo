"""Media normalization for real MediaRecorder browser captures.

Browser-produced WebM files are often decodable but omit reliable duration/cue
metadata. Analysis prefers a no-loss remux; only when that fails do we transcode.
The ``fast_analysis`` mode deliberately reduces frame-rate/encoding cost because
Vision samples sparse frames and does not need a delivery-quality master file.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def _float(value, default=0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return float(default)


def ffprobe_video(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not Path(path).exists():
        return {"ok": False, "duration": 0.0, "width": 0, "height": 0, "fps": 0.0}
    cmd = [
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,duration:format=duration",
        "-of", "json", str(path),
    ]
    try:
        raw = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True).stdout
        payload = json.loads(raw or "{}")
        streams = payload.get("streams") or [{}]
        stream = streams[0] if streams else {}
        duration = max(_float(stream.get("duration")), _float((payload.get("format") or {}).get("duration")))
        rate = str(stream.get("avg_frame_rate") or "0/1")
        num, den = (rate.split("/", 1) + ["1"])[:2] if "/" in rate else (rate, "1")
        fps = _float(num) / max(1e-9, _float(den, 1.0))
        return {
            "ok": duration > 0 and int(stream.get("width") or 0) > 0,
            "duration": duration,
            "width": int(stream.get("width") or 0),
            "height": int(stream.get("height") or 0),
            "fps": fps,
        }
    except Exception:
        return {"ok": False, "duration": 0.0, "width": 0, "height": 0, "fps": 0.0}


def _run(cmd: list[str], timeout: int = 120) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
        return True
    except Exception:
        return False


def normalize_browser_capture(
    source_path: Path,
    derived_dir: Path,
    *,
    fast_analysis: bool = False,
) -> tuple[Path, dict]:
    """Return a seekable video path plus probe metadata.

    1. Keep an already seekable source.
    2. Remux with generated timestamps (no re-encoding).
    3. If remuxing fails, transcode. In ``fast_analysis`` mode the fallback is
       intentionally analysis-oriented: 12 fps, <=1280 px, ultrafast H.264.
       This removes the old multi-minute 88% stall without lowering the source
       pixels used during the live pre-analysis pass.
    """
    source_path = Path(source_path)
    derived_dir = Path(derived_dir)
    derived_dir.mkdir(parents=True, exist_ok=True)
    original = ffprobe_video(source_path)
    if original.get("ok"):
        return source_path, {**original, "normalization": "not_needed"}

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return source_path, {**original, "normalization": "ffmpeg_unavailable"}

    remuxed = derived_dir / "capture-normalized.mkv"
    remux_cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-fflags", "+genpts+discardcorrupt", "-i", str(source_path),
        "-map", "0:v:0", "-an", "-c:v", "copy",
        "-avoid_negative_ts", "make_zero", str(remuxed),
    ]
    remux_timeout = 45 if fast_analysis else 90
    if _run(remux_cmd, timeout=remux_timeout) and remuxed.exists() and remuxed.stat().st_size > 64 * 1024:
        probe = ffprobe_video(remuxed)
        if probe.get("ok"):
            return remuxed, {**probe, "normalization": "remux_genpts"}

    encoded = derived_dir / "capture-normalized.mp4"
    encode_cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-fflags", "+genpts+discardcorrupt", "-i", str(source_path),
        "-map", "0:v:0", "-an",
    ]
    if fast_analysis:
        encode_cmd += [
            "-vf", "fps=12,scale=w=min(1280\\,iw):h=-2",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        ]
        encode_timeout = 90
        normalization = "reencode_h264_fast_analysis"
    else:
        encode_cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "25"]
        encode_timeout = 300
        normalization = "reencode_h264"
    encode_cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", str(encoded)]

    if _run(encode_cmd, timeout=encode_timeout) and encoded.exists() and encoded.stat().st_size > 64 * 1024:
        probe = ffprobe_video(encoded)
        if probe.get("ok"):
            return encoded, {**probe, "normalization": normalization}

    return source_path, {**original, "normalization": "failed_keep_original"}
