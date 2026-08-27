"""Curated benchmark matches used to validate future AquaMetric video models.

Ground-truth values must come from authoritative sources. The benchmark registry
is intentionally small and explicit: it is for evaluation, not for fabricating
analysis on videos the system has not yet processed.
"""
from urllib.parse import urlparse, parse_qs

BENCHMARK_MATCHES = [
    {
        "id": "BENCH-001-ESP-GRE-U20W-2025",
        "video_id": "bF-Am10VtF4",
        "title": "Spain vs Greece — Women's U20 World Championship 2025 semifinal",
        "competition": "World Aquatics Women's U20 Water Polo Championships 2025",
        "date": "2025-08-15",
        "video_type": "full_match",
        "duration_seconds": 5222,
        "duration_label": "1:27:02",
        "team_a": "Spain",
        "team_b": "Greece",
        "final_score": [11, 9],
        "quarters": [[0, 3], [3, 4], [3, 0], [5, 2]],
        "shots": {"Spain": 36, "Greece": 35},
        "extra_player": {
            "Spain": {"goals": 4, "attempts": 9},
            "Greece": {"goals": 2, "attempts": 6},
        },
        "penalties": {
            "Spain": {"goals": 3, "attempts": 4},
            "Greece": {"goals": 0, "attempts": 1},
        },
        "steals": {"Spain": 4, "Greece": 2},
        "goalkeeper_saves": {"Spain_combined": 13, "Greece_Kyriakopoulou": 9},
        "scoring_highlights": {
            "Spain": {"Isabel Piralkova": 5},
            "Greece": {
                "Nefeli Krassa": 2,
                "Aspasia Fouraki": 2,
                "Foteini Tricha": 2,
                "Ariadni Karampetsou": 2,
            },
        },
        "turning_points": [
            "Greece built a 6-1 lead during the first half.",
            "Spain trailed 7-3 at halftime, then won the third quarter 3-0.",
            "Spain won the fourth quarter 5-2 to complete the comeback.",
            "Late Spanish extra-player conversions helped turn 8-8 into a decisive lead.",
        ],
        "validation_targets": [
            "full-match vs highlights classification",
            "scoreboard and quarter segmentation",
            "shot count",
            "extra-player / 5-on-6 sequence detection",
            "penalty detection",
            "steal/turnover detection",
            "goalkeeper save detection",
            "player identity and scorer attribution",
            "timeout and VAR/review context",
            "comeback / momentum sequence reconstruction",
        ],
        "official_sources": [
            {
                "label": "World Aquatics match report",
                "url": "https://www.worldaquatics.com/news/4342094/spain-makes-third-straight-u20-womens-final",
            },
            {
                "label": "World Aquatics full-session video",
                "url": "https://www.worldaquatics.com/videos/4335110/semi-final-2-day-6-world-aquatics-womens-u20-water-polo-championships-2025",
            },
        ],
    }
]


def youtube_video_id(url: str) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        return (parse_qs(parsed.query).get("v") or [None])[0]
    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0] or None
    return None


def benchmark_for_url(url: str) -> dict | None:
    video_id = youtube_video_id(url)
    if not video_id:
        return None
    return next((item for item in BENCHMARK_MATCHES if item["video_id"] == video_id), None)
