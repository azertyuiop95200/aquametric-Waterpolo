"""Scoreboard OCR utilities for owned/local water-polo broadcast video.

Evidence-first: OCR is treated as an observation, never as official truth. The
module can run without Tesseract; callers receive an explicit unavailable state.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
import os
import re
import shutil

import cv2
import numpy as np

try:
    import pytesseract
except Exception:  # pragma: no cover - optional at runtime
    pytesseract = None


@dataclass
class ScoreboardObservation:
    second: float
    roi_name: str
    raw_text: str
    normalized_text: str
    ocr_confidence: float
    period: int | None
    clock_seconds: int | None
    numbers: list[int]
    home_score: int | None = None
    away_score: int | None = None

    def to_dict(self):
        return asdict(self)


def tesseract_available() -> bool:
    if pytesseract is None:
        return False
    configured = os.getenv("TESSERACT_CMD", "").strip()
    if configured:
        pytesseract.pytesseract.tesseract_cmd = configured
        return Path(configured).exists()
    return shutil.which("tesseract") is not None


def _roi(frame: np.ndarray, rect: tuple[float, float, float, float]) -> np.ndarray:
    h, w = frame.shape[:2]
    x, y, rw, rh = rect
    x1, y1 = max(0, int(x * w)), max(0, int(y * h))
    x2, y2 = min(w, max(x1 + 1, int((x + rw) * w))), min(h, max(y1 + 1, int((y + rh) * h)))
    return frame[y1:y2, x1:x2]


def _variants(img: np.ndarray) -> list[np.ndarray]:
    if img.size == 0:
        return []
    scale = 2.0 if img.shape[1] < 900 else 1.35
    enlarged = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
    denoise = cv2.bilateralFilter(gray, 7, 45, 45)
    clahe = cv2.createCLAHE(clipLimit=2.3, tileGridSize=(8, 8)).apply(denoise)
    otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    inv = cv2.bitwise_not(otsu)
    return [enlarged, clahe, otsu, inv]


def _parse_clock(text: str) -> int | None:
    matches = re.findall(r"(?<!\d)(\d{1,2})\s*[:.]\s*(\d{2})(?!\d)", text)
    best = None
    for mm, ss in matches:
        m, s = int(mm), int(ss)
        if 0 <= m <= 15 and 0 <= s < 60:
            value = m * 60 + s
            if best is None or value <= 8 * 60 + 59:
                best = value
    return best


def _parse_period(text: str) -> int | None:
    patterns = [
        r"\bQ\s*([1-4])\b", r"\bP\s*([1-4])\b", r"\bPER\s*([1-4])\b",
        r"\b([1-4])\s*(?:Q|ST|ND|RD|TH)\b",
    ]
    upper = text.upper().replace("O", "0")
    for pattern in patterns:
        m = re.search(pattern, upper)
        if m:
            return int(m.group(1))
    return None


def _canonical_numeric_tokens(text: str) -> str:
    out = []
    for token in (text or "").split():
        if re.fullmatch(r"[0-9Oo]{1,2}", token):
            token = token.upper().replace("O", "0")
        out.append(token)
    return " ".join(out)


def _extract_numbers(text: str) -> list[int]:
    cleaned = _canonical_numeric_tokens(text)
    # Remove clock and period tokens before score extraction so Q1 does not erase a 1-0 score.
    cleaned = re.sub(r"\d{1,2}\s*[:.]\s*\d{2}", " ", cleaned)
    cleaned = re.sub(r"\b(?:Q|P|PER)\s*[1-4]\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b[1-4]\s*(?:Q|ST|ND|RD|TH)\b", " ", cleaned, flags=re.I)
    values = []
    for token in re.findall(r"(?<!\d)\d{1,2}(?!\d)", cleaned):
        n = int(token)
        if 0 <= n <= 40:
            values.append(n)
    return values[:8]


def parse_scoreboard_text(text: str) -> dict:
    normalized = " ".join((text or "").replace("\n", " ").split())
    canonical = _canonical_numeric_tokens(normalized)
    period = _parse_period(canonical)
    clock = _parse_clock(canonical)
    numbers = _extract_numbers(canonical)
    home = away = None
    # Two score-like numbers plus a clock or period cue are sufficient for a candidate.
    if (period is not None or clock is not None) and len(numbers) >= 2:
        home, away = numbers[0], numbers[1]
    return {
        "normalized_text": normalized,
        "period": period,
        "clock_seconds": clock,
        "numbers": numbers,
        "home_score": home,
        "away_score": away,
    }


def _ocr_once(variant: np.ndarray, config: str = "--psm 7") -> tuple[str, float]:
    try:
        data = pytesseract.image_to_data(variant, config=config, output_type=pytesseract.Output.DICT)
    except Exception:
        return "", 0.0
    parts, confs = [], []
    for txt, conf in zip(data.get("text", []), data.get("conf", [])):
        txt = (txt or "").strip()
        try: cf = float(conf)
        except Exception: cf = -1
        if txt:
            parts.append(txt)
            if cf >= 0:
                confs.append(cf)
    return " ".join(parts), (float(np.mean(confs) / 100.0) if confs else 0.0)


def ocr_image(img: np.ndarray) -> tuple[str, float]:
    if not tesseract_available():
        return "", 0.0
    variants = _variants(img)
    if not variants:
        return "", 0.0
    # Fast path: one OCR call on the enlarged colour/gray image. Broadcast overlays
    # are usually high contrast. This is essential for 1–2 h matches.
    text, conf = _ocr_once(variants[0], "--psm 7")
    parsed = parse_scoreboard_text(text)
    if text and (parsed["clock_seconds"] is not None or parsed["period"] is not None or len(parsed["numbers"]) >= 2):
        return text, min(1.0, conf)
    # Fallback only when the fast pass did not produce useful scoreboard syntax.
    best_text, best_conf, best_utility = text, conf, conf
    for variant in variants[1:3]:
        t, c = _ocr_once(variant, "--psm 7")
        p = parse_scoreboard_text(t)
        utility = c + (0.18 if p["clock_seconds"] is not None else 0) + (0.12 if p["period"] else 0) + (0.08 if len(p["numbers"]) >= 2 else 0)
        if utility > best_utility:
            best_text, best_conf, best_utility = t, c, utility
    return best_text, min(1.0, max(0.0, best_conf))


def sample_scoreboard_observations(
    video_path: Path,
    rois: Iterable[dict],
    duration_seconds: float,
    max_samples: int = 48,
) -> list[ScoreboardObservation]:
    if not tesseract_available():
        return []
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened() or duration_seconds <= 0:
        return []
    try:
        candidates = list(rois)[:2]
        if not candidates:
            return []
        n = max(8, min(max_samples, max(8, int(duration_seconds / 12))))
        end = max(0.0, duration_seconds - 0.25)
        times = np.linspace(0.0, end, n)
        observations: list[ScoreboardObservation] = []
        for second in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(second) * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            best = None
            for roi_idx, roi_info in enumerate(candidates):
                rect = tuple(float(roi_info[k]) for k in ("x", "y", "w", "h"))
                text, confidence = ocr_image(_roi(frame, rect))
                parsed = parse_scoreboard_text(text)
                useful = parsed["clock_seconds"] is not None or parsed["period"] is not None or (parsed["home_score"] is not None)
                if not useful:
                    continue
                obs = ScoreboardObservation(
                    second=round(float(second), 2), roi_name=str(roi_info.get("name", "candidate")),
                    raw_text=text, normalized_text=parsed["normalized_text"],
                    ocr_confidence=round(confidence, 3), period=parsed["period"],
                    clock_seconds=parsed["clock_seconds"], numbers=parsed["numbers"],
                    home_score=parsed["home_score"], away_score=parsed["away_score"],
                )
                if best is None or obs.ocr_confidence > best.ocr_confidence:
                    best = obs
                if roi_idx == 0 and confidence >= 0.45 and parsed["clock_seconds"] is not None:
                    break
            if best:
                observations.append(best)
        return observations
    finally:
        cap.release()
