from __future__ import annotations

import csv
import html
import io
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

from sqlalchemy import select

from models import (
    AnalysisJob,
    AutonomousAnalysis,
    AutonomousEventCandidate,
    LibraryPlayerMatchStat,
    MatchLibraryItem,
    MediaArtifact,
    VisionAnalysis,
)
from services.media import create_clip, create_screenshot, MediaGenerationError
from services.rapid_match_analysis import run_rapid_analysis, RapidAnalysisError
from services.tactical_engine import analyze_match_tactics
from services.ultimate_analytics import ultimate_match_report
from services.video import timestamped_video_url, youtube_embed


INTERESTING_EVENT_TYPES = {
    "goal", "shot_on_target", "shot_off_target", "shot_blocked", "save", "block",
    "turnover", "bad_pass", "interception", "recovery", "exclusion_earned",
    "exclusion_committed", "penalty_earned", "key_pass", "assist", "duel_won",
    "duel_lost", "fast_recovery", "late_recovery",
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


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "")
    return value.strip("_")[:80] or "match"


def youtube_segment_embed(video_url: str, start_second: float, end_second: float) -> str:
    """Return an iframe URL constrained to the exact review window when YouTube supports it."""
    base = youtube_embed(video_url)
    if not base:
        return ""
    parsed = urlparse(base)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    start = max(0, int(float(start_second or 0)))
    end = max(start + 1, int(float(end_second or start + 1)))
    params.update({"start": str(start), "end": str(end), "rel": "0"})
    return urlunparse(parsed._replace(query=urlencode(params)))


def _analysis_type(event_type: str) -> str:
    if event_type in {"turnover", "bad_pass", "interception", "recovery", "fast_recovery", "late_recovery"}:
        return "transition"
    if event_type in {"block", "exclusion_earned", "exclusion_committed", "penalty_earned"}:
        return "tactic"
    return "action"


def _title(event_type: str, prefix: str = "") -> str:
    label = (event_type or "study moment").replace("_", " ").strip().title()
    return f"{prefix}{label}".strip()


def _artifact_exists(match, *, event_id=None, second=None, artifact_type=None, source_prefix="analysis_exact"):
    for artifact in list(getattr(match, "media_artifacts", []) or []):
        if not str(getattr(artifact, "source", "") or "").startswith(source_prefix):
            continue
        if event_id is not None and artifact.event_id != event_id:
            continue
        if second is not None and abs(float(artifact.second or 0) - float(second)) > 0.35:
            continue
        if artifact_type and artifact.artifact_type != artifact_type:
            continue
        return True
    return False


