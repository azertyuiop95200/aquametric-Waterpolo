"""Collision-safe persistence for concurrent browser-capture progress updates."""
from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path


def write_state_atomic(root: Path, state: dict) -> None:
    """Atomically publish progress JSON without sharing a temporary filename.

    Browser capture uploads video chunks while Vision frames are analysed in
    parallel.  Multiple requests can therefore write progress at the same time.
    A fixed ``progress.tmp`` lets one writer rename/delete another writer's temp
    file, producing a FileNotFoundError and HTTP 500.  A per-write temp name in
    the same directory keeps ``os.replace`` atomic while removing that race.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "progress.json"
    tmp = root / (
        f".progress.{os.getpid()}.{threading.get_ident()}."
        f"{secrets.token_hex(6)}.tmp"
    )
    try:
        payload = json.dumps(state, ensure_ascii=False)
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
