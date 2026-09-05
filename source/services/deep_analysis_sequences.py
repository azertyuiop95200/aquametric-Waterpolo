from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select

from models import (
    AutonomousAnalysis,
    AutonomousEventCandidate,
    MediaArtifact,
    VisionAnalysis,
    VisionSample,
)
from services.media import MediaGenerationError, create_clip, create_screenshot
from services.tactical_engine import analyze_match_tactics
from services.video import timestamped_video_url, youtube_embed


PRIORITY = {
    "verified": 0,
    "automatic": 1,
    "tactical": 2,
    "vision_peak": 3,
    "active_window": 4,
}

INTERESTING_EVENTS = {
    "goal", "assist", "key_pass", "action_created", "shot_on_target", "shot_off_target",
    "shot_blocked", "save", "block", "turnover", "bad_pass", "interception", "recovery",
    "exclusion_earned", "exclusion_committed", "penalty_earned", "penalty_committed",
    "duel_won", "duel_lost", "counterattack_start", "defensive_recovery_start",
    "fast_recovery", "late_recovery", "power_play_start", "penalty_kill_start",
}


def _safe_json(raw, fallback):
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, type(fallback)) else fallback
    except Exception:
        return fallback


def _latest(db, model, match_id: int):
    return db.scalar(
        select(model)
        .where(model.match_id == match_id)
        .order_by(model.created_at.desc(), model.id.desc())
    )


def _label(value: str) -> str:
    return (value or "séquence").replace("_", " ").strip().title()


def _confidence_value(value, default: float = 1.0) -> float:
    """Normalize numeric and historical text confidence values without crashing.

    Older AquaMetric datasets used labels such as CONFIRMED/HIGH/MEDIUM rather than
    numeric scores. They are evidence states, not measurements, so the mapping is
    deliberately conservative and bounded to [0, 1].
    """
    if value is None or value == "":
        return default
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        label = str(value).strip().upper()
        return {
            "CONFIRMED": 1.0,
            "VERIFIED": 1.0,
            "HIGH": 0.9,
            "HAUTE": 0.9,
            "MEDIUM": 0.72,
            "MOYENNE": 0.72,
            "LOW": 0.45,
            "FAIBLE": 0.45,
            "ESTIMATED": 0.55,
            "CANDIDATE": 0.5,
        }.get(label, default)


def _confidence_label(value: float) -> str:
    if value >= 0.86:
        return "HAUTE"
    if value >= 0.68:
        return "MOYENNE"
    return "FAIBLE"


def _window(second: float, before: float = 4.0, after: float = 6.0):
    second = max(0.0, float(second or 0))
    return max(0.0, second - before), second + after


def _target(
    *,
    kind: str,
    second: float,
    title: str,
    summary: str,
    confidence: float,
    event_id: int | None = None,
    phase: str = "",
    start_second: float | None = None,
    end_second: float | None = None,
    source: str = "",
):
    start, end = _window(second)
    if start_second is not None:
        start = max(0.0, float(start_second))
    if end_second is not None:
        end = max(start + 0.5, float(end_second))
    confidence = _confidence_value(confidence, 0.0)
    return {
        "key": f"{kind}:{event_id or 't'}:{float(second):.2f}",
        "kind": kind,
        "priority": PRIORITY.get(kind, 9),
        "event_id": event_id,
        "second": round(float(second), 2),
        "start_second": round(start, 2),
        "end_second": round(end, 2),
        "title": title,
        "summary": summary,
        "confidence": round(confidence, 3),
        "confidence_label": _confidence_label(confidence),
        "phase": phase or "",
        "source": source or kind,
        "aliases": [],
    }


def _dedupe_targets(rows: list[dict], *, min_gap: float = 1.2, max_total: int = 72) -> list[dict]:
    ranked = sorted(rows, key=lambda r: (r["priority"], -r["confidence"], r["second"]))
    kept: list[dict] = []
    for row in ranked:
        nearest = next((x for x in kept if abs(float(x["second"]) - float(row["second"])) <= min_gap), None)
        if nearest:
            if row["title"] != nearest["title"]:
                nearest["aliases"].append({"kind": row["kind"], "title": row["title"], "summary": row["summary"]})
            nearest["start_second"] = min(nearest["start_second"], row["start_second"])
            nearest["end_second"] = max(nearest["end_second"], row["end_second"])
            continue
        kept.append(row)
        if len(kept) >= max_total:
            break
    kept.sort(key=lambda r: r["second"])
    return kept


