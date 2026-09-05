from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx


class RemoteVideoError(RuntimeError):
    pass


def _direct_video_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"))


def materialize_remote_video(url: str, work_dir: Path) -> Path:
    """Materialize a public video URL into a temporary local file for analysis.

    The caller owns cleanup. The file is strictly transient and should never be
    exposed as an AquaMetric download or persisted as evidence.
    """
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RemoteVideoError("Unsupported remote video URL.")

    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="aquametric_url_", dir=root))

    try:
        if _direct_video_url(url):
            target = temp_dir / "source.mp4"
            with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "").lower()
                if content_type and not (content_type.startswith("video/") or "octet-stream" in content_type):
                    raise RemoteVideoError(f"Remote URL did not return video content ({content_type}).")
                with target.open("wb") as handle:
                    for chunk in response.iter_bytes(1024 * 1024):
                        handle.write(chunk)
            if target.stat().st_size < 1024:
                raise RemoteVideoError("Remote video is empty or too small.")
            return target

        output_template = str(temp_dir / "source.%(ext)s")
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--no-progress",
            "--quiet",
            "--no-warnings",
            "--socket-timeout", "30",
            "--retries", "2",
            "--format", "best[ext=mp4]/best",
            "--output", output_template,
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "remote extractor failed").strip()[-500:]
            raise RemoteVideoError(detail)
        candidates = sorted(temp_dir.glob("source.*"))
        if not candidates:
            raise RemoteVideoError("No playable video was produced from the URL.")
        return candidates[0]
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def cleanup_remote_video(path: Path | None) -> None:
    if not path:
        return
    try:
        parent = Path(path).parent
        if parent.name.startswith("aquametric_url_"):
            shutil.rmtree(parent, ignore_errors=True)
        elif Path(path).exists():
            Path(path).unlink(missing_ok=True)
    except Exception:
        pass
