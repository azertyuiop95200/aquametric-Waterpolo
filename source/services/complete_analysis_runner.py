from __future__ import annotations

from pathlib import Path

from services.analysis_product import build_exact_evidence_pack, run_product_analysis
from services.rapid_match_analysis import run_rapid_analysis


def run_complete_analysis(db, match, upload_dir: Path, evidence_dir: Path, *, include_audio: bool = True):
    """Use the densest CPU-safe scan available for owned video.

    URL-only matches keep the evidence-safe product path. Uploaded videos double the
    normal sparse visual density to 360 samples and use the maximum bounded OCR pass
    (96 observations), then materialize exact evidence around more verified/automatic
    targets. This remains sparse rather than pretending to understand every frame.
    """
    if match.video_source != "upload" or not match.video_path:
        return run_product_analysis(db, match, upload_dir, evidence_dir, include_audio=False)

    source_path = Path(upload_dir) / Path(match.video_path).name
    result = run_rapid_analysis(
        db,
        match,
        source_path,
        Path(evidence_dir),
        include_audio=include_audio,
        visual_samples=360,
        ocr_samples=96,
    )
    build_exact_evidence_pack(
        db,
        match,
        Path(upload_dir),
        Path(evidence_dir),
        max_verified_events=32,
        max_candidates=28,
    )
    return result