def build_exact_evidence_pack(
    db,
    match,
    upload_dir: Path,
    evidence_dir: Path,
    *,
    max_verified_events: int = 16,
    max_candidates: int = 8,
):
    """Create media that corresponds to the exact timestamp of the evidence it represents.

    Owned uploads get a short clip + freeze frame. Third-party URLs never get a fake image:
    only a bounded/timestamped reference is stored.
    """
    upload_dir = Path(upload_dir)
    evidence_dir = Path(evidence_dir)
    created = []

    events = [
        e for e in sorted(list(match.events or []), key=lambda row: float(row.second or 0))
        if e.event_type in INTERESTING_EVENT_TYPES
    ][:max_verified_events]

    latest_auto = _latest(db, AutonomousAnalysis, match.id)
    candidates = []
    if latest_auto:
        candidates = db.scalars(
            select(AutonomousEventCandidate)
            .where(AutonomousEventCandidate.analysis_id == latest_auto.id)
            .order_by(AutonomousEventCandidate.confidence_score.desc(), AutonomousEventCandidate.second)
            .limit(max_candidates)
        ).all()
        candidates = sorted(candidates, key=lambda row: float(row.second or 0))

    local_video = match.video_source == "upload" and bool(match.video_path)
    source_path = upload_dir / Path(match.video_path).name if local_video else None
    if local_video and (not source_path or not source_path.exists()):
        local_video = False

    for event in events:
        second = float(event.second or 0)
        analysis_type = _analysis_type(event.event_type)
        if local_video:
            if not _artifact_exists(match, event_id=event.id, artifact_type="clip"):
                try:
                    media = create_clip(source_path, evidence_dir, second, before=3.0, after=5.0)
                    artifact = MediaArtifact(
                        match_id=match.id, event_id=event.id, artifact_type="clip",
                        analysis_type=analysis_type, title=_title(event.event_type),
                        note=event.note or "Séquence centrée exactement sur l'événement confirmé.",
                        second=second, start_second=media.start_second, end_second=media.end_second,
                        file_path=media.filename, mime_type=media.mime_type, is_downloadable=True,
                        source="analysis_exact_event",
                    )
                    db.add(artifact); created.append(artifact)
                except MediaGenerationError:
                    pass
            if not _artifact_exists(match, event_id=event.id, artifact_type="screenshot"):
                try:
                    media = create_screenshot(source_path, evidence_dir, second)
                    artifact = MediaArtifact(
                        match_id=match.id, event_id=event.id, artifact_type="screenshot",
                        analysis_type=analysis_type, title=f"Image · {_title(event.event_type)}",
                        note="Arrêt sur image au timestamp exact de l'événement confirmé.",
                        second=second, start_second=second, end_second=second,
                        file_path=media.filename, mime_type=media.mime_type, is_downloadable=True,
                        source="analysis_exact_event",
                    )
                    db.add(artifact); created.append(artifact)
                except MediaGenerationError:
                    pass
        elif match.video_url and not _artifact_exists(match, event_id=event.id, artifact_type="bookmark"):
            start = max(0.0, second - 3.0)
            end = second + 5.0
            artifact = MediaArtifact(
                match_id=match.id, event_id=event.id, artifact_type="bookmark",
                analysis_type=analysis_type, title=_title(event.event_type),
                note="Séquence distante bornée par timestamps. Aucune image locale n'est inventée.",
                second=second, start_second=start, end_second=end,
                external_url=timestamped_video_url(match.video_url, start),
                is_downloadable=False, source="analysis_exact_event_url",
            )
            db.add(artifact); created.append(artifact)

    if local_video:
        for candidate in candidates:
            second = float(candidate.second or 0)
            label = _title(candidate.event_type, "Candidat · ")
            note = f"{candidate.summary} · Confiance {candidate.confidence_label}. Candidat automatique, non promu en fait confirmé."
            if not _artifact_exists(match, second=second, artifact_type="clip", source_prefix="analysis_exact_candidate"):
                try:
                    media = create_clip(source_path, evidence_dir, second, before=2.5, after=4.5)
                    artifact = MediaArtifact(
                        match_id=match.id, artifact_type="clip", analysis_type="action",
                        title=label, note=note, second=second,
                        start_second=media.start_second, end_second=media.end_second,
                        file_path=media.filename, mime_type=media.mime_type, is_downloadable=True,
                        source="analysis_exact_candidate",
                    )
                    db.add(artifact); created.append(artifact)
                except MediaGenerationError:
                    pass
            if not _artifact_exists(match, second=second, artifact_type="screenshot", source_prefix="analysis_exact_candidate"):
                try:
                    media = create_screenshot(source_path, evidence_dir, second)
                    artifact = MediaArtifact(
                        match_id=match.id, artifact_type="screenshot", analysis_type="action",
                        title=f"Image · {label}", note=note, second=second,
                        start_second=second, end_second=second,
                        file_path=media.filename, mime_type=media.mime_type, is_downloadable=True,
                        source="analysis_exact_candidate",
                    )
                    db.add(artifact); created.append(artifact)
                except MediaGenerationError:
                    pass

    db.commit()
    return created


def _public_reference(db, match):
    wanted = {str(match.team.name or "").strip().lower(), str(match.opponent or "").strip().lower()}
    best = None
    best_score = -1
    for item in db.scalars(select(MatchLibraryItem).order_by(MatchLibraryItem.id.desc())).all():
        pair = {str(item.team_a or "").strip().lower(), str(item.team_b or "").strip().lower()}
        score = 0
        if pair == wanted:
            score += 10
        elif wanted and all(any(token and token in name for name in pair) for token in wanted):
            score += 5
        if match.competition and item.competition and match.competition.lower() in item.competition.lower():
            score += 2
        if score > best_score:
            best, best_score = item, score
    return best if best_score >= 5 else None