def collect_sequence_targets(db, match, *, max_total: int = 72) -> list[dict]:
    """Build the densest evidence-first review timeline available for one match.

    Targets remain explicitly typed: verified events, automatic candidates, tactical
    sequences, vision peaks and coarse active-play windows are never mixed as equal facts.
    """
    rows: list[dict] = []

    for event in sorted(list(match.events or []), key=lambda e: float(e.second or 0)):
        if event.event_type not in INTERESTING_EVENTS:
            continue
        confidence = _confidence_value(event.confidence, 1.0)
        meta = getattr(event, "context_meta", None)
        phase = getattr(meta, "phase_tag", "") if meta else ""
        player = event.player.name if event.player else ""
        suffix = f" · {player}" if player else ""
        rows.append(_target(
            kind="verified",
            second=float(event.second or 0),
            title=f"{_label(event.event_type)}{suffix}",
            summary=(event.note or "Événement confirmé utilisé dans les résultats Ultimate."),
            confidence=confidence,
            event_id=event.id,
            phase=phase,
            source=event.source or "verified_event",
        ))

    auto = _latest(db, AutonomousAnalysis, match.id)
    if auto:
        candidates = db.scalars(
            select(AutonomousEventCandidate)
            .where(AutonomousEventCandidate.analysis_id == auto.id)
            .order_by(AutonomousEventCandidate.confidence_score.desc(), AutonomousEventCandidate.second)
            .limit(40)
        ).all()
        for candidate in candidates:
            rows.append(_target(
                kind="automatic",
                second=float(candidate.second or 0),
                title=f"Candidat · {_label(candidate.event_type)}",
                summary=candidate.summary or "Moment automatique à vérifier.",
                confidence=_confidence_value(candidate.confidence_score, 0.0),
                source=candidate.source or "automatic_candidate",
            ))

    tactical = analyze_match_tactics(match)
    for seq in tactical.get("sequences", []) or []:
        start = float(seq.get("start", 0) or 0)
        duration = max(1.0, float(seq.get("duration", 0) or 0))
        shot_offset = seq.get("time_to_first_shot")
        if shot_offset is not None:
            focus = start + max(0.0, min(duration, float(shot_offset)))
        else:
            focus = start + min(duration * 0.5, 6.0)
        phase = str(seq.get("phase") or "tactical")
        summary_bits = [
            f"{int(seq.get('passes', 0) or 0)} passes taguées",
            f"{int(seq.get('shots_for', 0) or 0)} tirs",
            f"{int(seq.get('goals_for', 0) or 0)} buts",
            f"{int(seq.get('losses_for', 0) or 0)} pertes",
        ]
        rows.append(_target(
            kind="tactical",
            second=focus,
            title=f"Séquence tactique · {_label(phase)}",
            summary=" · ".join(summary_bits),
            confidence=0.92 if seq.get("events") else 0.72,
            phase=phase,
            start_second=start,
            end_second=start + duration,
            source="tactical_engine",
        ))

    vision = _latest(db, VisionAnalysis, match.id)
    if vision:
        samples = db.scalars(
            select(VisionSample)
            .where(VisionSample.analysis_id == vision.id)
            .order_by(VisionSample.action_score.desc(), VisionSample.second)
            .limit(100)
        ).all()
        selected: list[VisionSample] = []
        for sample in samples:
            if float(sample.active_score or 0) < 0.34:
                continue
            if any(abs(float(sample.second or 0) - float(other.second or 0)) < 4.0 for other in selected):
                continue
            selected.append(sample)
            if len(selected) >= 28:
                break
        for sample in selected:
            score = max(float(sample.action_score or 0), float(sample.active_score or 0))
            rows.append(_target(
                kind="vision_peak",
                second=float(sample.second or 0),
                title="Pic d'activité visuelle",
                summary=(
                    f"Signal visuel : action={float(sample.action_score or 0):.2f}, "
                    f"activité={float(sample.active_score or 0):.2f}, mouvement={float(sample.motion_score or 0):.2f}. "
                    "À contrôler : ce signal n'est pas un événement sportif confirmé."
                ),
                confidence=min(0.78, max(0.35, score)),
                source="vision_sample",
            ))

        for window in (_safe_json(vision.active_windows_json, []) or [])[:24]:
            start = float(window.get("start", 0) or 0)
            end = float(window.get("end", start + 1) or start + 1)
            duration = max(0.5, end - start)
            if duration < 4.0:
                continue
            focus = start + duration / 2.0
            rows.append(_target(
                kind="active_window",
                second=focus,
                title="Fenêtre de jeu actif",
                summary=f"Fenêtre visuelle active estimée sur {duration:.1f}s. À vérifier dans la vidéo.",
                confidence=_confidence_value(window.get("confidence", 0.45), 0.45),
                start_second=start,
                end_second=end,
                source="vision_active_window",
            ))

    return _dedupe_targets(rows, max_total=max_total)


