from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]


def test_tactics_hub_template_compiles_and_keeps_multi_frame_contract():
    source = (ROOT / "templates" / "knowledge.html").read_text(encoding="utf-8")
    Environment().parse(source)
    assert source.count("{{ frame(") >= 25
    assert 'data-hub-version="2026-08-29-v2"' in source
    assert "M-zone : 6 schémas de rotation" in source
    assert "5v6 : rotation 3-2 en 5 schémas" in source