def _reference_payload(db, item):
    if not item:
        return None
    player_rows = db.scalars(
        select(LibraryPlayerMatchStat)
        .where(LibraryPlayerMatchStat.library_match_id == item.id)
        .order_by(LibraryPlayerMatchStat.team_name, LibraryPlayerMatchStat.player_name)
    ).all()
    return {
        "id": item.id,
        "title": item.title,
        "competition": item.competition,
        "season": item.season,
        "team_a": item.team_a,
        "team_b": item.team_b,
        "score_a": item.score_a,
        "score_b": item.score_b,
        "quarters": _safe_json(item.quarter_scores_json, []),
        "team_stats": _safe_json(item.team_stats_json, {}),
        "official_source_url": item.official_source_url,
        "video_url": item.video_url,
        "analysis_status": item.analysis_status,
        "tactical_summary": item.tactical_summary,
        "players": [
            {
                "team": row.team_name, "player": row.player_name, "goals": row.goals,
                "shots": row.shots, "assists": row.assists, "steals": row.steals,
                "exclusions": row.exclusions, "saves": row.saves,
                "source_quality": row.source_quality, "note": row.note,
            }
            for row in player_rows
        ],
    }


def analysis_snapshot(db, match):
    vision = _latest(db, VisionAnalysis, match.id)
    auto = _latest(db, AutonomousAnalysis, match.id)
    job = _latest(db, AnalysisJob, match.id)
    candidates = []
    if auto:
        candidates = db.scalars(
            select(AutonomousEventCandidate)
            .where(AutonomousEventCandidate.analysis_id == auto.id)
            .order_by(AutonomousEventCandidate.second)
        ).all()
    reference = _reference_payload(db, _public_reference(db, match))

    artifacts = sorted(list(match.media_artifacts or []), key=lambda row: (float(row.second or 0), row.id or 0))
    artifact_rows = []
    for a in artifacts:
        artifact_rows.append({
            "id": a.id, "event_id": a.event_id, "artifact_type": a.artifact_type,
            "analysis_type": a.analysis_type, "title": a.title, "note": a.note,
            "second": float(a.second or 0), "start_second": float(a.start_second or 0),
            "end_second": float(a.end_second or 0), "file_path": a.file_path,
            "mime_type": a.mime_type, "external_url": a.external_url,
            "downloadable": bool(a.is_downloadable), "source": a.source,
            "segment_embed": youtube_segment_embed(match.video_url, a.start_second, a.end_second)
                if match.video_url and a.artifact_type == "bookmark" else "",
        })

    candidate_rows = [
        {
            "id": c.id, "second": float(c.second or 0), "event_type": c.event_type,
            "confidence": float(c.confidence_score or 0), "confidence_label": c.confidence_label,
            "summary": c.summary, "evidence": _safe_json(c.evidence_json, {}), "source": c.source,
        }
        for c in candidates
    ]

    return {
        "ultimate": ultimate_match_report(match),
        "tactical": analyze_match_tactics(match),
        "vision": {
            "available": bool(vision),
            "engine": vision.engine_version if vision else "",
            "duration_seconds": float(vision.duration_seconds or 0) if vision else 0,
            "sample_count": int(vision.sample_count or 0) if vision else 0,
            "video_type": vision.video_type if vision else "",
            "confidence": vision.confidence if vision else "",
            "active_seconds": float(vision.active_seconds_estimate or 0) if vision else 0,
            "active_windows": _safe_json(vision.active_windows_json, []) if vision else [],
            "interesting_moments": _safe_json(vision.interesting_moments_json, []) if vision else [],
            "contact_sheet_file": vision.contact_sheet_file if vision else "",
            "limitations": _safe_json(vision.limitations_json, []) if vision else [],
        },
        "automatic": {
            "available": bool(auto),
            "engine": auto.engine_version if auto else "",
            "summary": _safe_json(auto.summary_json, {}) if auto else {},
            "periods": _safe_json(auto.periods_json, []) if auto else [],
            "observations": _safe_json(auto.observations_json, []) if auto else [],
            "limitations": _safe_json(auto.limitations_json, []) if auto else [],
            "candidates": candidate_rows,
        },
        "job": {
            "status": job.status if job else "not_run",
            "stage": job.stage if job else "",
            "progress": int(job.progress or 0) if job else 0,
            "message": job.message if job else "",
        },
        "reference": reference,
        "artifacts": artifact_rows,
        "verified_events": [
            {
                "id": e.id, "second": float(e.second or 0), "event_type": e.event_type,
                "player": e.player.name if e.player else "", "confidence": e.confidence,
                "source": e.source, "note": e.note,
                "perspective": getattr(getattr(e, "context_meta", None), "perspective", "for"),
                "phase": getattr(getattr(e, "context_meta", None), "phase_tag", "auto"),
            }
            for e in sorted(list(match.events or []), key=lambda row: float(row.second or 0))
        ],
    }


