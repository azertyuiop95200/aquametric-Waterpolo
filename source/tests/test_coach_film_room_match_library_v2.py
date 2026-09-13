from pathlib import Path
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_knowledge_compiles_and_is_visual_coach_grade():
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
    env.get_template("knowledge.html")
    page = read("templates/knowledge.html")
    assert page.count("{{ frame(") >= 25
    assert page.count("{{ freeze(") >= 20
    assert page.count("youtube-nocookie.com/embed/") >= 4
    assert 'data-wing-reference="O1-O5-2to3m"' in page
    assert "Séance vidéo coach" in page
    assert "VIDEO → ARRÊT → LECTURE → CORRECTION → PISCINE" in page
    assert "Israël féminin U20" in page


def test_match_library_reviews_every_seeded_reference_match():
    page = read("templates/analysis_library_detail.html")
    keys = [
        "EA-CLW-2024-FINAL-SABA-OLY",
        "EA-CLW-2025-FINAL-SABA-SA",
        "WA-U20W-2025-SF-ESP-GRE",
        "WA-U20W-2025-F-USA-ESP",
        "WA-U20W-2025-BRONZE-ITA-GRE",
        "WA-U20W-2025-7TH-CRO-BRA",
    ]
    for key in keys:
        assert key in page
    assert "FILM ROOM" in page
    assert "ARRÊTS SUR IMAGE PÉDAGOGIQUES" in page
    assert "PLAN DE SÉANCE" in page
    assert page.count("set review_title=") >= 6


def test_embeddable_library_matches_stay_inside_the_site():
    overview = read("templates/analysis_library.html")
    detail = read("templates/analysis_library_detail.html")
    for video_id in ("pIJu8tQT7-I", "bF-Am10VtF4", "TnZjH0VeCsQ"):
        assert video_id in overview
        assert video_id in detail
    assert "Open official video" not in detail


def test_separate_tactics_entry_stays_removed():
    base = read("templates/base.html")
    assert 'href="/tactical-chess"' not in base
    assert base.count("Tactique & Connaissance") >= 1
