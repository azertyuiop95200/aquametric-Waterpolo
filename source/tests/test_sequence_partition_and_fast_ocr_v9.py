import os

from services.deep_analysis_sequences import _dedupe_targets, _target, _youtube_segment_embed
from services.mosaic_match_analysis import _ocr_target_seconds
from services.scoreboard_ocr import _ocr_timeout_seconds


def _row(second, start, end, title):
    return _target(
        kind="verified",
        second=second,
        title=title,
        summary=title,
        confidence=1.0,
        start_second=start,
        end_second=end,
        source="test",
    )


def test_sequence_playback_windows_are_partitioned_without_overlap():
    rows = [
        _row(10.0, 5.0, 18.0, "A"),
        _row(14.5, 9.0, 22.0, "B"),
        _row(25.0, 20.0, 32.0, "C"),
    ]
    out = _dedupe_targets(rows, min_gap=2.0)
    assert len(out) == 3
    for left, right in zip(out, out[1:]):
        assert float(left["end_second"]) <= float(right["start_second"])
    assert any(row.get("playback_partitioned") for row in out)


def test_near_duplicate_moments_are_merged_before_playback_partition():
    rows = [
        _row(10.0, 5.0, 16.0, "Goal candidate"),
        _row(11.2, 7.0, 17.0, "Score change"),
    ]
    out = _dedupe_targets(rows)
    assert len(out) == 1
    assert out[0]["aliases"]


def test_youtube_sequence_embed_is_explicitly_bounded():
    url = _youtube_segment_embed("https://www.youtube.com/watch?v=abcdefghijk", 123.4, 131.9)
    assert "/embed/abcdefghijk" in url
    assert "start=123" in url
    assert "end=131" in url
    assert "loop=0" in url


def test_focused_ocr_plan_caps_work_and_keeps_action_peaks():
    targets = _ocr_target_seconds(1800.0, 112, [333.0, 777.0, 1201.0])
    assert 16 <= len(targets) <= 64
    assert targets == sorted(targets)
    assert any(abs(value - 333.0) < 0.8 for value in targets)
    assert any(abs(value - 777.0) < 0.8 for value in targets)
    assert targets[0] == 0.0


def test_individual_tesseract_call_timeout_is_bounded(monkeypatch):
    monkeypatch.setenv("AQUAMETRIC_OCR_CALL_TIMEOUT", "999")
    assert _ocr_timeout_seconds() == 8.0
    monkeypatch.setenv("AQUAMETRIC_OCR_CALL_TIMEOUT", "0.1")
    assert _ocr_timeout_seconds() == 0.8
