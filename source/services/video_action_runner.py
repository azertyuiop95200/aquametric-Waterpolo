"""Checkpoint every continuous video segment; retry only unfinished segments."""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from threading import Lock

from sqlalchemy import select
from models import VideoActionAnalysis
from services.browser_capture_media import ffprobe_video
from services.media import _run_ffmpeg
from services.video_action_provider import VideoActionError, analyze_video_segment, provider_configuration
from services.video_action_schema import VERSION, SegmentObservation

_WORK_LOCK = Lock()
_ENCODE_LOCK = Lock()
SEGMENT_SECONDS = 60.0


def segment_plan(duration: float, capture_state: dict | None = None) -> tuple[list[dict], float]:
    if not math.isfinite(duration) or not 0 < duration <= 8 * 3600:
        raise VideoActionError("media_duration", "La durée de la vidéo ne peut pas être vérifiée (limite : 8 h).")
    state = capture_state or {}
    start = float(state.get("source_start_second") or 0)
    end = float(state.get("source_duration_seconds") or duration)
    rate = float(state.get("playback_rate") or 1)
    panes = int(state.get("parallel_segments") or 1)
    if (not all(math.isfinite(v) for v in (start, end, rate)) or
            not 0 <= start < end <= 8 * 3600 or not 1 <= rate <= 4 or panes not in {1, 2, 4}):
        raise VideoActionError("capture_mapping", "La chronologie de la capture ne peut pas être vérifiée.")
    span = (end - start) / panes
    plan = []
    for pane in range(panes):
        pane_start = start + pane * span
        available = min(span, duration * rate)
        offset = 0.0
        while offset < available - .05:
            core_start, core_end = pane_start + offset, pane_start + min(available, offset + SEGMENT_SECONDS)
            first, last = max(pane_start, core_start - 2), min(pane_start + available, core_end + 2)
            plan.append({"index": len(plan), "pane": pane, "panes": panes, "rate": rate,
                         "start": core_start, "end": core_end, "clip_start": first, "clip_end": last,
                         "capture_start": (first - pane_start) / rate,
                         "capture_duration": (last - first) / rate, "status": "pending"})
            offset += SEGMENT_SECONDS
    return plan, end - start


