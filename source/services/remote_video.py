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


def _download_direct(url: str, temp_dir: Path) -> Path:
    target = temp_dir / "source.mp4"
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if content_type and not (content_type.startswith("video/") or "octet-stream" in content_type):
            raise RemoteVideoError(f"Remote URL did not return video content ({content_type}).")
        with target.open("wb") as handle:
            for chunk in response.iter_bytes(1024 * 1024):
                if chunk:
                    handle.write(chunk)
    if not target.exists() or target.stat().st_size < 1024:
        raise RemoteVideoError("Remote video is empty or too small.")
    return target


def _yt_dlp_attempt(url: str, temp_dir: Path, *, player_client: str) -> tuple[Path | None, str]:
    output_template = str(temp_dir / f"source_{player_client}.%(ext)s")
    provider_home = "/root/bgutil-ytdlp-pot-provider/server"
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-progress",
        "--no-warnings",
        "--socket-timeout", "30",
        "--retries", "2",
        "--fragment-retries", "2",
        "--js-runtimes", "node",
        "--extractor-args", f"youtube:player_client={player_client}",
        "--extractor-args", f"youtubepot-bgutilscript:server_home={provider_home}",
        "--format", "best[height<=720][ext=mp4]/best[height<=720]/best",
        "--merge-output-format", "mp4",
        "--output", output_template,
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240, check=False)
    except subprocess.TimeoutExpired as exc:
        return None, f"{player_client}: extraction timed out after 240 seconds ({exc})."
    except OSError as exc:
        return None, f"{player_client}: yt-dlp could not start ({exc})."

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "remote extractor failed").strip()
        return None, f"{player_client}: {detail[-900:]}"

    candidates = sorted(
        p for p in temp_dir.glob(f"source_{player_client}.*")
        if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
    )
    if not candidates:
        return None, f"{player_client}: extractor completed but produced no playable file."
    best = max(candidates, key=lambda p: p.stat().st_size)
    if best.stat().st_size < 1024:
        return None, f"{player_client}: produced file is empty or too small."
    return best, ""


def materialize_remote_video(url: str, work_dir: Path) -> Path:
    """Materialize an accessible third-party video only for analysis duration.

    The transient source is never exposed as an AquaMetric download or stored as
    match evidence. YouTube datacenter requests use the current yt-dlp JavaScript
    challenge runtime plus a local PO-token provider and several player clients.
    """
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RemoteVideoError("Unsupported remote video URL.")

    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="aquametric_url_", dir=root))

    try:
        if _direct_video_url(url):
            return _download_direct(url, temp_dir)

        errors: list[str] = []
        for client in ("mweb", "web_embedded", "tv"):
            path, error = _yt_dlp_attempt(url, temp_dir, player_client=client)
            if path:
                return path
            if error:
                errors.append(error)

        raise RemoteVideoError(
            "YouTube/remote extraction failed before Vision could read any frame. "
            + (" | ".join(errors[-3:]) or "No playable stream was produced.")
        )
    except RemoteVideoError:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RemoteVideoError(f"Remote video materialisation failed: {exc}") from exc


def cleanup_remote_video(path: Path | None) -> None:
    if not path:
        return
    try:
        p = Path(path)
        parent = p.parent
        if parent.name.startswith("aquametric_url_"):
            shutil.rmtree(parent, ignore_errors=True)
        elif p.exists():
            p.unlink(missing_ok=True)
    except Exception:
        pass
