import json

from sqlalchemy import select

from models import MatchLibraryItem, LibraryPlayerMatchStat
from services.benchmark_matches import BENCHMARK_MATCHES


def _official_source(item):
    sources = item.get("official_sources") or []
    return next((s.get("url", "") for s in sources if s.get("url")), "")


def _official_video(item):
    sources = item.get("official_sources") or []
    return next((s.get("url", "") for s in sources if "video" in (s.get("label", "").lower())), "")


def _competition_level(item):
    text = f"{item.get('competition','')} {item.get('title','')}".lower()
    if "u20" in text or "under 20" in text or "under-20" in text:
        return 4
    if "world cup" in text or "world championship" in text:
        return 5
    return 4


def _existing_canonical_match(db, item, score):
    """Find the same sporting match even if the benchmark uses another key/title."""
    year = (item.get("date", "")[:4] or "")
    return db.scalar(
        select(MatchLibraryItem).where(
            MatchLibraryItem.team_a == item.get("team_a", ""),
            MatchLibraryItem.team_b == item.get("team_b", ""),
            MatchLibraryItem.score_a == score[0],
            MatchLibraryItem.score_b == score[1],
            MatchLibraryItem.season == year,
        )
    )


def seed_benchmark_match_evidence(db):
    """Promote authoritative benchmark facts into the shared evidence library.

    Only explicitly attributed player statistics are persisted. Team totals such as
    combined goalkeeper saves or total shots stay in match metadata and never become
    individual player metrics unless the benchmark names the player unambiguously.
    Existing canonical library matches are enriched in place rather than duplicated.
    """
    for item in BENCHMARK_MATCHES:
        key = item["id"]
        score = item.get("final_score") or [None, None]
        row = db.scalar(select(MatchLibraryItem).where(MatchLibraryItem.external_key == key))
        if not row:
            row = _existing_canonical_match(db, item, score)
        metadata = {
            "_aquametric": {
                "competition_level": _competition_level(item),
                "source_tier": "world_aquatics_official",
                "evidence_scope": "official_benchmark_attributions",
                "scorer_list_complete": False,
                "benchmark": True,
                "benchmark_id": key,
                "match_date": item.get("date", ""),
            },
            "team_shots": item.get("shots", {}),
            "extra_player": item.get("extra_player", {}),
            "penalties": item.get("penalties", {}),
            "team_steals": item.get("steals", {}),
            "goalkeeper_saves": item.get("goalkeeper_saves", {}),
        }
        if not row:
            row = MatchLibraryItem(
                external_key=key,
                title=item.get("title", ""),
                competition=item.get("competition", ""),
                season=(item.get("date", "")[:4] or ""),
                entity_type="national_team",
                team_a=item.get("team_a", ""),
                team_b=item.get("team_b", ""),
                score_a=score[0],
                score_b=score[1],
                quarter_scores_json=json.dumps(item.get("quarters", [])),
                video_url=_official_video(item),
                video_kind=item.get("video_type", "official_video"),
                official_source_url=_official_source(item),
                analysis_status="official_benchmark_evidence",
                tactical_summary=" ".join(item.get("turning_points", [])),
                team_stats_json=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(row)
            db.flush()
        else:
            # Preserve the canonical library identity/title while enriching evidence.
            row.video_url = _official_video(item) or row.video_url
            row.official_source_url = _official_source(item) or row.official_source_url
            row.analysis_status = "official_benchmark_evidence"
            row.team_stats_json = json.dumps(metadata, ensure_ascii=False)

        for team_name, scorers in (item.get("scoring_highlights") or {}).items():
            for player_name, goals in scorers.items():
                stat = db.scalar(select(LibraryPlayerMatchStat).where(
                    LibraryPlayerMatchStat.library_match_id == row.id,
                    LibraryPlayerMatchStat.player_name == player_name,
                ))
                note = (
                    "Player scoring total explicitly attributed in an official World Aquatics benchmark source. "
                    "The benchmark scorer dictionary is not assumed to be a complete team scorer list."
                )
                if not stat:
                    db.add(LibraryPlayerMatchStat(
                        library_match_id=row.id,
                        team_name=team_name,
                        player_name=player_name,
                        goals=int(goals),
                        source_quality="world_aquatics_official",
                        note=note,
                    ))
                else:
                    stat.team_name = team_name
                    stat.goals = int(goals)
                    stat.source_quality = "world_aquatics_official"
                    stat.note = note
    db.commit()
