"""Evidence gate for browser-captured third-party video.

A successful MediaRecorder session proves screen pixels arrived, not that game
footage was visible. Reject near-identical long captures as unverified, and use
bounded local OCR to identify known YouTube human-verification/error pages.
Never use this gate to infer an action, score, player, or tactical statistic.
"""
from __future__ import annotations

from pathlib import Path
import re

import cv2
import numpy as np


BAD_TEXT_PATTERNS = (
    ("sign in", "not a bot"),
    ("sign in", "confirm"),
    ("verify", "human"),
    ("verify", "robot"),
    ("video unavailable",),
    ("playback error",),
    ("this video is unavailable",),
    ("connectez vous", "robot"),
    ("confirmer", "robot"),
)


def _looks_blocked(text: str) -> bool:
    plain = re.sub(r"[^a-z0-9 ]+", " ", str(text).lower())
    plain = " ".join(plain.split())
    return any(all(term in plain for term in patterns) for patterns in BAD_TEXT_PATTERNS)


def _read_frame(path: Path):
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        return None
    height, width = image.shape[:2]
    if max(height, width) > 1000:
        scale = 1000 / max(height, width)
        image = cv2.resize(image, (round(width*scale),round(height*scale)),interpolation=cv2.INTER_AREA)
    return image


def _screen_text(image) -> str:
    """Bounded CPU OCR. Run only on suspicious static frames, never per-frame."""
    try:
        from services.scoreboard_ocr import pytesseract, tesseract_available
        if not tesseract_available() or pytesseract is None:
            return ""
        h,w=image.shape[:2]
        # Search all 4 panes: the video overlay may occupy only one quarter.
        return str(pytesseract.image_to_string(image, config="--psm 11", timeout=4.0))[:1400]
    except Exception:
        return ""


def capture_source_quality(root: Path, state: dict, *, records=None, ocr=None) -> dict:
    """Classify sports-frame availability without pretending motion is a goal.

    status is one of playable_candidate, blocked, static_unverified, insufficient.
    playable_candidate is *not* a guarantee of sport footage or full coverage.
    """
    if records is None:
        from services.live_frame_match_analysis import _timeline_records
        records = _timeline_records(root, state)
    count = len(records)
    # Short sessions can retain 3–5 JPEGs and still contain a perfectly clear
    # YouTube sign-in challenge. Do not call them valid match footage merely
    # because fewer than six frames were available for comparison.
    if count < 3:
        return {"status":"insufficient", "frames_checked":count, "reason":"not_enough_retained_frames"}
    sample_count = min(6, count)
    selected = [records[round(i*(count-1)/(sample_count-1))] for i in range(sample_count)]
    images = [_read_frame(Path(row["path"])) for row in selected]
    images = [im for im in images if im is not None]
    if len(images) < 3:
        return {"status":"insufficient", "frames_checked":len(images), "reason":"frames_unreadable"}
    # Compare full captured tab across long-spaced records, at fixed resolution.
    previews=[]
    for im in images:
        gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
        previews.append(cv2.resize(gray,(192,108),interpolation=cv2.INTER_AREA))
    motion=[float(np.mean(cv2.absdiff(previews[i], previews[i-1]))) for i in range(1,len(previews))]
    high_movement=sum(value>=2.5 for value in motion)
    static=high_movement <= 1 and max(motion,default=0) < 6.0
    evidence={"frames_checked":len(images),"mean_frame_delta":round(float(np.mean(motion)),3),
              "max_frame_delta":round(max(motion,default=0),3)}
    if not static:
        return {**evidence, "status":"playable_candidate","reason":"changes_present_not_sport_verified"}

    reader=ocr or _screen_text
    text=" ".join(reader(im) for im in (images[0],images[-1]))
    if _looks_blocked(text):
        return {**evidence,"status":"blocked","reason":"player_verification_or_error_screen",
                "ocr_blocker_detected":True}
    return {**evidence,"status":"static_unverified","reason":"static_screen_not_valid_game_evidence",
            "ocr_blocker_detected":False}


def capture_is_unverified(quality: dict) -> bool:
    return (quality or {}).get("status") in {"blocked","static_unverified"}