def _artifact_exists(match, source: str, artifact_type: str, second: float) -> bool:
    return any(
        str(a.source or "") == source
        and a.artifact_type == artifact_type
        and abs(float(a.second or 0) - float(second)) <= 0.45
        for a in list(match.media_artifacts or [])
    )


def _youtube_segment_embed(video_url: str, start_second: float, end_second: float) -> str:
    base = youtube_embed(video_url)
    if not base:
        return ""
    parsed = urlparse(base)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    start = max(0, int(float(start_second or 0)))
    end = max(start + 1, int(float(end_second or start + 1)))
    params.update({"start": str(start), "end": str(end), "rel": "0"})
    return urlunparse(parsed._replace(query=urlencode(params)))


def materialize_deep_sequence_pack(
    db,
    match,
    upload_dir: Path,
    evidence_dir: Path,
    *,
    max_targets: int = 72,
    max_clips: int = 24,
    max_image_targets: int = 48,
    triple_frames: int = 18,
):
    """Materialize many exact local sequences without confusing candidates with facts."""
    targets = collect_sequence_targets(db, match, max_total=max_targets)
    upload_dir = Path(upload_dir)
    evidence_dir = Path(evidence_dir)
    local_video = match.video_source == "upload" and bool(match.video_path)
    source_path = upload_dir / Path(match.video_path).name if local_video else None
    if local_video and (not source_path or not source_path.exists()):
        local_video = False

    created = 0
    for index, target in enumerate(targets):
        second = float(target["second"])
        source_base = f"analysis_deep_{target['kind']}"
        if local_video:
            if index < max_clips and not _artifact_exists(match, source_base, "clip", second):
                before = max(2.0, min(6.0, second - float(target["start_second"]) + 1.0))
                after = max(3.0, min(8.0, float(target["end_second"]) - second + 1.0))
                try:
                    media = create_clip(source_path, evidence_dir, second, before=before, after=after)
                    db.add(MediaArtifact(
                        match_id=match.id,
                        event_id=target.get("event_id"),
                        artifact_type="clip",
                        analysis_type=target["kind"],
                        title=target["title"],
                        note=target["summary"][:1200],
                        second=second,
                        start_second=media.start_second,
                        end_second=media.end_second,
                        file_path=media.filename,
                        mime_type=media.mime_type,
                        is_downloadable=True,
                        source=source_base,
                    ))
                    created += 1
                except MediaGenerationError:
                    pass

            if index < max_image_targets:
                offsets = [0.0]
                if index < triple_frames:
                    offsets = [-2.0, 0.0, 2.0]
                for offset in offsets:
                    marker = "pre" if offset < 0 else "post" if offset > 0 else "focus"
                    source = f"{source_base}_{marker}"
                    if _artifact_exists(match, source, "screenshot", second):
                        continue
                    actual_second = max(0.0, second + offset)
                    try:
                        media = create_screenshot(source_path, evidence_dir, actual_second)
                        db.add(MediaArtifact(
                            match_id=match.id,
                            event_id=target.get("event_id"),
                            artifact_type="screenshot",
                            analysis_type=target["kind"],
                            title=f"{target['title']} · {'T−2' if offset < 0 else 'T+2' if offset > 0 else 'T0'}",
                            note=target["summary"][:1200],
                            second=second,
                            start_second=actual_second,
                            end_second=actual_second,
                            file_path=media.filename,
                            mime_type=media.mime_type,
                            is_downloadable=True,
                            source=source,
                        ))
                        created += 1
                    except MediaGenerationError:
                        pass
        elif match.video_url:
            source = f"{source_base}_url"
            if _artifact_exists(match, source, "bookmark", second):
                continue
            db.add(MediaArtifact(
                match_id=match.id,
                event_id=target.get("event_id"),
                artifact_type="bookmark",
                analysis_type=target["kind"],
                title=target["title"],
                note=(target["summary"] + " · Fenêtre distante bornée ; aucune copie locale.")[:1200],
                second=second,
                start_second=target["start_second"],
                end_second=target["end_second"],
                external_url=timestamped_video_url(match.video_url, target["start_second"]),
                mime_type="",
                is_downloadable=False,
                source=source,
            ))
            created += 1

    db.commit()
    return {"targets": targets, "created": created}


