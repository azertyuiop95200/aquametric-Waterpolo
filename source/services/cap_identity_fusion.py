"""Conservative multi-frame cap identity candidates for AquaMetric.

This module never confirms a player. It fuses admissible per-frame readings into
review candidates, then applies a simultaneity constraint so one team+cap
identity cannot be assigned to two overlapping tracks.
"""
from collections import Counter, defaultdict
from math import isfinite

VERSION = "0.2.0"


def fuse(readings, roster, *, min_frames=3, min_score=.8, min_share=.8):
    """Fuse per-frame cap readings into one review candidate."""
    if min_frames < 2 or not 0 < min_score <= 1 or not .5 < min_share <= 1:
        raise ValueError("thresholds")
    frames = defaultdict(set)
    for r in readings:
        try:
            side, cap, score, frame = (r[k] for k in ("side", "cap", "score", "frame"))
        except (KeyError, TypeError) as exc:
            raise ValueError("invalid reading") from exc
        if type(frame) is not int or frame < 0 or not isinstance(score, (int, float)) or not isfinite(score) or not 0 <= score <= 1:
            raise ValueError("invalid reading")
        if score >= min_score and side in roster and cap in roster[side]:
            frames[frame].add((side, cap))

    votes = Counter(next(iter(v)) for v in frames.values() if len(v) == 1)
    n = len(frames)
    best = votes.most_common(1)
    key, count = best[0] if best else (None, 0)
    share = count / n if n else None
    accepted = key is not None and count >= min_frames and share >= min_share
    return {
        "candidate": key if accepted else None,
        "status": "review_candidate" if accepted else "unresolved",
        "frames": n,
        "support": count,
        "share": share,
        "conflicting_frames": sum(len(v) > 1 for v in frames.values()),
    }


def _overlap_seconds(a, b):
    try:
        a0, a1 = float(a["start_second"]), float(a["end_second"])
        b0, b1 = float(b["start_second"]), float(b["end_second"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid track interval") from exc
    if not all(isfinite(x) for x in (a0, a1, b0, b1)) or a1 < a0 or b1 < b0:
        raise ValueError("invalid track interval")
    return max(0.0, min(a1, b1) - max(a0, b0))


def _dominates(a, b, *, min_support_margin, min_share_margin):
    """Return True only when a has clearly stronger evidence than b."""
    for row in (a, b):
        if not isinstance(row.get("support"), int) or row["support"] < 0:
            raise ValueError("invalid support")
        share = row.get("share")
        if share is None or not isinstance(share, (int, float)) or not isfinite(share) or not 0 <= share <= 1:
            raise ValueError("invalid share")
    support_win = a["support"] >= b["support"] + min_support_margin and a["share"] >= b["share"]
    share_win = a["share"] >= b["share"] + min_share_margin and a["support"] >= b["support"]
    return support_win or share_win


def enforce_unique_candidates(
    tracks,
    *,
    min_overlap_s=.001,
    min_support_margin=2,
    min_share_margin=.10,
):
    """Reject simultaneous duplicate assignments of the same team+cap.

    Candidate tracks survive only if they clearly dominate every overlapping
    rival carrying the same identity. Ties remain unresolved. Opposing teams
    may use the same cap number and non-overlapping fragments may reuse an
    identity. Input rows are never mutated.
    """
    if not isfinite(min_overlap_s) or min_overlap_s < 0:
        raise ValueError("invalid overlap threshold")
    if type(min_support_margin) is not int or min_support_margin < 1:
        raise ValueError("invalid support margin")
    if not isfinite(min_share_margin) or not 0 < min_share_margin <= 1:
        raise ValueError("invalid share margin")

    rows = [dict(t) for t in tracks]
    seen_ids = set()
    for row in rows:
        tid = row.get("track_id")
        if tid is None or tid in seen_ids:
            raise ValueError("track_id must be unique")
        seen_ids.add(tid)
        _overlap_seconds(row, row)
        if row.get("candidate") is not None:
            cand = row["candidate"]
            if not isinstance(cand, (tuple, list)) or len(cand) != 2:
                raise ValueError("invalid candidate")
            row["candidate"] = tuple(cand)
            _dominates(row, row, min_support_margin=min_support_margin, min_share_margin=min_share_margin)

    conflicts = defaultdict(list)
    participating = [r for r in rows if r.get("candidate") is not None]
    for i, a in enumerate(participating):
        for b in participating[i + 1:]:
            if a["candidate"] != b["candidate"]:
                continue
            overlap = _overlap_seconds(a, b)
            if overlap < min_overlap_s or overlap <= 0:
                continue
            conflicts[a["track_id"]].append((b, overlap))
            conflicts[b["track_id"]].append((a, overlap))

    by_id = {r["track_id"]: r for r in rows}
    audit = {tid: [] for tid in conflicts}
    rejected = set()
    for tid, rivals in conflicts.items():
        row = by_id[tid]
        for rival, overlap in rivals:
            if _dominates(row, rival, min_support_margin=min_support_margin, min_share_margin=min_share_margin):
                decision = "wins"
            elif _dominates(rival, row, min_support_margin=min_support_margin, min_share_margin=min_share_margin):
                decision = "loses"
                rejected.add(tid)
            else:
                decision = "tie"
                rejected.add(tid)
            audit[tid].append({
                "other_track_id": rival["track_id"],
                "overlap_seconds": round(overlap, 6),
                "decision": decision,
            })

    for row in rows:
        tid = row["track_id"]
        row["identity_conflicts"] = audit.get(tid, [])
        row["identity_conflict_count"] = len(row["identity_conflicts"])
        if tid in rejected:
            row["candidate_before_uniqueness"] = row.get("candidate")
            row["candidate"] = None
            row["status"] = "identity_collision"
        elif row.get("candidate") is not None:
            row["status"] = "review_candidate"

    return {
        "tracks": rows,
        "conflict_pairs": sum(len(v) for v in conflicts.values()) // 2,
        "rejected_tracks": len(rejected),
        "remaining_candidates": sum(r.get("candidate") is not None for r in rows),
    }