def encode_segment(source: Path, target: Path, segment: dict, timeout: float) -> None:
    filters = []
    pane = segment["pane"]
    if segment["panes"] == 2:
        filters.append(f"crop=trunc(iw/4)*2:trunc(ih/2)*2:{'iw/2' if pane else '0'}:0")
    elif segment["panes"] == 4:
        filters.append(f"crop=trunc(iw/4)*2:trunc(ih/4)*2:{'iw/2' if pane % 2 else '0'}:{'ih/2' if pane >= 2 else '0'}")
    filters += [f"setpts={segment['rate']:.6f}*(PTS-STARTPTS)",
                "scale=w='trunc(min(960,iw)/2)*2':h=-2", "fps=8"]
    _run_ffmpeg(["-ss", f"{segment['capture_start']:.3f}", "-t", f"{segment['capture_duration']:.3f}",
                 "-i", str(source), "-map", "0:v:0", "-an", "-vf", ",".join(filters),
                 "-c:v", "libx264", "-threads", "1", "-preset", "veryfast", "-crf", "22",
                 "-maxrate", "1200k", "-bufsize", "2400k", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", str(target)], timeout=max(1, int(timeout)))
    meta = ffprobe_video(target)
    expected = segment["clip_end"] - segment["clip_start"]
    if not meta.get("ok") or meta["duration"] < expected - max(.75, expected * .03):
        raise VideoActionError("short_media", "La séquence est tronquée ; sa couverture n’est pas validée.")


def normalize_observations(payload: dict, segment: dict) -> dict:
    payload = SegmentObservation.model_validate(payload).model_dump()
    events = []
    ignored = {"replays": 0, "overlap": 0, "duplicates": 0}
    for event in payload["actions"]:
        if payload["scene"] in {"not_water_polo", "unreadable"}:
            raise VideoActionError("invalid_scene", "Des actions sont présentes dans une séquence déclarée illisible.")
        relative = event["second"]
        if relative >= segment["clip_end"] - segment["clip_start"] + .15:
            raise VideoActionError("invalid_timestamp", "Le moteur a fourni un horodatage hors de la séquence.")
        if event["is_replay"]:
            ignored["replays"] += 1
            continue
        second = relative + segment["clip_start"]
        # Only the owning core segment contributes a count, despite overlapping context.
        if not segment["start"] <= second < segment["end"]:
            ignored["overlap"] += 1
            continue
        event["second"] = round(second, 3)
        event["segment_index"] = segment["index"]
        # Literal duplicates are safely removed; close-in-time shots or passes
        # from different players must not be collapsed into one event.
        signature = (event["second"], event["event_type"], event["side"], event["cap_number"])
        if any((e["second"], e["event_type"], e["side"], e["cap_number"]) == signature for e in events):
            ignored["duplicates"] += 1
            continue
        events.append(event)
    payload["actions"] = sorted(events, key=lambda e: e["second"])
    payload["ignored"] = ignored
    return payload


def _segment_work(source, segment, team, opponent, deadline):
    try:
        with tempfile.TemporaryDirectory(prefix="aquametric-actions-") as folder:
            target = Path(folder) / "segment.mp4"
            with _ENCODE_LOCK:
                remaining = deadline - time.monotonic()
                if remaining < 10:
                    raise VideoActionError("budget", "Limite de temps atteinte ; les séquences restantes pourront être reprises.")
                encode_segment(source, target, segment, timeout=min(45, remaining - 5))
            remaining = deadline - time.monotonic()
            if remaining < 5:
                raise VideoActionError("budget", "Limite de temps atteinte ; les séquences restantes pourront être reprises.")
            payload = analyze_video_segment(target, team=team, opponent=opponent, timeout=min(75, remaining))
            return {"status": "complete", "result": normalize_observations(payload, segment)}
    except VideoActionError as exc:
        return {"status": "failed", "error_code": exc.code, "error": str(exc)}
    except Exception:
        # Exceptions may contain a provider request or local path. Never put
        # those raw exceptions in an owner-visible report.
        return {"status": "failed", "error_code": "processing", "error": "Cette séquence n’a pas pu être traitée ; elle pourra être reprise."}


def _save(db, run, plan):
    run.segments_json = json.dumps(plan, ensure_ascii=False)
    run.updated_at = time.time()
    db.add(run)
    db.commit()


def run_video_actions(db, match, source: Path, *, capture_state: dict | None = None, budget_seconds=None):
    source = Path(source)
    config = provider_configuration()
    stat = source.stat() if source.is_file() else None
    identity = [VERSION, match.owner_id, match.id, str(source), stat.st_size if stat else 0,
                stat.st_mtime_ns if stat else 0, config["model"], match.team.name, match.opponent,
                {key: (capture_state or {}).get(key) for key in ("source_start_second", "source_duration_seconds", "playback_rate", "parallel_segments")}]
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    # One orchestrator/encoder per small Render instance. Worker threads only
    # handle independent inference calls, never share SQLAlchemy sessions.
    with _WORK_LOCK:
        run = db.scalar(select(VideoActionAnalysis).where(VideoActionAnalysis.fingerprint == fingerprint))
        if not run:
            run = VideoActionAnalysis(match_id=match.id, fingerprint=fingerprint, model=config["model"],
                                      source_kind="browser_capture" if capture_state else "upload", source_path=str(source))
            db.add(run)
            db.commit()
        if run.status == "complete":
            return run
        plan = json.loads(run.segments_json or "[]")
        if not config["configured"]:
            run.status, run.message = "not_configured", config["message"]
            _save(db, run, plan)
            return run
        try:
            if not plan:
                meta = ffprobe_video(source)
                if not meta.get("ok"):
                    raise VideoActionError("source_unavailable", "Le fichier vidéo reçu n’est plus disponible ou sa durée est illisible.")
                plan, duration = segment_plan(meta["duration"], capture_state)
                run.duration_seconds = duration
            run.status, run.message = "running", "Reconnaissance des actions dans les séquences vidéo."
            _save(db, run, plan)
            try:
                budget = float(budget_seconds if budget_seconds is not None else os.getenv("AQUAMETRIC_VIDEO_BUDGET_SECONDS", "420"))
            except ValueError:
                budget = 420
            budget = min(600, max(10, budget)) if math.isfinite(budget) else 420
            deadline = time.monotonic() + budget
            pending = iter(s for s in plan if s.get("status") != "complete")
            stop = False
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="video-actions") as pool:
                active = {}
                while True:
                    while not stop and len(active) < 2 and time.monotonic() < deadline - 5:
                        segment = next(pending, None)
                        if segment is None:
                            break
                        segment["status"] = "running"
                        active[pool.submit(_segment_work, source, dict(segment), match.team.name, match.opponent, deadline)] = segment
                    if not active:
                        break
                    done, _ = wait(active, timeout=5, return_when=FIRST_COMPLETED)
                    for future in done:
                        segment = active.pop(future)
                        for key in ("error", "error_code", "result"):
                            segment.pop(key, None)
                        segment.update(future.result())
                        if segment.get("error_code") in {"credentials", "quota", "not_configured", "budget"}:
                            stop = True
                    _save(db, run, plan)  # heartbeat and per-segment checkpoint
            completed = sum(s["status"] == "complete" for s in plan)
            run.status = "complete" if completed == len(plan) and plan else ("partial" if completed else "failed")
            run.message = (f"{completed}/{len(plan)} séquences traitées. Les statistiques automatiques restent des estimations à contrôler."
                           if completed else "Aucune séquence d’actions exploitable. Consulter la cause et reprendre le traitement.")
        except VideoActionError as exc:
            run.status, run.message = "failed", str(exc)
        except Exception:
            db.rollback()
            run.status, run.message = "failed", "Le traitement s’est interrompu. Les séquences déjà enregistrées sont conservées."
        _save(db, run, plan)
        return run
