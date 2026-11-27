"""Bounded local vision pass for the native analysis pipeline.

Outputs are candidate evidence only. A digest binds the input bytes at execution;
report readers still do not re-hash media, and no sporting event is created.
"""
from hashlib import sha256
from pathlib import Path
import cv2
from services.local_clip_scan import scan_clip
from services.vision_scan_evidence import save_scan, report, export_scans

MODES = ('baseline', 'head_flow_supported')
POLICY = 'bounded-local-scan-v1'


def fingerprint(path):
    path = Path(path)
    before = path.stat()
    h = sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Source changed during hashing')
    return h.hexdigest(), (after.st_size, after.st_mtime_ns)


def plan(total, count=4):
    if type(total) is not int or total < 1 or type(count) is not int or not 1 <= count <= 12:
        raise ValueError('Invalid scan plan')
    length = min(75, total)
    return [(s, length) for s in sorted({round((i+0.5) * (total-length) / count) for i in range(count)})]


def run(db, match, path, *, window_count=4):
    path = Path(path)
    if match.video_source != 'upload' or path.name != Path(match.video_path).name:
        raise ValueError('Local upload binding required')
    sha, stat = fingerprint(path)
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError('Unreadable video')
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        cap.release()
    windows = plan(total, window_count)
    existing = {}
    for row in export_scans(db, match, report(db, match)):
        r = row['result']
        if row['segment_id'] is None and r.get('source_sha256_at_execution') == sha and r.get('batch_policy') == POLICY:
            existing[(r.get('first_frame'), r.get('end_frame_exclusive'), r.get('tracking_mode'))] = row['id']
    ids = []; failed = []; reused = 0
    for start, n in windows:
        for mode in MODES:
            key = (start, start+n, mode)
            if key in existing:
                ids.append(existing[key]); reused += 1; continue
            try:
                result = scan_clip(path, start, n, tracking_mode=mode)
                now = path.stat()
                if (now.st_size, now.st_mtime_ns) != stat:
                    raise ValueError('Source changed during scan')
                result.update(source_sha256_at_execution=sha, batch_policy=POLICY)
                ids.append(save_scan(db, match, None, 'tracklets', result, path).id)
            except (OSError, ValueError, cv2.error) as exc:
                failed.append({'first_frame':start,'mode':mode,'error':type(exc).__name__})
    return {'status':'experimental_partial' if ids else 'unavailable','policy':POLICY,
            'source_sha256_at_execution':sha,'planned_windows':len(windows),'planned_runs':len(windows)*len(MODES),
            'persisted_ids':ids,'reused_runs':reused,'failed':failed,'statistical_use_allowed':False}
