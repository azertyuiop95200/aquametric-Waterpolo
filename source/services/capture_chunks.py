"""Idempotent, serialized capture uploads with crash-recoverable append receipts."""
import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path
from fastapi import HTTPException


def _publish(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as out:
        out.write(value)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def append_capture_chunk(root: Path, index: int, upload, writer):
    """A lost HTTP response may retry an index; only identical bytes are accepted.

    A receipt precedes the append. If a process dies before advancing the
    counter, the next retry truncates the partial append and writes it again.
    flock serializes requests across threads and server processes on Render.
    """
    try:
        if not root.is_dir() or not (root / "next_index.txt").exists():
            raise HTTPException(404, "Capture session expired or not found.")
        with (root / ".chunks.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state_file = root / "next_index.txt"
            try:
                expected = int(state_file.read_text().strip())
            except ValueError:
                raise HTTPException(409, "Capture session state is invalid.")
            if index < 0 or index > expected:
                raise HTTPException(409, f"Capture chunk out of order: expected {expected}, got {index}.")
            target = root / "capture.webm"
            size = target.stat().st_size if target.exists() else 0
            receipt_path = root / f"chunk-{index}.json"
            receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
            if index < expected and receipt is None:
                raise HTTPException(409, "Old capture chunk cannot be verified; restart capture.")
            offset = receipt["offset"] if receipt else size
            # Validate the whole upload before touching the assembled video.
            with tempfile.TemporaryDirectory(dir=root, prefix=".chunk-") as tmp:
                staged = Path(tmp) / "data"
                written = writer(upload, staged, current_size=offset)
                if written <= 0:
                    raise HTTPException(400, "Empty capture chunk.")
                with staged.open("rb") as source:
                    digest = hashlib.file_digest(source, "sha256").hexdigest()
                if receipt and (receipt["sha256"] != digest or receipt["size"] != written):
                    raise HTTPException(409, "Capture chunk retry contains different data.")
                if index < expected:
                    return {"ok": True, "next_index": expected, "bytes": size, "duplicate": True}
                _publish(receipt_path, json.dumps({"offset": offset, "size": written, "sha256": digest}))
                with target.open("r+b" if target.exists() else "w+b") as out, staged.open("rb") as src:
                    out.truncate(offset)
                    out.seek(offset)
                    while data := src.read(1024 * 1024):
                        out.write(data)
                    out.flush()
                    os.fsync(out.fileno())
                _publish(state_file, str(expected + 1))
                return {"ok": True, "next_index": expected + 1, "bytes": offset + written, "duplicate": False}
    finally:
        upload.file.close()
