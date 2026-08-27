"""Heuristic whistle candidate detector from owned video audio.

It looks for short, narrow-band, high-frequency energy bursts typical of referee
whistles. It deliberately emits candidates only; crowd noise and broadcast tones
can cause false positives. Future classification must fuse video/referee/clock cues.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import shutil
import subprocess
import numpy as np


@dataclass
class WhistleCandidate:
    second: float
    score: float
    peak_hz: float
    duration_hint: float

    def to_dict(self):
        return asdict(self)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _pcm_from_video(path: Path, sample_rate: int = 16000, max_seconds: int = 3 * 60 * 60) -> np.ndarray:
    if not ffmpeg_available():
        return np.array([], dtype=np.float32)
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sample_rate),
           "-t", str(max_seconds), "-f", "s16le", "pipe:1"]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=180)
    except Exception:
        return np.array([], dtype=np.float32)
    if not proc.stdout:
        return np.array([], dtype=np.float32)
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def detect_whistle_candidates(video_path: Path, sample_rate: int = 16000, limit: int = 60) -> list[WhistleCandidate]:
    audio = _pcm_from_video(Path(video_path), sample_rate)
    if audio.size < sample_rate:
        return []
    win = int(sample_rate * 0.12)
    hop = int(sample_rate * 0.06)
    hann = np.hanning(win).astype(np.float32)
    freqs = np.fft.rfftfreq(win, 1.0 / sample_rate)
    band = (freqs >= 2200) & (freqs <= 5200)
    broader = (freqs >= 500) & (freqs <= 6500)
    rows = []
    for start in range(0, audio.size - win, hop):
        frame = audio[start:start+win] * hann
        rms = float(np.sqrt(np.mean(frame * frame)) + 1e-9)
        if rms < 0.004:
            continue
        spec = np.abs(np.fft.rfft(frame)) ** 2
        total = float(spec[broader].sum() + 1e-12)
        band_power = float(spec[band].sum())
        ratio = band_power / total
        if not np.any(band):
            continue
        bspec = spec.copy(); bspec[~band] = 0
        peak_idx = int(np.argmax(bspec))
        peak = float(spec[peak_idx])
        concentration = peak / (band_power + 1e-12)
        # Narrowband high-frequency energy, weighted by audibility.
        aud = min(1.0, rms / 0.06)
        score = min(1.0, max(0.0, (ratio - 0.28) * 1.55 + (concentration - 0.18) * 1.2) * aud)
        if score >= 0.42:
            rows.append((start / sample_rate, score, float(freqs[peak_idx])))
    # Merge adjacent windows into one candidate.
    merged = []
    for second, score, hz in rows:
        if merged and second - merged[-1][0] < 0.45:
            if score > merged[-1][1]:
                merged[-1] = [second, score, hz, merged[-1][3] + hop / sample_rate]
            else:
                merged[-1][3] += hop / sample_rate
        else:
            merged.append([second, score, hz, win / sample_rate])
    ranked = sorted(merged, key=lambda r: r[1], reverse=True)[:limit]
    ranked.sort(key=lambda r: r[0])
    return [WhistleCandidate(round(s,2), round(sc,3), round(hz,1), round(d,2)) for s,sc,hz,d in ranked]
