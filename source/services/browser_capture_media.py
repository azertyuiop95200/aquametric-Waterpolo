"""Media normalization and verified frame access for analysis videos.

Browser-produced WebM files can expose plausible metadata while still being
unreliable for random seeks in OpenCV.  AquaMetric's analysis stack samples
frames throughout a match, so metadata alone is not a sufficient readiness
check.  This module therefore validates actual decoded frames before allowing a
source to bypass normalization.
"""
from __future__ import annotations

import json
import math
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


def opencv_readability(path: Path, duration_hint: float = 0.0) -> dict:
    """Verify that OpenCV can decode frames across the timeline.

    A successful ``ffprobe`` is not enough for MediaRecorder WebM and some MOV /
    variable-frame-rate files.  We deliberately test real random seeks because
    Vision and OCR use the same access pattern.
    """
    try:
        import cv2
    except Exception:
        return {"ok": False, "checked": False, "decoded": 0, "attempted": 0, "seekable": False}

    path = Path(path)
    if not path.exists() or path.stat().st_size <= 0:
        return {"ok": False, "checked": True, "decoded": 0, "attempted": 0, "seekable": False}

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        return {"ok": False, "checked": True, "decoded": 0, "attempted": 1, "seekable": False}

    try:
        duration = max(0.0, float(duration_hint or 0.0))
        if duration <= 0:
            fps = _float(cap.get(cv2.CAP_PROP_FPS))
            frames = _float(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if fps > 0 and frames > 0:
                duration = frames / fps

        positions = [0.0]
        if duration > 1.0:
            safe_end = max(0.0, duration - 0.35)
            positions.extend([
                min(safe_end, duration * 0.18),
                min(safe_end, duration * 0.50),
                min(safe_end, duration * 0.82),
            ])
        # Preserve order while removing duplicate positions on very short clips.
        positions = list(dict.fromkeys(round(max(0.0, p), 3) for p in positions))

        decoded = 0
        seek_decoded = 0
        for idx, second in enumerate(positions):
            if second > 0:
                cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
            ok, frame = cap.read()
            valid = bool(ok and frame is not None and getattr(frame, "size", 0) > 0)
            if valid:
                decoded += 1
                if idx > 0:
                    seek_decoded += 1

        attempted = len(positions)
        required = 1 if attempted == 1 else max(2, int(math.ceil(attempted * 0.60)))
        seekable = attempted == 1 or seek_decoded >= max(1, len(positions) - 2)
        return {
            "ok": decoded >= required and seekable,
            "checked": True,
            "decoded": decoded,
            "attempted": attempted,
            "seekable": seekable,
        }
    except Exception:
        return {"ok": False, "checked": True, "decoded": 0, "attempted": 0, "seekable": False}
    finally:
        cap.release()


def read_frame_at(video_path: Path, second: float, capture=None):
    """Read one frame at ``second`` with a clean-open retry after a failed seek."""
    try:
        import cv2
    except Exception:
        return None

    target_ms = max(0.0, float(second or 0.0)) * 1000.0
    if capture is not None:
        try:
            capture.set(cv2.CAP_PROP_POS_MSEC, target_ms)
            ok, frame = capture.read()
            if ok and frame is not None and getattr(frame, "size", 0) > 0:
                return frame
        except Exception:
            pass

    retry = cv2.VideoCapture(str(video_path))
    if not retry.isOpened():
        retry.release()
        return None
    try:
        retry.set(cv2.CAP_PROP_POS_MSEC, target_ms)
        ok, frame = retry.read()
        if ok and frame is not None and getattr(frame, "size", 0) > 0:
            return frame
        return None
    finally:
        retry.release()


def _run(cmd: list[str], timeout: int = 120) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
        return True
    except Exception:
        return False


def _usable_file(path: Path) -> bool:
    """Reject empty/truncated outputs without excluding legitimate short clips."""
    try:
        return Path(path).exists() and Path(path).stat().st_size >= 4096
    except OSError:
        return False


def _verified_probe(path: Path) -> dict:
    probe = ffprobe_video(path)
    decoded = opencv_readability(path, probe.get("duration", 0.0))
    return {
        **probe,
        "decode_ok": bool(decoded.get("ok")),
        "seekable": bool(decoded.get("seekable")),
        "decode_checks": int(decoded.get("attempted") or 0),
        "decoded_checks": int(decoded.get("decoded") or 0),
    }


def normalize_browser_capture(
    source_path: Path,
    derived_dir: Path,
    *,
    fast_analysis: bool = False,
) -> tuple[Path, dict]:
    """Return a seekable, actually decoded video path plus probe metadata.

    1. Keep the source only when metadata *and real OpenCV seek/decode checks*
       are healthy.
    2. Remux with generated timestamps (no re-encoding).
    3. If remuxing is still not seekable, transcode to H.264/yuv420p.

    ``fast_analysis`` reduces frame-rate/encoding cost because Vision samples
    sparse frames and does not need a delivery-quality master file.
    """
    source_path = Path(source_path)
    derived_dir = Path(derived_dir)
    derived_dir.mkdir(parents=True, exist_ok=True)

    original = _verified_probe(source_path)
    if original.get("ok") and original.get("decode_ok"):
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
    if _run(remux_cmd, timeout=remux_timeout) and _usable_file(remuxed):
        probe = _verified_probe(remuxed)
        if probe.get("ok") and probe.get("decode_ok"):
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

    if _run(encode_cmd, timeout=encode_timeout) and _usable_file(encoded):
        probe = _verified_probe(encoded)
        if probe.get("ok") and probe.get("decode_ok"):
            return encoded, {**probe, "normalization": normalization}

    return source_path, {**original, "normalization": "failed_keep_original"}
