"""Immediate, local visual review evidence for V16 report-first publication.

This pass is intentionally OCR-free and provider-free. It reuses a small evenly
spaced subset of JPEG frames that the browser already sent during playback and
publishes only generic visual review moments. It never labels motion as a goal,
shot, pass, exclusion, player identity or tactical fact.

The heavier live-frame OCR pass and optional video-action provider may later
supersede these rows because analysis_snapshot always selects the newest Vision
and Autonomous analyses for the match.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import cv2
import numpy as np

from db import SessionLocal
from models import AutonomousAnalysis, AutonomousEventCandidate, Match, VisionAnalysis, VisionSample
from services.live_frame_match_analysis import _even_records, _timeline_records
from services.mosaic_match_analysis import _pane, _signal
from services.vision_baseline import _classify_video_type, _group_windows, _interesting_moments


def _persist_publication_latency(root: Path, state: dict) -> None:
    """Keep the fast terminal timing in mutable state used by /status."""
    try:
        started = float(
            state.get("v14_finalization_started_at")
            or state.get("v16_report_published_at")
            or state.get("published_at")
            or time.time()
        )
        elapsed = max(0.0, time.time() - started)
        if not math.isfinite(elapsed):
            elapsed = 0.0
        state["finalization_elapsed_seconds"] = round(elapsed, 3)
        # Imported lazily to avoid extending the capture-route import chain.
        # priority_analysis_routes patches this shared writer to the collision-
        # safe atomic implementation before V16 is installed.
        from capture_turbo_routes import _write_state
        _write_state(root, state)
    except Exception:
        # This timing field is diagnostic only and must never make report
        # publication fail.
        pass


def publish_report_first_visual(match_id: int, root_value: str | Path, state: dict | None = None) -> dict:
    """Persist bounded visual candidates before the report-first response returns."""
    root = Path(root_value)
    state = dict(state or {})
    db = SessionLocal()
    try:
        match = db.get(Match, int(match_id))
        if not match or not root.is_dir():
            return {"published": False, "reason": "missing_match_or_capture"}

        records = _timeline_records(root, state)
        if len(records) < 4:
            return {"published": False, "reason": "too_few_retained_frames", "records": len(records)}

        segments_raw = int(state.get("parallel_segments") or 1)
        segments = 4 if segments_raw >= 4 else (2 if segments_raw >= 2 else 1)
        rate = max(1.0, min(4.0, float(state.get("playback_rate") or 1.0)))
        source_start = max(0.0, float(state.get("source_start_second") or 0.0))
        source_end = max(source_start + 1.0, float(state.get("source_duration_seconds") or 0.0))
        source_duration = max(1.0, source_end - source_start)
        segment_span = source_duration / segments

        # At most 18 composite JPEGs are decoded. With four panes this is 72
        # visual samples, enough for a useful review timeline without delaying
        # the report or competing with OCR/provider work.
        selected = _even_records(records, min(18, max(6, len(records))))
        signals = []
        prev_gray = [None] * segments
        prev_hist = [None] * segments
        pane_width = pane_height = 0

        for record in selected:
            image = cv2.imread(str(record["path"]), cv2.IMREAD_COLOR)
            if image is None:
                continue
            wall = max(0.0, float(record["wall_second"]))
            for seg in range(segments):
                rel_second = seg * segment_span + wall * rate
                if rel_second >= min(source_duration, (seg + 1) * segment_span):
                    continue
                pane = _pane(image, seg, segments)
                if pane.size == 0:
                    continue
                row, gray, hist, _ = _signal(pane, rel_second, prev_gray[seg], prev_hist[seg])
                row.second = round(float(row.second) + source_start, 3)
                signals.append(row)
                prev_gray[seg], prev_hist[seg] = gray, hist
                pane_height, pane_width = pane.shape[:2]

        if len(signals) < 4:
            return {"published": False, "reason": "frames_not_decodable", "records": len(records)}

        signals.sort(key=lambda row: float(row.second))
        interval = source_duration / max(1, len(signals))
        windows = _group_windows(signals, interval)
        moments = _interesting_moments(signals, limit=14, separation=max(4.0, source_duration / 180.0))
        avg_pool = float(np.mean([row.pool_ratio for row in signals]))
        avg_motion = float(np.mean([row.motion_score for row in signals]))
        scene_cut_rate = float(np.mean([1.0 if row.scene_change >= 0.35 else 0.0 for row in signals]))
        active_seconds = min(source_duration, float(sum(float(w.get("duration", 0.0)) for w in windows)))
        video_type, type_conf = _classify_video_type(source_duration, scene_cut_rate, active_seconds)

        vision = VisionAnalysis(
            match_id=match.id,
            status="partial",
            engine_version="report-first-visual-v1",
            source_kind="browser_capture_live_frames",
            duration_seconds=source_duration,
            fps=0.0,
            width=max(1, pane_width),
            height=max(1, pane_height),
            sample_interval_seconds=interval,
            sample_count=len(signals),
            video_type=video_type,
            confidence=type_conf,
            avg_pool_ratio=avg_pool,
            avg_motion_score=avg_motion,
            scene_cut_rate=scene_cut_rate,
            active_seconds_estimate=active_seconds,
            active_windows_json=json.dumps(windows, ensure_ascii=False),
            interesting_moments_json=json.dumps(moments, ensure_ascii=False),
            scoreboard_candidates_json="[]",
            contact_sheet_file="",
            limitations_json=json.dumps([
                "Pré-publication locale à partir des images JPEG réellement reçues pendant la capture.",
                "Les pics d'activité sont uniquement des moments à revoir : ils ne prouvent ni but, ni tir, ni passe, ni exclusion.",
                "Le score, les périodes, les joueurs et le type d'action restent non mesurés tant qu'un moteur approprié ne les confirme pas.",
            ], ensure_ascii=False),
        )
        db.add(vision)
        db.flush()
        for row in signals:
            db.add(VisionSample(
                analysis_id=vision.id,
                second=float(row.second),
                pool_ratio=float(row.pool_ratio),
                motion_score=float(row.motion_score),
                scene_change=float(row.scene_change),
                active_score=float(row.active_score),
                action_score=float(row.action_score),
            ))

        summary = {
            "pipeline": "report-first-visual-v1",
            "visual_review_only": True,
            "visual_samples": len(signals),
            "retained_live_frames": len(records),
            "scoreboard_observations": 0,
            "action_candidates": len(moments),
            "ocr_reason": "pending_or_unavailable",
            "analysis_outcome": "visual_review_available" if moments else "no_measurements",
            "measurement_strategy": "bounded local visual activity review before OCR/provider enrichment",
            "scientific_honesty": "A visual activity peak is a review timestamp only and is never converted into a sporting event by this pass.",
        }
        autonomy = AutonomousAnalysis(
            match_id=match.id,
            status="partial" if moments else "no_measurements",
            engine_version="report-first-visual-v1",
            ocr_available=False,
            observations_json="[]",
            periods_json="[]",
            summary_json=json.dumps(summary, ensure_ascii=False),
            limitations_json=json.dumps([
                "Candidats visuels génériques uniquement; aucune statistique sportive n'est déduite du mouvement seul.",
                "L'enrichissement Vision/OCR et le moteur vidéo peuvent remplacer cette pré-publication par des preuves plus spécifiques.",
            ], ensure_ascii=False),
        )
        db.add(autonomy)
        db.flush()

        for item in moments:
            score = max(0.0, min(1.0, float(item.get("score") or 0.0)))
            confidence = min(0.55, max(0.20, score * 0.55))
            second = float(item.get("second") or 0.0)
            db.add(AutonomousEventCandidate(
                analysis_id=autonomy.id,
                match_id=match.id,
                second=second,
                event_type="unclassified_action_candidate",
                confidence_score=confidence,
                confidence_label="LOW",
                summary="Pic d’activité visuelle détecté ; moment à revoir. Le type d’action n’est pas déterminé par cette pré-analyse.",
                evidence_json=json.dumps({
                    "signal": "visual_activity_only",
                    "visual_activity_score": round(score, 3),
                    "counting_rule": "review_only_never_counted_as_goal_shot_pass_or_exclusion",
                    "provider_independent": True,
                }, ensure_ascii=False),
                source="report-first-visual-v1",
            ))

        db.commit()
        return {
            "published": True,
            "visual_samples": len(signals),
            "candidates": len(moments),
            "retained_frames": len(records),
        }
    except Exception:
        db.rollback()
        return {"published": False, "reason": "visual_prepublication_failed"}
    finally:
        db.close()
        _persist_publication_latency(root, state)
