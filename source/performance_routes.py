from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import get_db
from models import (
    Match,
    User,
    PlayerIntelligenceProfile,
    VisionAnalysis,
    AutonomousAnalysis,
    AutonomousEventCandidate,
    AnalysisJob,
)
from services.advanced_metrics import shot_map_summary
from services.performance_intelligence import team_performance_report, player_match_breakdown, shot_preference_summary
from services.ultimate_analytics import ultimate_match_report, ultimate_event_report
from services.ratings import calculate_player_rating
from services.video import youtube_embed

router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _json(value, fallback):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def _automatic_video_report(db: Session, match: Match, vision: VisionAnalysis | None) -> dict:
    autonomy = db.scalar(
        select(AutonomousAnalysis)
        .where(AutonomousAnalysis.match_id == match.id)
        .order_by(AutonomousAnalysis.id.desc())
    )
    observations = _json(autonomy.observations_json, []) if autonomy else []
    periods = _json(autonomy.periods_json, []) if autonomy else []
    summary = _json(autonomy.summary_json, {}) if autonomy else {}
    autonomy_limitations = _json(autonomy.limitations_json, []) if autonomy else []

    candidates = []
    if autonomy:
        candidates = db.scalars(
            select(AutonomousEventCandidate)
            .where(AutonomousEventCandidate.analysis_id == autonomy.id)
            .order_by(AutonomousEventCandidate.second)
        ).all()
    candidate_counts = Counter(c.event_type for c in candidates)
    score_change_candidates = [
        c for c in candidates
        if c.event_type.startswith("goal_candidate") or c.event_type.startswith("score_change_window")
    ]
    whistle_candidates = [c for c in candidates if "whistle" in c.event_type]

    jobs = db.scalars(
        select(AnalysisJob)
        .where(AnalysisJob.match_id == match.id)
        .order_by(AnalysisJob.id.desc())
        .limit(6)
    ).all()

    vision_report = None
    if vision:
        active_windows = _json(vision.active_windows_json, [])
        interesting = _json(vision.interesting_moments_json, [])
        scoreboard_rois = _json(vision.scoreboard_candidates_json, [])
        vision_report = {
            "status": vision.status,
            "engine": vision.engine_version,
            "source_kind": vision.source_kind,
            "duration_seconds": round(float(vision.duration_seconds or 0), 2),
            "duration_minutes": round(float(vision.duration_seconds or 0) / 60.0, 2),
            "fps": round(float(vision.fps or 0), 3),
            "width": int(vision.width or 0),
            "height": int(vision.height or 0),
            "sample_interval_seconds": round(float(vision.sample_interval_seconds or 0), 3),
            "sample_count": int(vision.sample_count or 0),
            "video_type": vision.video_type,
            "confidence": vision.confidence,
            "avg_pool_ratio": round(float(vision.avg_pool_ratio or 0), 4),
            "avg_motion_score": round(float(vision.avg_motion_score or 0), 4),
            "scene_cut_rate": round(float(vision.scene_cut_rate or 0), 4),
            "active_seconds_estimate": round(float(vision.active_seconds_estimate or 0), 2),
            "active_minutes_estimate": round(float(vision.active_seconds_estimate or 0) / 60.0, 2),
            "active_windows_count": len(active_windows),
            "interesting_moments_count": len(interesting),
            "scoreboard_roi_candidates": len(scoreboard_rois),
            "active_windows": active_windows[:24],
            "interesting_moments": interesting[:24],
            "limitations": _json(vision.limitations_json, []),
        }

    autonomy_report = None
    if autonomy:
        autonomy_report = {
            "status": autonomy.status,
            "engine": autonomy.engine_version,
            "ocr_available": bool(autonomy.ocr_available),
            "scoreboard_observations": len(observations),
            "periods": periods,
            "period_count": len(periods),
            "summary": summary,
            "candidate_count": len(candidates),
            "candidate_counts": dict(sorted(candidate_counts.items())),
            "score_change_candidates": [
                {
                    "second": round(float(c.second or 0), 2),
                    "type": c.event_type,
                    "confidence": c.confidence_label,
                    "confidence_score": round(float(c.confidence_score or 0), 3),
                    "summary": c.summary,
                }
                for c in score_change_candidates[:24]
            ],
            "whistle_candidates": [
                {
                    "second": round(float(c.second or 0), 2),
                    "confidence": c.confidence_label,
                    "confidence_score": round(float(c.confidence_score or 0), 3),
                    "summary": c.summary,
                }
                for c in whistle_candidates[:24]
            ],
            "limitations": autonomy_limitations,
        }

    return {
        "vision": vision_report,
        "autonomy": autonomy_report,
        "jobs": [
            {
                "stage": j.stage,
                "progress": int(j.progress or 0),
                "status": j.status,
                "message": j.message or "",
            }
            for j in jobs
        ],
    }