def run_product_analysis(db, match, upload_dir: Path, evidence_dir: Path, *, include_audio: bool = False):
    if match.video_source == "upload" and match.video_path:
        source_path = Path(upload_dir) / Path(match.video_path).name
        result = run_rapid_analysis(
            db, match, source_path, Path(evidence_dir), include_audio=include_audio,
            visual_samples=180, ocr_samples=48,
        )
        build_exact_evidence_pack(db, match, upload_dir, evidence_dir)
        return result

    if match.video_url:
        reference = _public_reference(db, match)
        event_count = len(list(match.events or []))
        build_exact_evidence_pack(db, match, upload_dir, evidence_dir)
        if reference or event_count:
            status = "url_results_ready"
            message = (
                f"Résultat URL généré avec {event_count} événement(s) vérifié(s)"
                + (" et une référence publique correspondante." if reference else ".")
                + " Les preuves vidéo tierces restent des séquences temporelles exactes, sans capture locale inventée."
            )
        else:
            status = "url_source_ready_needs_evidence"
            message = (
                "La source URL est lisible, mais aucune donnée de match correspondante ni événement horodaté n'est encore prouvé. "
                "AquaMetric n'invente donc ni tirs, ni joueuses, ni images."
            )
        job = AnalysisJob(match_id=match.id, stage="url_analysis", progress=100, status=status, message=message)
        match.status = status
        db.add(job); db.commit()
        return {"job": job}

    job = AnalysisJob(match_id=match.id, stage="analysis", progress=0, status="no_video", message="Aucune source vidéo disponible.")
    match.status = "no_video"
    db.add(job); db.commit()
    return {"job": job}


def _csv_text(headers, rows) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _html_report(match, snapshot) -> str:
    ultimate = snapshot["ultimate"]
    team = ultimate["team"]["basic"]
    opponent = ultimate["opponent"]["basic"]
    coverage = ultimate["team"]["coverage"]
    findings = ultimate["team"]["qualitative"]
    findings_html = "".join(
        f"<li><strong>{html.escape(str(row['title']))}</strong> — {html.escape(str(row['text']))} <small>{html.escape(str(row['evidence']))}</small></li>"
        for row in findings
    ) or "<li>Aucun constat fort sans preuve suffisante.</li>"
    return f"""<!doctype html><html lang='fr'><meta charset='utf-8'><title>AquaMetric analysis</title>
<style>body{{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 24px;color:#15202b}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd6dd;padding:8px;text-align:left}}small{{color:#657786}}</style>
<h1>{html.escape(match.team.name)} vs {html.escape(match.opponent)}</h1>
<p>{html.escape(match.competition or '')} · {html.escape(match.match_date or '')}</p>
<h2>Couverture Ultimate</h2><p><strong>{coverage['score']}% · {html.escape(coverage['readiness'])}</strong></p>
<h2>KPIs vérifiés</h2><table><tr><th></th><th>{html.escape(match.team.name)}</th><th>{html.escape(match.opponent)}</th></tr>
<tr><td>Buts</td><td>{team['goals']}</td><td>{opponent['goals']}</td></tr><tr><td>Tirs</td><td>{team['shots']}</td><td>{opponent['shots']}</td></tr>
<tr><td>Passes réussies</td><td>{team['pass_completion_pct'] if team['pass_completion_pct'] is not None else '—'}%</td><td>{opponent['pass_completion_pct'] if opponent['pass_completion_pct'] is not None else '—'}%</td></tr>
<tr><td>Pertes</td><td>{team['turnovers']}</td><td>{opponent['turnovers']}</td></tr></table>
<h2>Constats coach fondés sur les données</h2><ul>{findings_html}</ul>
<h2>Preuves</h2><p>{len(snapshot['verified_events'])} événements vérifiés · {len(snapshot['automatic']['candidates'])} candidats automatiques · {len(snapshot['artifacts'])} médias/références.</p>
<p><small>Les candidats automatiques restent distincts des faits confirmés. Les vidéos tierces ne sont pas copiées dans l'archive.</small></p></html>"""


