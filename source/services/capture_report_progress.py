"""Owner-scoped report progress without exposing capture tokens or paths."""
from __future__ import annotations

import json
import time
from pathlib import Path


def latest_capture_root(match, base: Path | None = None) -> Path | None:
    if base is None:
        from analysis_product_routes import CAPTURE_SESSION_ROOT
        base = CAPTURE_SESSION_ROOT
    roots = []
    for path in Path(base).glob(f"u{int(match.owner_id)}_m{int(match.id)}_*"):
        token = path.name.rsplit("_", 1)[-1]
        if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
            continue
        try:
            roots.append(((path / "progress.json").stat().st_mtime, path))
        except OSError:
            pass
    return max(roots, default=(0, None), key=lambda row: row[0])[1]


def report_progress(match, *, root: Path | None = None, now: float | None = None) -> dict:
    root = root or latest_capture_root(match)
    result = {"active": False, "enrichment_status": "", "media_status": "", "media_clips": 0,
              "media_targets": 0, "retry_available": False, "stale": False, "revision": ""}
    if root is None:
        return result
    try:
        state = json.loads((root / "progress.json").read_text(encoding="utf-8"))
        marker_path = root / ".v16-report-ready.json"
        marker = json.loads(marker_path.read_text(encoding="utf-8")) if marker_path.exists() else {}
        # Terminal OCR markers win over delayed upload progress; clip progress
        # is written only to progress.json after the verifier has finished.
        enrichment = marker.get("enrichment_status") or state.get("enrichment_status", "")
        media = state.get("media_status", "")
        updated = float(state.get("media_updated_at") or state.get("v16_report_published_at")
                        or (root / "progress.json").stat().st_mtime)
        stale = (time.time() if now is None else now) - updated > 600
        active = not stale and (enrichment in {"queued", "running"} or media in {"queued", "running"})
        result.update(active=active, enrichment_status=enrichment, media_status=media,
                      media_clips=int(state.get("media_clips") or 0),
                      media_targets=int(state.get("media_targets") or 0), stale=stale,
                      retry_available=not active and (root / "capture.webm").is_file())
        result["revision"] = json.dumps([enrichment, media, result["media_clips"], stale,
                                        marker.get("scoreboard_observations", 0)], separators=(",", ":"))
    except (OSError, ValueError, TypeError):
        pass
    return result
