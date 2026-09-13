from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]


def test_tactics_hub_template_compiles_and_keeps_multi_frame_contract():
    source = (ROOT / "templates" / "knowledge.html").read_text(encoding="utf-8")
    Environment().parse(source)
    assert source.count("{{ frame(") >= 25
    assert source.count("{{ freeze(") >= 20
    assert 'data-hub-version="2026-09-02-coach-room"' in source
    assert 'data-wing-reference="O1-O5-2to3m"' in source
    assert "M-zone · 8 images de rotation" in source
    assert "6v5 puis 5v6 · 10 images" in source
    assert source.count("youtube-nocookie.com/embed/") >= 4