def build_analysis_zip(db, match, evidence_dir: Path) -> io.BytesIO:
    snapshot = analysis_snapshot(db, match)
    root = f"AquaMetric_{_slug(match.team.name)}_vs_{_slug(match.opponent)}_{match.id}"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        readme = (
            "AquaMetric — dossier complet d'analyse\n"
            "====================================\n\n"
            "01_report : rapport lisible + données JSON complètes\n"
            "02_kpis : KPI équipe/adversaire et différentiels\n"
            "03_events : événements vérifiés\n"
            "04_sequences : candidats automatiques et séquences tactiques\n"
            "05_evidence : clips/images locaux réellement liés aux timestamps + index des références externes\n"
            "06_sources : référence publique/officiale éventuelle et contrat de preuve\n\n"
            "Important : une source YouTube/tiers n'est jamais copiée dans le ZIP. Les segments exacts sont fournis par URL + bornes temporelles.\n"
        )
        archive.writestr(f"{root}/00_README.txt", readme)
        archive.writestr(f"{root}/01_report/report.html", _html_report(match, snapshot))
        archive.writestr(f"{root}/01_report/analysis.json", json.dumps(snapshot, ensure_ascii=False, indent=2, default=str))

        for side in ("team", "opponent"):
            basic = snapshot["ultimate"][side]["basic"]
            archive.writestr(
                f"{root}/02_kpis/{side}_kpis.csv",
                _csv_text(["metric", "value"], [{"metric": k, "value": v} for k, v in basic.items()]),
            )
        archive.writestr(
            f"{root}/02_kpis/differentials.csv",
            _csv_text(["key", "label", "team", "opponent", "delta"], snapshot["ultimate"]["differentials"]),
        )
        archive.writestr(
            f"{root}/03_events/events.csv",
            _csv_text(["id", "second", "event_type", "player", "perspective", "phase", "confidence", "source", "note"], snapshot["verified_events"]),
        )
        archive.writestr(
            f"{root}/04_sequences/auto_candidates.csv",
            _csv_text(["id", "second", "event_type", "confidence", "confidence_label", "summary", "source"], snapshot["automatic"]["candidates"]),
        )
        archive.writestr(
            f"{root}/04_sequences/tactical_sequences.json",
            json.dumps(snapshot["tactical"].get("sequences", []), ensure_ascii=False, indent=2, default=str),
        )

        evidence_rows = []
        external_rows = []
        evidence_dir = Path(evidence_dir)
        for row in snapshot["artifacts"]:
            evidence_rows.append({k: row.get(k) for k in ("id", "event_id", "artifact_type", "analysis_type", "title", "second", "start_second", "end_second", "source")})
            if row.get("file_path"):
                path = evidence_dir / Path(row["file_path"]).name
                if path.exists() and path.is_file():
                    folder = "clips" if row.get("artifact_type") == "clip" else "images"
                    archive.write(path, f"{root}/05_evidence/{folder}/{path.name}")
            if row.get("external_url"):
                external_rows.append({
                    "title": row.get("title"), "event_second": row.get("second"),
                    "start_second": row.get("start_second"), "end_second": row.get("end_second"),
                    "url": row.get("external_url"), "segment_embed": row.get("segment_embed"),
                })
        archive.writestr(
            f"{root}/05_evidence/evidence_index.csv",
            _csv_text(["id", "event_id", "artifact_type", "analysis_type", "title", "second", "start_second", "end_second", "source"], evidence_rows),
        )
        archive.writestr(
            f"{root}/05_evidence/external_segments.csv",
            _csv_text(["title", "event_second", "start_second", "end_second", "url", "segment_embed"], external_rows),
        )
        contact = snapshot["vision"].get("contact_sheet_file")
        if contact:
            contact_path = evidence_dir / Path(contact).name
            if contact_path.exists() and contact_path.is_file():
                archive.write(contact_path, f"{root}/05_evidence/contact_sheet/{contact_path.name}")

        archive.writestr(
            f"{root}/06_sources/evidence_contract.json",
            json.dumps(snapshot["ultimate"]["evidence_contract"], ensure_ascii=False, indent=2),
        )
        archive.writestr(
            f"{root}/06_sources/public_reference.json",
            json.dumps(snapshot.get("reference"), ensure_ascii=False, indent=2, default=str),
        )
        archive.writestr(
            f"{root}/06_sources/source.txt",
            f"video_source={match.video_source}\nvideo_url={match.video_url or ''}\ncompetition={match.competition or ''}\ndate={match.match_date or ''}\n",
        )
    buffer.seek(0)
    return buffer
