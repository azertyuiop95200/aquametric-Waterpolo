"""Separately sourced match facts: never pretend a title or fixture is video OCR.

These numbers describe a *published claim*, not video-confirmed events. A source
match only applies to the exact video ID and cannot populate event/player stats.
"""
from __future__ import annotations

from urllib.parse import urlparse, parse_qs

KNOWN_SOURCE_FACTS = {
    "f_WzRHjybgU": {
        "home_team": "Granville WP",
        "away_team": "CN Marseille",
        "home_goals": 9,
        "away_goals": 25,
        "competition": "Élite féminine",
        "match_date": "2026-11-13",
        "score_source": "Titre public de la vidéo YouTube",
        "source_title": "Elite F Ganville WP 9 / 25 CN Marseille",
        "source_url": "https://www.youtube.com/watch?v=f_WzRHjybgU",
        "fixture_source": "https://www.extranat.fr/waterpolo/cgi-bin/wp_calendar.php?action=structure&structure=3021",
        "verification_level": "source_claim_not_image_verified",
    },
}


def declared_match_facts(video_url: str) -> dict | None:
    from services.video import youtube_embed
    embed=youtube_embed(video_url or "")
    if not embed:
        return None
    video_id=urlparse(embed).path.rsplit("/",1)[-1]
    source=KNOWN_SOURCE_FACTS.get(video_id)
    if not source:
        return None
    return {
        **source,
        "video_id":video_id,
        "goal_difference_home":source["home_goals"]-source["away_goals"],
        "total_goals":source["home_goals"]+source["away_goals"],
        "claim_only":True,
    }
