"""Export only hash-matched files in the private, match/revision-scoped proof store."""
from hashlib import sha256
from pathlib import Path
from services.review_reference_import import load


def collect(match, evidence_dir, *, byte_limit=100*1024*1024):
    root = Path(evidence_dir).resolve()
    links, files = {}, {}
    used = 0
    for ref in match.review_references:
        try:
            payload, _, digest, period = load(ref.payload_json.encode())
        except (ValueError, TypeError, AttributeError):
            continue
        if digest != ref.digest or period != ref.period:
            continue
        base = root / 'review_references' / str(match.id) / digest
        if base.resolve() != base:
            continue
        by_event = links.setdefault(digest,{})
        for row in payload['reference'].get('evidence_manifest') or []:
            rel = row['path']
            dest = f'03_events/review_proofs/Q{period}_{digest}/{rel}'
            if dest not in files:
                path = base / rel
                try:
                    if path.resolve() != path or not path.is_file() or path.stat().st_size != row['bytes'] or used+row['bytes']>byte_limit:
                        continue
                    with path.open("rb") as f:
                        data = f.read(row["bytes"]+1)
                except OSError:
                    continue
                if len(data)!=row['bytes'] or sha256(data).hexdigest()!=row['sha256']:
                    continue
                files[dest]=data
                used+=len(data)
            by_event.setdefault(row['id'],[]).append('../'+dest)
    return links, files
