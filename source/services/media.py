from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path


class MediaGenerationError(RuntimeError):
    pass


@dataclass
class GeneratedMedia:
    filename: str
    mime_type: str
    start_second: float
    end_second: float


def ffmpeg_executable() -> str | None:
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def ffmpeg_available() -> bool:
    return ffmpeg_executable() is not None


def _run_ffmpeg(args: list[str], timeout: int = 180) -> None:
    executable = ffmpeg_executable()
    if not executable:
        raise MediaGenerationError("FFmpeg is not available on this server.")
    proc = subprocess.run(
        [executable, "-hide_banner", "-loglevel", "error", "-y", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        message = (proc.stderr or "FFmpeg could not process this video.").strip()
        raise MediaGenerationError(message[-1200:])


def create_screenshot(video_path: Path, output_dir: Path, second: float) -> GeneratedMedia:
    output_dir.mkdir(parents=True, exist_ok=True)
    second = max(0.0, float(second))
    filename = f"shot_{uuid.uuid4().hex}.jpg"
    target = output_dir / filename
    _run_ffmpeg([
        "-ss", f"{second:.3f}",
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(target),
    ])
    if not target.exists() or target.stat().st_size == 0:
        raise MediaGenerationError("No screenshot was produced for this timestamp.")
    return GeneratedMedia(filename, "image/jpeg", second, second)


def create_clip(
    video_path: Path,
    output_dir: Path,
    second: float,
    before: float = 4.0,
    after: float = 6.0,
) -> GeneratedMedia:
    output_dir.mkdir(parents=True, exist_ok=True)
    second = max(0.0, float(second))
    before = min(max(float(before), 0.0), 30.0)
    after = min(max(float(after), 0.5), 45.0)
    start = max(0.0, second - before)
    duration = min(before + after, 60.0)
    end = start + duration
    filename = f"clip_{uuid.uuid4().hex}.mp4"
    target = output_dir / filename
    _run_ffmpeg([
        "-ss", f"{start:.3f}",
        "-i", str(video_path),
        "-t", f"{duration:.3f}",
        "-map", "0:v:0",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "24",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(target),
    ], timeout=300)
    if not target.exists() or target.stat().st_size == 0:
        raise MediaGenerationError("No video clip was produced for this timestamp.")
    return GeneratedMedia(filename, "video/mp4", start, end)
