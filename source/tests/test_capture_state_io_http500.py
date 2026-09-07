from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json

from services.capture_state_io import write_state_atomic


def test_concurrent_progress_writes_do_not_share_temp_file(tmp_path: Path):
    root = tmp_path / "session"

    def write(i: int) -> None:
        write_state_atomic(root, {
            "status": "running",
            "chunks": i,
            "analysis_percent": float(i),
        })

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(write, range(1, 81)))

    progress = root / "progress.json"
    assert progress.exists()
    payload = json.loads(progress.read_text(encoding="utf-8"))
    assert payload["status"] == "running"
    assert 1 <= int(payload["chunks"]) <= 80
    assert not list(root.glob(".progress.*.tmp"))
