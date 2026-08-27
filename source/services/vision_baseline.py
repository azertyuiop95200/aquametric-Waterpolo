"""Evidence-first baseline computer-vision scan for owned local match video.

This module deliberately does NOT claim to recognize players, ball, passes, shots,
whistles or tactical systems. It performs inexpensive visual pre-analysis that is
useful before trained water-polo models are connected:
- video probe / duration / fps / resolution;
- sampled frame quality and pool-colour coverage;
- coarse visual motion and scene-cut signals;
- probable active-play windows (heuristic, not official periods);
- probable fixed scoreboard overlay regions (ROI candidates, not OCR);
- high-information review moments;
- contact sheet for human review.

Every output is labelled as heuristic so downstream product code cannot mistake it
for verified match truth.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json
import math
import uuid

import cv2
import numpy as np


class VisionBaselineError(RuntimeError):
    pass


@dataclass
class FrameSignal:
    second: float
    pool_ratio: float
    motion_score: float
    scene_change: float
    active_score: float
    action_score: float


@dataclass
class ScoreboardCandidate:
    name: str
    x: float
    y: float
    w: float
    h: float
    score: float


@dataclass
class VideoScanResult:
    duration_seconds: float
    fps: float
    width: int
    height: int
    frame_count: int
    sample_interval_seconds: float
    samples: list[FrameSignal]
    video_type: str
    video_type_confidence: str
    active_windows: list[dict[str, float]]
    interesting_moments: list[dict[str, Any]]
    scoreboard_candidates: list[ScoreboardCandidate]
    avg_pool_ratio: float
    avg_motion_score: float
    scene_cut_rate: float
    active_seconds_estimate: float
    contact_sheet_file: str
    limitations: list[str]

    def summary_json(self) -> str:
        payload = asdict(self)
        payload["samples"] = [asdict(s) for s in self.samples]
        payload["scoreboard_candidates"] = [asdict(s) for s in self.scoreboard_candidates]
        return json.dumps(payload, ensure_ascii=False)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _pool_ratio(frame: np.ndarray) -> float:
    """Broad cyan/blue water coverage heuristic.

    Pools vary a lot in white balance and lighting, therefore this threshold is
    intentionally broad and is used only as a visual scene cue.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # OpenCV H range 0..179. Cyan/blue usually ~75..115 but broadcasts vary.
    lower = np.array([70, 35, 55], dtype=np.uint8)
    upper = np.array([120, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    return float(np.count_nonzero(mask) / mask.size)


def _histogram(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def _motion(prev_gray: np.ndarray | None, gray: np.ndarray) -> float:
    if prev_gray is None:
        return 0.0
    # Resize defensively in case a corrupted stream changes dimensions.
    if prev_gray.shape != gray.shape:
        prev_gray = cv2.resize(prev_gray, (gray.shape[1], gray.shape[0]))
    diff = cv2.absdiff(prev_gray, gray)
    # Mean absolute pixel change; normalize to a practical 0..1 range.
    return _clamp(float(diff.mean()) / 55.0)


def _scene_change(prev_hist: np.ndarray | None, hist: np.ndarray) -> float:
    if prev_hist is None:
        return 0.0
    corr = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL))
    if math.isnan(corr):
        return 0.0
    return _clamp(1.0 - ((corr + 1.0) / 2.0))


def _region_score(frame: np.ndarray, rect: tuple[float, float, float, float]) -> float:
    h, w = frame.shape[:2]
    x, y, rw, rh = rect
    x1, y1 = int(x * w), int(y * h)
    x2, y2 = max(x1 + 1, int((x + rw) * w)), max(y1 + 1, int((y + rh) * h))
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return 0.0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 180)
    edge_density = float(np.count_nonzero(edges) / edges.size)
    contrast = _clamp(float(gray.std()) / 80.0)
    # Text/score overlays tend to combine local edges and contrast.
    return _clamp(edge_density * 2.4 + contrast * 0.35)


_SCOREBOARD_REGIONS: dict[str, tuple[float, float, float, float]] = {
    # Wide regions catch modern broadcast bars that contain both team names, score and clock.
    "top_wide": (0.00, 0.00, 0.72, 0.20),
    "bottom_wide": (0.00, 0.80, 0.72, 0.20),
    "top_left": (0.00, 0.00, 0.42, 0.20),
    "top_center": (0.24, 0.00, 0.52, 0.20),
    "top_right": (0.58, 0.00, 0.42, 0.20),
    "bottom_left": (0.00, 0.80, 0.42, 0.20),
    "bottom_center": (0.24, 0.80, 0.52, 0.20),
    "bottom_right": (0.58, 0.80, 0.42, 0.20),
}


