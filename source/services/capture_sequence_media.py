"""Create private, downloadable clips from pixels explicitly sent by the browser."""
from __future__ import annotations

import math
import time
import uuid
from pathlib import Path
from threading import Lock

from models import MediaArtifact
from services.capture_state_io import write_state_atomic
from services.deep_analysis_sequences import collect_sequence_targets
from services.media import MediaGenerationError, _run_ffmpeg, create_screenshot

_MEDIA_LOCK = Lock()


def capture_window(target: dict, state: dict) -> dict | None:
    start = float(state.get("source_start_second") or 0)
    end = float(state.get("source_duration_seconds") or 0)
    rate = max(1., min(4., float(state.get("playback_rate") or 1)))
    segments = 4 if int(state.get("parallel_segments") or 1) >= 4 else (2 if int(state.get("parallel_segments") or 1) >= 2 else 1)
    second = float(target["second"])
    if not all(math.isfinite(value) for value in (start, end, rate, second)) or end <= start or not start <= second < end:
        return None
    span = (end - start) / segments
    pane = min(segments - 1, int((second - start) / span))
    pane_start, pane_end = start + pane * span, start + (pane + 1) * span
    first = max(pane_start, second - 6, float(target["start_second"]))
    last = min(pane_end, second + 8, float(target["end_second"]))
    if not math.isfinite(first + last) or last - first < .2:
        return None
    return {"source_start": first, "source_end": last, "capture_start": (first - pane_start) / rate,
            "capture_duration": (last - first) / rate, "rate": rate, "pane": pane, "segments": segments}


def create_capture_clip(source: Path, destination: Path, window: dict) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"capture_clip_{uuid.uuid4().hex}.mp4"
    pane, segments = window["pane"], window["segments"]
    filters = []
    if segments == 2:
        filters.append(f"crop=trunc(iw/4)*2:trunc(ih/2)*2:{'iw/2' if pane else '0'}:0")
    elif segments == 4:
        filters.append(f"crop=trunc(iw/4)*2:trunc(ih/4)*2:{'iw/2' if pane % 2 else '0'}:{'ih/2' if pane >= 2 else '0'}")
    filters += [f"setpts={window['rate']:.6f}*(PTS-STARTPTS)", "scale=w='trunc(min(960,iw)/2)*2':h=-2"]
    try:
        _run_ffmpeg(["-threads", "1", "-ss", f"{window['capture_start']:.3f}",
                     "-t", f"{window['capture_duration']:.3f}", "-i", str(source),
                     "-map", "0:v:0", "-an", "-vf", ",".join(filters),
                     "-fps_mode", "vfr", "-c:v", "libx264", "-threads", "1",
                     "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                     "-movflags", "+faststart", str(path)], timeout=45)
        if not path.exists() or not path.stat().st_size:
            raise MediaGenerationError("Aucun extrait vidéo n'a été produit.")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def materialize_capture_sequences(db, match, root: Path, evidence_dir: Path, *, max_targets=72, budget_seconds=180):
    from capture_turbo_routes import _read_state
    root, evidence_dir = Path(root), Path(evidence_dir)
    source = root / "capture.webm"
    if not source.exists():
        state = _read_state(root)
        state.update(media_status="unavailable", media_updated_at=time.time(),
                     media_message="La capture source n'est plus disponible.")
        write_state_atomic(root, state)
        return state
    with _MEDIA_LOCK:
        started = time.monotonic()
        state = _read_state(root)
        targets = collect_sequence_targets(db, match, max_total=max_targets)
        done = 0
        errors = []
        state.update(media_status="running", media_targets=len(targets), media_updated_at=time.time())
        write_state_atomic(root, state)
        for target in sorted(targets, key=lambda row: (row.get("priority", 9), row["second"])):
            if time.monotonic() - started > budget_seconds:
                errors.append("Le temps de génération de ce lot est atteint ; la capture est conservée.")
                break
            window = capture_window(target, state)
            if window is None:
                continue
            source_name = f"analysis_deep_{target['kind']}"
            existing = next((a for a in match.media_artifacts if a.source == source_name
                             and a.artifact_type == "clip" and abs(a.second - target["second"]) < .45), None)
            try:
                if existing and existing.file_path and (evidence_dir / Path(existing.file_path).name).exists():
                    clip = evidence_dir / Path(existing.file_path).name
                else:
                    clip = create_capture_clip(source, evidence_dir, window)
                    artifact = existing or MediaArtifact(match_id=match.id, event_id=target.get("event_id"),
                        artifact_type="clip", analysis_type=target["kind"], source=source_name)
                    artifact.title = target["title"]
                    artifact.note = (target["summary"] + " · Extrait de la capture fournie, remis à vitesse normale, sans audio. Horodatage selon la chronologie de capture.")[:1200]
                    artifact.second = target["second"]
                    artifact.start_second, artifact.end_second = window["source_start"], window["source_end"]
                    artifact.file_path, artifact.mime_type, artifact.is_downloadable = clip.name, "video/mp4", True
                    db.add(artifact)
                    db.commit()
                    db.expire(match, ["media_artifacts"])
                done += 1
                image_source = source_name + "_focus"
                has_image = any(a.source == image_source and a.artifact_type == "screenshot"
                                and abs(a.second - target["second"]) < .45 and a.file_path
                                and (evidence_dir / Path(a.file_path).name).exists() for a in match.media_artifacts)
                if not has_image:
                    image = create_screenshot(clip, evidence_dir, max(0., target["second"] - window["source_start"]))
                    db.add(MediaArtifact(match_id=match.id, event_id=target.get("event_id"), artifact_type="screenshot",
                        analysis_type=target["kind"], source=image_source, title=target["title"] + " · image clé",
                        note=target["summary"][:1200], second=target["second"], start_second=target["second"],
                        end_second=target["second"], file_path=image.filename, mime_type="image/jpeg", is_downloadable=True))
                    db.commit()
                    db.expire(match, ["media_artifacts"])
            except Exception as exc:
                db.rollback()
                errors.append(str(exc)[:200])
                # A corrupt recording cannot yield the next 72 clips either.
                # Preserve the source and permit an explicit retry.
                if done == 0 and len(errors) >= 3:
                    break
            state.update(media_clips=done, media_updated_at=time.time())
            write_state_atomic(root, state)
        result = {"media_status": "partial" if errors else "complete", "media_clips": done,
                  "media_targets": len(targets), "media_errors": errors[:3], "media_updated_at": time.time(),
                  "media_elapsed_seconds": round(time.monotonic() - started, 2), "capture_retained": True}
        state.update(result)
        write_state_atomic(root, state)
        return result
