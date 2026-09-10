"""Clean evidence-first match report.

The UI must never turn absence of evidence into a sporting zero. Only verified
Event rows are shown as measured counts; Vision/OCR candidates are clearly
separate and all other values render as non measured.
"""
from __future__ import annotations

from collections import Counter

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from db import get_db
from analysis_product_routes import TEMPLATES, _owned_match
from services.analysis_product import analysis_snapshot, youtube_segment_embed
from services.deep_analysis_sequences import sequence_gallery, sequence_summary
from services.video import youtube_embed


def _verified_side(events: list[dict], perspective: str) -> dict:
    side = [row for row in events if row.get("perspective") == perspective]
    counts = Counter(str(row.get("event_type") or "") for row in side)

    def measured(event_types):
        value = sum(counts.get(kind, 0) for kind in event_types)
        return value if value > 0 else None

    return {
        "goals": measured({"goal"}),
        "shots": measured({"shot_on_target", "shot_off_target", "shot_blocked"}),
        "saves": measured({"save"}),
        "turnovers": measured({"turnover", "bad_pass"}),
        "recoveries": measured({"recovery", "interception"}),
        "exclusions_earned": measured({"exclusion_earned"}),
        "exclusions_committed": measured({"exclusion", "exclusion_committed"}),
        "assists": measured({"assist"}),
        "key_passes": measured({"key_pass"}),
        "verified_events": len(side),
    }


def _period_rows(snapshot: dict) -> list[dict]:
    rows = []
    for index, raw in enumerate(snapshot.get("automatic", {}).get("periods", []) or [], start=1):
        if isinstance(raw, dict):
            rows.append({
                "label": raw.get("label") or raw.get("period") or raw.get("name") or f"P{index}",
                "start": raw.get("start_second", raw.get("start")),
                "end": raw.get("end_second", raw.get("end")),
                "confidence": raw.get("confidence_label") or raw.get("confidence") or "candidat",
            })
        else:
            rows.append({"label": f"P{index}", "start": None, "end": None, "confidence": "candidat"})
    return rows


def clean_analysis_result(match_id: int, request: Request, db: Session = Depends(get_db)):
    user, match = _owned_match(match_id, request, db)
    snapshot = analysis_snapshot(db, match)
    events = list(snapshot.get("verified_events") or [])
    sequences = sequence_gallery(db, match, max_total=72)
    source_embed = youtube_embed(match.video_url) if match.video_url else ""
    return TEMPLATES.TemplateResponse(
        request,
        "analysis_result_clean_v2.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "match": match,
            "snapshot": snapshot,
            "vision": snapshot.get("vision") or {},
            "automatic": snapshot.get("automatic") or {},
            "for_verified": _verified_side(events, "for"),
            "against_verified": _verified_side(events, "against"),
            "period_rows": _period_rows(snapshot),
            "sequences": sequences,
            "sequence_summary": sequence_summary(sequences),
            "source_embed": source_embed,
            "category": getattr(match.team, "category", "") or "Non précisée",
        },
    )


def download_analysis_report(match_id: int, request: Request, db: Session = Depends(get_db)):
    """Portable report rebuilt from the authenticated owner's saved evidence."""
    from datetime import datetime, timezone
    user, match = _owned_match(match_id, request, db)
    snapshot = analysis_snapshot(db, match)
    return TEMPLATES.TemplateResponse(request, 'analysis_report_portable.html', {
        'match': match, 'snapshot': snapshot,
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'for_verified': _verified_side(snapshot['verified_events'], 'for'),
        'against_verified': _verified_side(snapshot['verified_events'], 'against'),
    }, headers={'Content-Disposition': f'attachment; filename="rapport-match-{match.id}.html"',
                'Cache-Control': 'private, no-store'})
