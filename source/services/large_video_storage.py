"""S3-compatible object storage for resumable large video uploads.

The browser uploads directly to the private bucket via short-lived presigned
UploadPart URLs; Render receives only JSON metadata, never 5 GB of video bytes.
Cloudflare R2 and standard AWS S3 endpoints use the same multipart protocol.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException

MIB = 1024 * 1024
PART_BYTES = 16 * MIB
MAX_GB = max(1, min(20, int(os.getenv("AQUAMETRIC_MAX_CLOUD_VIDEO_GB", "5"))))
MAX_BYTES = MAX_GB * 1024**3
OWNER_QUOTA_GB = max(MAX_GB, int(os.getenv("AQUAMETRIC_MAX_USER_CLOUD_GB", "10")))
OWNER_QUOTA_BYTES = OWNER_QUOTA_GB * 1024**3
VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".m4v": "video/x-m4v",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
}


def object_storage_configured() -> bool:
    return all(os.getenv(key, "").strip() for key in (
        "AQUAMETRIC_OBJECT_BUCKET",
        "AQUAMETRIC_OBJECT_ENDPOINT",
        "AQUAMETRIC_OBJECT_ACCESS_KEY",
        "AQUAMETRIC_OBJECT_SECRET_KEY",
    ))


def durable_match_metadata() -> bool:
    # S3 persists the pixels, not the match/upload ID. An ephemeral Render
    # SQLite file would lose the user's 3 GB video association after sleep.
    url = os.getenv("DATABASE_URL", "").strip().lower()
    return url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")) or (
        os.getenv("AQUAMETRIC_PERSISTENT_UPLOAD_METADATA", "") == "1"
    )


def configured() -> bool:
    return object_storage_configured() and durable_match_metadata()


def capabilities() -> dict:
    enabled = configured()
    if enabled:
        reason = ""
    elif not object_storage_configured():
        reason = "Stockage cloud privé R2/S3 non configuré. L'administrateur doit connecter un bucket."
    else:
        reason = "Base des matchs non persistante. Configurer PostgreSQL ou un disque persistant pour ne pas perdre les vidéos à un redémarrage Render."
    return {
        "enabled": enabled, "max_bytes": MAX_BYTES,
        "max_gb": MAX_GB, "part_bytes": PART_BYTES,
        "resume_supported": enabled, "reason": reason,
    }


def bucket() -> str:
    if not configured():
        raise HTTPException(503, "Envoi de gros fichiers indisponible : configurer un bucket privé R2/S3 ET une base de données persistante.")
    return os.environ["AQUAMETRIC_OBJECT_BUCKET"].strip()


def client():
    bucket()
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=os.environ["AQUAMETRIC_OBJECT_ENDPOINT"].strip(),
        aws_access_key_id=os.environ["AQUAMETRIC_OBJECT_ACCESS_KEY"].strip(),
        aws_secret_access_key=os.environ["AQUAMETRIC_OBJECT_SECRET_KEY"].strip(),
        region_name=os.getenv("AQUAMETRIC_OBJECT_REGION", "auto"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      retries={"max_attempts": 3, "mode": "standard"}),
    )


def allowed_video(filename: str) -> tuple[str, str]:
    name = Path((filename or "").replace("\\", "/")).name[:150]
    suffix = Path(name).suffix.lower()
    if suffix not in VIDEO_MIME or not name or len(name) < 5:
        raise HTTPException(400, "Format vidéo non autorisé. Utiliser MP4, MOV, M4V, WebM ou MKV.")
    return name, VIDEO_MIME[suffix]


def list_uploaded_parts(api, *, key: str, upload_id: str) -> list[dict]:
    """Read all S3 parts; do not trust client-reported completion or ETags."""
    parts = []
    marker = 0
    while True:
        params = {"Bucket": bucket(), "Key": key, "UploadId": upload_id, "MaxParts": 1000}
        if marker:
            params["PartNumberMarker"] = marker
        result = api.list_parts(**params)
        for row in result.get("Parts", []):
            parts.append({"PartNumber": int(row["PartNumber"]), "ETag": row["ETag"], "Size": int(row["Size"])})
        if not result.get("IsTruncated"):
            break
        next_marker = int(result.get("NextPartNumberMarker") or 0)
        if next_marker <= marker:
            raise HTTPException(502, "Réponse incomplète du stockage de fichiers.")
        marker = next_marker
    return sorted(parts, key=lambda item: item["PartNumber"])


def signed_video_url(key: str) -> str:
    return client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket(), "Key": key,
                "ResponseContentDisposition": "inline"},
        ExpiresIn=3600,
    )


def is_missing_object_error(exc: Exception) -> bool:
    # Standard S3 / R2 head_object missing-key codes.
    code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
    return str(code) in {"404", "NoSuchKey", "NotFound"}