def sequence_gallery(db, match, *, max_total: int = 72) -> list[dict]:
    targets = collect_sequence_targets(db, match, max_total=max_total)
    artifacts = list(match.media_artifacts or [])
    cards = []
    for target in targets:
        second = float(target["second"])
        near = [
            a for a in artifacts
            if str(a.source or "").startswith("analysis_deep_")
            and abs(float(a.second or 0) - second) <= 0.55
        ]
        clip = next((a for a in near if a.artifact_type == "clip" and a.file_path), None)
        screenshots = [a for a in near if a.artifact_type == "screenshot" and a.file_path]
        screenshots.sort(key=lambda a: (float(a.start_second or 0), a.id or 0))
        bookmark = next((a for a in near if a.artifact_type == "bookmark" and a.external_url), None)
        start = float(target["start_second"])
        end = float(target["end_second"])
        cards.append({
            **target,
            "clip_id": clip.id if clip else None,
            "clip_url": f"/matches/{match.id}/evidence/{clip.id}" if clip else "",
            "screenshot_urls": [f"/matches/{match.id}/evidence/{a.id}" for a in screenshots],
            "screenshot_ids": [a.id for a in screenshots],
            "external_url": bookmark.external_url if bookmark else (timestamped_video_url(match.video_url, start) if match.video_url else ""),
            "segment_embed": _youtube_segment_embed(match.video_url, start, end) if match.video_url else "",
            "local_segment_url": f"/matches/{match.id}/video#t={start:.1f},{end:.1f}" if match.video_source == "upload" and match.video_path else "",
            "downloadable": bool(clip),
        })
    return cards


def sequence_summary(cards: list[dict]) -> dict:
    by_kind = {}
    for card in cards:
        by_kind[card["kind"]] = by_kind.get(card["kind"], 0) + 1
    return {
        "total": len(cards),
        "downloadable_clips": sum(1 for c in cards if c.get("clip_url")),
        "with_images": sum(1 for c in cards if c.get("screenshot_urls")),
        "external_segments": sum(1 for c in cards if c.get("segment_embed") or c.get("external_url")),
        "by_kind": by_kind,
    }


def _csv_text(headers, rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def append_sequence_manifest(zip_buffer: io.BytesIO, cards: list[dict], root: str):
    """Append the complete sequence catalogue to an already-built AquaMetric ZIP."""
    zip_buffer.seek(0, io.SEEK_END)
    rows = []
    for card in cards:
        rows.append({
            "kind": card["kind"],
            "title": card["title"],
            "second": card["second"],
            "start_second": card["start_second"],
            "end_second": card["end_second"],
            "confidence": card["confidence"],
            "confidence_label": card["confidence_label"],
            "phase": card["phase"],
            "source": card["source"],
            "downloadable": card["downloadable"],
            "external_url": card.get("external_url", ""),
            "summary": card["summary"],
        })
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{root}/04_sequences/sequence_manifest.csv",
            _csv_text(
                ["kind", "title", "second", "start_second", "end_second", "confidence", "confidence_label", "phase", "source", "downloadable", "external_url", "summary"],
                rows,
            ),
        )
        archive.writestr(
            f"{root}/04_sequences/sequence_manifest.json",
            json.dumps(cards, ensure_ascii=False, indent=2, default=str),
        )
        archive.writestr(
            f"{root}/04_sequences/README.txt",
            "verified = fait confirmé ; automatic = candidat automatique ; tactical = séquence dérivée des événements tagués ; vision_peak/active_window = signaux visuels à contrôler.\n",
        )
    zip_buffer.seek(0)
    return zip_buffer