def _measurement_matrix(match: Match, team_report: dict, ultimate: dict, automatic: dict) -> list[dict]:
    events = list(match.events)
    event_types = Counter(e.event_type for e in events)
    stat = team_report.get("statboard", {})
    timing = team_report.get("transition_timing", {})
    ultimate_team = ultimate.get("team", {})
    coverage = ultimate_team.get("coverage", {})
    components = coverage.get("components", {})
    vision = automatic.get("vision") or {}
    autonomy = automatic.get("autonomy") or {}

    physical_samples = sum(
        int((timing.get("measured", {}).get(key) or {}).get("samples", 0) or 0)
        for key in ("sprint_5m_s", "sprint_10m_s", "max_swim_speed_mps", "shot_speed_kmh", "release_time_s")
    )
    transition_samples = sum(int(v or 0) for v in (timing.get("samples") or {}).values())
    attributed = sum(1 for e in events if e.player_id)

    def row(family, status, source, detail, available):
        return {"family": family, "status": status, "source": source, "detail": detail, "available": bool(available)}

    rows = [
        row("Structure vidéo", "AUTO", "Vision locale", f"{vision.get('sample_count', 0)} images échantillonnées · {vision.get('duration_minutes', 0)} min", bool(vision)),
        row("Activité / fenêtres de jeu", "AUTO", "Vision locale", f"{vision.get('active_windows_count', 0)} fenêtres · {vision.get('active_minutes_estimate', 0)} min actives estimées", bool(vision)),
        row("Scoreboard / OCR", "AUTO", "OCR vidéo", f"{autonomy.get('scoreboard_observations', 0)} observations", bool(autonomy.get("scoreboard_observations"))),
        row("Périodes", "AUTO", "OCR + timeline", f"{autonomy.get('period_count', 0)} période(s) inférée(s)", bool(autonomy.get("period_count"))),
        row("Variations de score", "CANDIDAT AUTO", "OCR + vision", f"{len(autonomy.get('score_change_candidates', []))} fenêtre(s) candidate(s), à valider", bool(autonomy.get("score_change_candidates"))),
        row("Sifflets", "CANDIDAT AUTO", "Audio", f"{len(autonomy.get('whistle_candidates', []))} signal(aux) candidat(s)", bool(autonomy.get("whistle_candidates"))),
        row("Tirs / buts / cadrage", "TAGUÉ", "Événements validés", f"{stat.get('shots', 0)} tir(s) tagué(s) · {stat.get('goals', 0)} but(s)", bool(stat.get("shots") or event_types.get("goal"))),
        row("Passes", "TAGUÉ", "Événements validés", f"{stat.get('pass_attempts_tagged', 0)} passe(s) avec dénominateur", bool(stat.get("pass_attempts_tagged"))),
        row("Pertes de balle", "TAGUÉ", "Événements validés", f"{stat.get('turnovers', 0)} perte(s)", bool(stat.get("turnovers"))),
        row("Attribution joueuse", "TAGUÉ", "Événements validés", f"{attributed}/{len(events)} événements attribués", bool(attributed)),
        row("Possessions exactes", "TAGUÉ", "possession=ID", f"couverture {components.get('possession_pct', 0) or 0}%", bool((ultimate_team.get("possessions") or {}).get("available"))),
        row("Phases tactiques", "TAGUÉ", "phase_tag", f"couverture {components.get('phase_pct', 0) or 0}%", bool(components.get("phase_pct"))),
        row("Transitions D→A / A→D", "CALCULÉ", "Timestamps validés", f"{transition_samples} séquence(s) chronométrée(s)", bool(transition_samples)),
        row("Sprint / vitesse / release", "CALIBRÉ", "Mesures explicites", f"{physical_samples} mesure(s) calibrée(s)", bool(physical_samples)),
        row("Décision / pression / zones", "TAGUÉ", "Tags structurés", f"décision {components.get('decision_pct', 0) or 0}% · pression {components.get('pressure_pct', 0) or 0}% · zone tir {components.get('shot_zone_pct', 0) or 0}%", bool(components.get("decision_pct") or components.get("pressure_pct") or components.get("shot_zone_pct"))),
        row("Analyse qualitative", "DÉRIVÉE", "Événements + contexte", f"{len(ultimate_team.get('qualitative') or [])} constat(s) étayé(s)", bool(ultimate_team.get("qualitative"))),
    ]
    for item in rows:
        if not item["available"] and item["status"] not in {"AUTO", "CANDIDAT AUTO"}:
            item["status"] = "NON MESURÉ"
    return rows