def _scoreboard_candidates(frames: list[np.ndarray]) -> list[ScoreboardCandidate]:
    if not frames:
        return []
    accum = {name: [] for name in _SCOREBOARD_REGIONS}
    for frame in frames[: min(40, len(frames))]:
        for name, rect in _SCOREBOARD_REGIONS.items():
            accum[name].append(_region_score(frame, rect))
    ranked = []
    for name, values in accum.items():
        rect = _SCOREBOARD_REGIONS[name]
        # Persistent overlay regions should repeatedly carry structured edges.
        score = float(np.mean(values)) if values else 0.0
        ranked.append(ScoreboardCandidate(name, *rect, round(score, 3)))
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:3]


def _group_windows(samples: list[FrameSignal], interval: float, threshold: float = 0.42) -> list[dict[str, float]]:
    active = [s for s in samples if s.active_score >= threshold]
    if not active:
        return []
    gap_limit = max(4.0, interval * 1.75)
    groups: list[list[FrameSignal]] = [[active[0]]]
    for sample in active[1:]:
        if sample.second - groups[-1][-1].second <= gap_limit:
            groups[-1].append(sample)
        else:
            groups.append([sample])
    windows = []
    half = interval / 2.0
    for group in groups:
        start = max(0.0, group[0].second - half)
        end = group[-1].second + half
        confidence = float(np.mean([g.active_score for g in group]))
        windows.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(max(0.0, end - start), 2),
            "confidence": round(confidence, 3),
        })
    return windows


def _interesting_moments(samples: list[FrameSignal], limit: int = 10, separation: float = 8.0) -> list[dict[str, Any]]:
    ranked = sorted(samples, key=lambda s: s.action_score, reverse=True)
    chosen: list[FrameSignal] = []
    for sample in ranked:
        if sample.active_score < 0.34:
            continue
        if any(abs(sample.second - other.second) < separation for other in chosen):
            continue
        chosen.append(sample)
        if len(chosen) >= limit:
            break
    chosen.sort(key=lambda s: s.second)
    return [{
        "second": round(s.second, 2),
        "score": round(s.action_score, 3),
        "reason": "high visual activity candidate — requires human/model verification",
    } for s in chosen]


def _classify_video_type(duration: float, scene_cut_rate: float, active_seconds: float) -> tuple[str, str]:
    # This is intentionally conservative: video editorial style cannot be proven
    # from duration alone, so all classes remain candidates until richer models run.
    if duration < 180:
        return "short_clip_candidate", "MODERATE"
    if duration < 1800 and scene_cut_rate >= 0.18:
        return "highlights_candidate", "LOW"
    if duration >= 2700 and active_seconds >= 900:
        return "full_match_candidate", "MODERATE"
    if duration >= 1200:
        return "partial_or_full_match_candidate", "LOW"
    return "unknown", "LOW"


