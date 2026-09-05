from __future__ import annotations

from pathlib import Path


class RemoteVideoError(RuntimeError):
    pass


def materialize_remote_video(url: str, work_dir: Path) -> Path:
    """Reject server-side materialisation of third-party video URLs.

    AquaMetric V12.2 treats remote players (YouTube and other third-party URLs) as
    reference media only: embed + exact timestamp/bookmark. Pixel analysis, OCR,
    screenshots and downloadable clips require a video file explicitly uploaded by
    the user. Keeping this guard in the legacy helper prevents an old route from
    silently reintroducing yt-dlp/cookie extraction.
    """
    del work_dir
    if not (url or "").strip().startswith(("http://", "https://")):
        raise RemoteVideoError("Unsupported remote video URL.")
    raise RemoteVideoError(
        "Les vidéos tierces sont en mode référence uniquement. "
        "Téléverse un fichier vidéo possédé pour l'analyse pixel/OCR et la génération de clips/images."
    )


def cleanup_remote_video(path: Path | None) -> None:
    """Compatibility no-op: V12.2 no longer materialises remote media."""
    del path