@router.get("/api/matches/{match_id}/performance")
def match_performance_api(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)

    team_report = team_performance_report(match)
    ultimate = ultimate_match_report(match)
    players = []
    for player in match.team.players:
        events = [e for e in match.events if e.player_id == player.id]
        _, _, evidence = calculate_player_rating(events, role=player.primary_role)
        detail = evidence["__evaluation__"]
        profile = db.scalar(
            select(PlayerIntelligenceProfile).where(
                func.lower(PlayerIntelligenceProfile.canonical_name) == player.name.strip().lower()
            )
        )
        shot_pref = {"available": False, "count": 0, "origin": "Not enough located shots", "target": "Not enough target-zone shots"}
        if profile:
            shot_pref = shot_preference_summary(shot_map_summary(db, profile.id))
        players.append({
            "id": player.id,
            "name": player.name,
            "cap": player.cap_number,
            "role": player.primary_role or "",
            "profile_url": f"/profiles/players/{profile.id}" if profile else f"/players/{player.id}",
            "rating": detail.get("overall"),
            "confidence": detail.get("confidence_label"),
            "confidence_score": detail.get("confidence_score", 0),
            "dimensions": detail.get("dimensions", {}),
            "strengths": detail.get("strengths", []),
            "improvements": detail.get("improvements", []),
            "breakdown": player_match_breakdown(events, detail, role=player.primary_role or ""),
            "ultimate": ultimate_event_report(events, "for"),
            "shot_preference": shot_pref,
        })

    players.sort(key=lambda x: (x["rating"] is not None, x["rating"] or -1), reverse=True)

    media = []
    for artifact in sorted(match.media_artifacts, key=lambda a: (float(a.second or 0), a.id or 0)):
        local_url = f"/matches/{match.id}/evidence/{artifact.id}" if artifact.file_path else ""
        media.append({
            "id": artifact.id,
            "type": artifact.artifact_type,
            "title": artifact.title,
            "note": artifact.note or "",
            "second": float(artifact.second or 0),
            "url": local_url or artifact.external_url or "",
            "local": bool(local_url),
            "mime_type": artifact.mime_type or "",
            "analysis_type": artifact.analysis_type or "",
        })

    vision = db.scalar(
        select(VisionAnalysis).where(VisionAnalysis.match_id == match.id).order_by(VisionAnalysis.id.desc())
    )
    if vision and vision.contact_sheet_file:
        media.insert(0, {
            "id": f"vision-{vision.id}", "type": "contact_sheet", "title": "Vision contact sheet",
            "note": "Sampled frames from the visual baseline scan.", "second": 0,
            "url": f"/matches/{match.id}/vision/contact-sheet", "local": True,
            "mime_type": "image/jpeg", "analysis_type": "vision",
        })

    automatic = _automatic_video_report(db, match, vision)
    measurement_matrix = _measurement_matrix(match, team_report, ultimate, automatic)

    embed = youtube_embed(match.video_url) if match.video_url else None
    video = {
        "source": match.video_source,
        "embed_url": embed or "",
        "local_url": f"/matches/{match.id}/video" if match.video_source == "upload" and match.video_path else "",
        "external_url": match.video_url if match.video_url and not embed else "",
    }

    return {
        "match": {"id": match.id, "team": match.team.name, "opponent": match.opponent, "competition": match.competition or ""},
        "team_performance": team_report,
        "ultimate": ultimate,
        "players": players,
        "video": video,
        "media": media,
        "automatic_analysis": automatic,
        "measurement_matrix": measurement_matrix,
        "policy": {
            "physical_tracking": "Absolute sprint/shot-speed values are shown only when a calibrated measurement is explicitly tagged.",
            "possession": "Exact possession rates require possession=ID tags; otherwise AquaMetric shows only terminal-action proxies.",
            "third_party_video": "Third-party video remains embedded/timestamp-linked; AquaMetric does not copy it.",
            "qualitative": "Coach findings are evidence-linked hypotheses and must be checked against video before being treated as causal conclusions.",
            "automatic_video": "Vision/OCR/audio outputs are shown as automatic measurements or candidates. They are not silently promoted to player-level pass/shot facts.",
        },
    }