def _create_contact_sheet(frames: list[tuple[float, np.ndarray]], out_dir: Path) -> str:
    if not frames:
        return ""
    out_dir.mkdir(parents=True, exist_ok=True)
    selected = frames
    if len(selected) > 12:
        idx = np.linspace(0, len(selected) - 1, 12).astype(int)
        selected = [selected[i] for i in idx]
    thumb_w, thumb_h = 320, 180
    thumbs = []
    for second, frame in selected:
        thumb = cv2.resize(frame, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
        cv2.rectangle(thumb, (0, 0), (110, 26), (0, 0, 0), -1)
        m, s = divmod(int(second), 60)
        cv2.putText(thumb, f"{m:02d}:{s:02d}", (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        thumbs.append(thumb)
    cols = 3
    rows = math.ceil(len(thumbs) / cols)
    canvas = np.zeros((rows * thumb_h, cols * thumb_w, 3), dtype=np.uint8)
    for i, thumb in enumerate(thumbs):
        y, x = divmod(i, cols)
        canvas[y * thumb_h:(y + 1) * thumb_h, x * thumb_w:(x + 1) * thumb_w] = thumb
    filename = f"vision_contact_{uuid.uuid4().hex}.jpg"
    target = out_dir / filename
    if not cv2.imwrite(str(target), canvas, [cv2.IMWRITE_JPEG_QUALITY, 88]):
        raise VisionBaselineError("Unable to write vision contact sheet.")
    return filename


def scan_local_video(video_path: Path, evidence_dir: Path, target_samples: int = 180) -> VideoScanResult:
    video_path = Path(video_path)
    if not video_path.exists():
        raise VisionBaselineError("Video file does not exist.")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VisionBaselineError("OpenCV cannot open this video.")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = (frame_count / fps) if fps > 0 and frame_count > 0 else 0.0
        if duration <= 0:
            raise VisionBaselineError("Video duration could not be determined.")
        sample_count = max(8, min(int(target_samples), max(8, int(duration / 2))))
        interval = max(0.5, duration / sample_count)
        end_second = max(0.0, duration - max(0.25, 3.0 / max(fps, 1.0)))
        times = np.linspace(0.0, end_second, sample_count)

        signals: list[FrameSignal] = []
        raw_frames: list[np.ndarray] = []
        contact_frames: list[tuple[float, np.ndarray]] = []
        prev_gray = None
        prev_hist = None
        for idx, second in enumerate(times):
            cap.set(cv2.CAP_PROP_POS_MSEC, float(second) * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            # Normalize analysis size for speed while preserving source metadata.
            analysis = frame
            if frame.shape[1] > 960:
                scale = 960.0 / frame.shape[1]
                analysis = cv2.resize(frame, (960, max(1, int(frame.shape[0] * scale))), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(analysis, cv2.COLOR_BGR2GRAY)
            hist = _histogram(analysis)
            pool = _pool_ratio(analysis)
            motion = _motion(prev_gray, gray)
            scene = _scene_change(prev_hist, hist)
            # Active play cue: substantial water scene + visual change, penalizing hard cuts.
            water_component = _clamp((pool - 0.12) / 0.58)
            active = _clamp(0.58 * water_component + 0.32 * motion + 0.10 * (1.0 - scene))
            action = _clamp(0.46 * motion + 0.34 * active + 0.20 * scene)
            signals.append(FrameSignal(round(float(second), 3), round(pool, 4), round(motion, 4), round(scene, 4), round(active, 4), round(action, 4)))
            if len(raw_frames) < 40:
                raw_frames.append(analysis.copy())
            if idx % max(1, sample_count // 12) == 0:
                contact_frames.append((float(second), analysis.copy()))
            prev_gray = gray
            prev_hist = hist

        if not signals:
            raise VisionBaselineError("No readable frames were sampled from the video.")
        avg_pool = float(np.mean([s.pool_ratio for s in signals]))
        avg_motion = float(np.mean([s.motion_score for s in signals]))
        scene_cut_rate = float(np.mean([1.0 if s.scene_change >= 0.35 else 0.0 for s in signals]))
        windows = _group_windows(signals, interval)
        active_seconds = min(duration, float(sum(w["duration"] for w in windows)))
        video_type, type_conf = _classify_video_type(duration, scene_cut_rate, active_seconds)
        candidates = _scoreboard_candidates(raw_frames)
        moments = _interesting_moments(signals)
        contact_sheet = _create_contact_sheet(contact_frames, evidence_dir)
        limitations = [
            "This is an untrained visual baseline, not a water-polo event detector.",
            "Active-play windows are heuristic and are not official quarter boundaries.",
            "Scoreboard regions are candidate ROIs only; no score/clock OCR is performed yet.",
            "Player identity, ball, passes, shots, goals, whistles and exclusions are not inferred by this scan.",
            "Tactical systems must not be concluded from these visual signals alone.",
        ]
        return VideoScanResult(
            duration_seconds=round(duration, 3), fps=round(fps, 3), width=width, height=height,
            frame_count=frame_count, sample_interval_seconds=round(interval, 3), samples=signals,
            video_type=video_type, video_type_confidence=type_conf, active_windows=windows,
            interesting_moments=moments, scoreboard_candidates=candidates,
            avg_pool_ratio=round(avg_pool, 4), avg_motion_score=round(avg_motion, 4),
            scene_cut_rate=round(scene_cut_rate, 4), active_seconds_estimate=round(active_seconds, 2),
            contact_sheet_file=contact_sheet, limitations=limitations,
        )
    finally:
        cap.release()
