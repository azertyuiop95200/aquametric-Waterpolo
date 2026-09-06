"""Conservative visual cap-number OCR for water-polo match video.

This module intentionally treats a cap number as *visual evidence*, never as a
player identity.  A number is only surfaced when the same reading is supported
by repeated observations.  Names are not accepted as inputs and no roster is
used to fill missing numbers.

The implementation is dependency-light: OpenCV plus the optional Tesseract
runtime already used by scoreboard OCR.  When Tesseract is unavailable or the
video does not expose a readable number, callers receive an empty list rather
than fabricated data.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import median
from typing import Iterable
import math
import re

import cv2
import numpy as np

try:  # optional at runtime, same policy as scoreboard_ocr
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

from services.scoreboard_ocr import tesseract_available


MIN_CAP_NUMBER = 1
MAX_CAP_NUMBER = 20


@dataclass(frozen=True)
class CapNumberObservation:
    second: float
    number: int
    confidence: float
    x: float
    y: float
    w: float
    h: float
    color_hint: str
    source: str = "cap-number-ocr-v1"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CapTrackCandidate:
    track_id: str
    number: int
    color_hint: str
    confidence: float
    observations: int
    first_second: float
    last_second: float
    verified_visual_number: bool
    evidence: tuple[dict, ...]

    def to_dict(self) -> dict:
        row = asdict(self)
        row["evidence"] = list(self.evidence)
        # Product wording is deliberately explicit: a cap number is not a name.
        row["identity_status"] = "player_indeterminate"
        return row


def _number_token(text: str) -> int | None:
    token = (text or "").strip().replace("O", "0").replace("o", "0")
    token = re.sub(r"[^0-9]", "", token)
    if not token or len(token) > 2:
        return None
    try:
        value = int(token)
    except ValueError:
        return None
    if MIN_CAP_NUMBER <= value <= MAX_CAP_NUMBER:
        return value
    return None


def _color_hint(frame: np.ndarray, box: tuple[int, int, int, int]) -> str:
    """Return only a weak cap-colour cue; never use it as identity by itself."""
    h, w = frame.shape[:2]
    x, y, bw, bh = box
    pad_x = max(6, int(bw * 0.9))
    pad_y = max(6, int(bh * 0.9))
    x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
    x2, y2 = min(w, x + bw + pad_x), min(h, y + bh + pad_y)
    patch = frame[y1:y2, x1:x2]
    if patch.size == 0:
        return "unknown"
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    # Use robust medians so water/specular highlights do not dominate.
    hue = float(np.median(hsv[..., 0]))
    sat = float(np.median(hsv[..., 1]))
    val = float(np.median(hsv[..., 2]))
    if sat < 65 and val > 155:
        return "white"
    # OpenCV hue wraps red around 0/179.
    red_pixels = (((hsv[..., 0] <= 12) | (hsv[..., 0] >= 170)) & (hsv[..., 1] >= 90) & (hsv[..., 2] >= 75))
    if float(np.mean(red_pixels)) >= 0.18:
        return "red"
    if val < 105:
        return "dark"
    if 85 <= hue <= 135 and sat >= 70:
        return "blue"
    return "unknown"


def _ocr_variants(frame: np.ndarray) -> list[tuple[np.ndarray, float, int, int]]:
    """Return OCR images plus scale and original crop offsets.

    Overlay-heavy top/bottom bands are excluded.  This is important because a
    scoreboard digit is not a player cap number.
    """
    h, w = frame.shape[:2]
    if h < 80 or w < 120:
        return []
    x1, x2 = int(w * 0.035), int(w * 0.965)
    y1, y2 = int(h * 0.13), int(h * 0.89)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return []
    # Small bonnet digits benefit from strong upscaling.  Keep the OCR image
    # bounded so long videos remain practical on a free CPU instance.
    target_w = min(2400, max(1200, crop.shape[1] * 3))
    scale = target_w / max(1, crop.shape[1])
    enlarged = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 5, 35, 35)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
    adaptive = cv2.adaptiveThreshold(
        clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7
    )
    inverse = cv2.bitwise_not(adaptive)
    return [
        (clahe, scale, x1, y1),
        (adaptive, scale, x1, y1),
        (inverse, scale, x1, y1),
    ]


def detect_cap_numbers_in_frame(frame: np.ndarray, second: float, *, min_confidence: float = 0.66) -> list[CapNumberObservation]:
    if frame is None or frame.size == 0 or pytesseract is None or not tesseract_available():
        return []
    h, w = frame.shape[:2]
    found: dict[tuple[int, int, int], CapNumberObservation] = {}
    config = "--psm 11 -c tessedit_char_whitelist=0123456789"
    for image, scale, offset_x, offset_y in _ocr_variants(frame):
        try:
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        texts = data.get("text", [])
        confs = data.get("conf", [])
        lefts, tops = data.get("left", []), data.get("top", [])
        widths, heights = data.get("width", []), data.get("height", [])
        for text, raw_conf, left, top, bw, bh in zip(texts, confs, lefts, tops, widths, heights):
            number = _number_token(text)
            if number is None:
                continue
            try:
                confidence = float(raw_conf) / 100.0
            except Exception:
                continue
            if confidence < min_confidence:
                continue
            ox = int(float(left) / scale) + offset_x
            oy = int(float(top) / scale) + offset_y
            ow = max(1, int(float(bw) / scale))
            oh = max(1, int(float(bh) / scale))
            # Cap digits are small relative to the broadcast frame.  This rejects
            # most large clocks/sponsor signage even if they enter the play ROI.
            area_ratio = (ow * oh) / max(1.0, float(w * h))
            if area_ratio > 0.0065 or ow > w * 0.12 or oh > h * 0.13:
                continue
            if ow < 2 or oh < 3:
                continue
            nx, ny = (ox + ow / 2) / w, (oy + oh / 2) / h
            # Deduplicate OCR variants at roughly the same image location.
            key = (number, int(nx * 24), int(ny * 18))
            obs = CapNumberObservation(
                second=round(float(second), 3),
                number=number,
                confidence=round(max(0.0, min(1.0, confidence)), 3),
                x=round(ox / w, 4),
                y=round(oy / h, 4),
                w=round(ow / w, 4),
                h=round(oh / h, 4),
                color_hint=_color_hint(frame, (ox, oy, ow, oh)),
            )
            previous = found.get(key)
            if previous is None or obs.confidence > previous.confidence:
                found[key] = obs
    return sorted(found.values(), key=lambda row: (-row.confidence, row.number))[:16]


def _center(obs: CapNumberObservation) -> tuple[float, float]:
    return obs.x + obs.w / 2.0, obs.y + obs.h / 2.0


def _compatible(a: CapNumberObservation, b: CapNumberObservation) -> bool:
    if a.number != b.number:
        return False
    if a.color_hint != "unknown" and b.color_hint != "unknown" and a.color_hint != b.color_hint:
        return False
    if abs(float(a.second) - float(b.second)) > 8.0:
        return False
    ax, ay = _center(a)
    bx, by = _center(b)
    # Broadcast motion/camera pans can be substantial; this radius is only for
    # short temporal continuity and never merges observations far apart in time.
    return math.hypot(ax - bx, ay - by) <= 0.24


def build_cap_tracks(observations: Iterable[CapNumberObservation]) -> list[CapTrackCandidate]:
    rows = sorted(list(observations), key=lambda o: (o.second, o.number, -o.confidence))
    clusters: list[list[CapNumberObservation]] = []
    for obs in rows:
        target = None
        for cluster in reversed(clusters):
            if _compatible(cluster[-1], obs):
                target = cluster
                break
        if target is None:
            clusters.append([obs])
        else:
            target.append(obs)

    tracks: list[CapTrackCandidate] = []
    per_number_counter: dict[tuple[int, str], int] = {}
    for cluster in clusters:
        # A single OCR hit is too weak to show as a cap number in the report.
        unique_times = sorted({round(float(row.second), 1) for row in cluster})
        conf = float(median([row.confidence for row in cluster]))
        if len(unique_times) < 2 or conf < 0.68:
            continue
        colors = [row.color_hint for row in cluster if row.color_hint != "unknown"]
        color = max(set(colors), key=colors.count) if colors else "unknown"
        number = cluster[0].number
        key = (number, color)
        per_number_counter[key] = per_number_counter.get(key, 0) + 1
        idx = per_number_counter[key]
        verified = len(unique_times) >= 3 and conf >= 0.76
        evidence = tuple(row.to_dict() for row in sorted(cluster, key=lambda r: -r.confidence)[:6])
        tracks.append(CapTrackCandidate(
            track_id=f"cap{number}-{color}-{idx}",
            number=number,
            color_hint=color,
            confidence=round(conf, 3),
            observations=len(unique_times),
            first_second=round(float(min(row.second for row in cluster)), 2),
            last_second=round(float(max(row.second for row in cluster)), 2),
            verified_visual_number=verified,
            evidence=evidence,
        ))
    return sorted(tracks, key=lambda row: (row.first_second, row.number, row.track_id))


def sample_cap_numbers(
    video_path: Path,
    duration_seconds: float,
    *,
    max_samples: int = 56,
    time_offset_seconds: float = 0.0,
    time_scale: float = 1.0,
) -> list[dict]:
    """Sample a local/transient video and return repeated visual cap tracks."""
    if not tesseract_available():
        return []
    path = Path(video_path)
    if not path.exists() or duration_seconds <= 0:
        return []
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []
    observations: list[CapNumberObservation] = []
    try:
        count = max(12, min(72, int(max_samples)))
        targets = np.linspace(0.0, max(0.0, float(duration_seconds) - 0.2), count)
        for second in targets:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(second) * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            mapped_second = float(second) * float(time_scale) + float(time_offset_seconds)
            observations.extend(detect_cap_numbers_in_frame(frame, mapped_second))
    finally:
        cap.release()
    return [row.to_dict() for row in build_cap_tracks(observations)]
