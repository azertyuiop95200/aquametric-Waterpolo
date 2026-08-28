import hashlib
import json
import re

from sqlalchemy import select

from models import OfficialDataSource, OfficialFixture, MatchLibraryItem, ScoutingTeam

FINAL_STATUSES = {"final", "finished", "complete", "completed"}
WOMEN_MARKERS = ("women", "women's", "femenina", "féminine", "femminile", "dames")


def _is_women_fixture(fixture: OfficialFixture) -> bool:
    category = (fixture.category or "").strip().lower()
    if category == "women":
        return True
    text = f"{fixture.competition or ''} {fixture.category or ''}".lower()
    return any(marker in text for marker in WOMEN_MARKERS)


def _is_finished(fixture: OfficialFixture) -> bool:
    status = (fixture.status or "").strip().lower()
    return (
        status in FINAL_STATUSES
        or status.startswith("final")
        or (fixture.home_score is not None and fixture.away_score is not None and status not in {"scheduled", "postponed", "cancelled", "canceled"})
    )


def _season_label(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    # Normalize RFEN-style 25/26 to an unambiguous season label.
    m = re.fullmatch(r"(\d{2})/(\d{2})", raw)
    if m:
        first, second = int(m.group(1)), int(m.group(2))
        return f"20{first:02d}-20{second:02d}"
    return raw


def _match_key(fixture: OfficialFixture) -> str:
    return f"OFFICIAL-FIXTURE-{fixture.source_id}-{fixture.external_key}"[:255]


def _stable_team_key(source: OfficialDataSource, team_name: str) -> str:
    """Return the same scouting key across Python processes and database rebuilds."""
    provider = re.sub(r"[^a-z0-9]+", "-", (source.provider or "official").strip().lower()).strip("-") or "official"
    identity = "|".join(
        [
            (source.provider or "official").strip().casefold(),
            (source.region or "").strip().casefold(),
            (team_name or "").strip().casefold(),
            "women",
        ]
    )
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    return f"auto-{provider[:32]}-{digest}"


def _find_same_match(db, fixture: OfficialFixture):
    season = _season_label(fixture.season)
    candidates = db.scalars(
        select(MatchLibraryItem).where(
            MatchLibraryItem.team_a == fixture.home_team,
            MatchLibraryItem.team_b == fixture.away_team,
            MatchLibraryItem.score_a == fixture.home_score,
            MatchLibraryItem.score_b == fixture.away_score,
        )
    ).all()
    for row in candidates:
        if not season or row.season in {season, fixture.season}:
            return row
    return None


def _ensure_scouting_team(db, team_name: str, source: OfficialDataSource, fixture: OfficialFixture):
    if not team_name:
        return None
    team = db.scalar(select(ScoutingTeam).where(ScoutingTeam.name == team_name))
    if not team:
        team = ScoutingTeam(
            external_key=_stable_team_key(source, team_name),
            name=team_name,
            team_type="club",
            category="Women",
            age_group="Senior",
            country=source.region or "",
            competition=fixture.competition or "",
            season_label=_season_label(fixture.season),
            roster_status="match_results_only",
            source_url=fixture.source_url or source.url or "",
            source_note="Automatically discovered from a structured official women’s competition result. Roster and player-level statistics still require separate evidence.",
            priority=45,
        )
        db.add(team)
        db.flush()
    else:
        # Never downgrade richer roster evidence. Only fill gaps on an existing card.
        if not team.competition and fixture.competition:
            team.competition = fixture.competition
        if not team.season_label and fixture.season:
            team.season_label = _season_label(fixture.season)
        if not team.source_url:
            team.source_url = fixture.source_url or source.url or ""
    return team


def promote_official_fixtures(db, source_id: int | None = None) -> dict:
    """Promote final official women's fixtures into the shared evidence library.

    This function only creates match/result evidence. It deliberately creates no
    LibraryPlayerMatchStat rows because a final score does not prove who played or
    who scored. Discovered teams are added to the scouting registry with the explicit
    state ``match_results_only`` until roster/player evidence is attached.
    """
    query = select(OfficialFixture)
    if source_id is not None:
        query = query.where(OfficialFixture.source_id == source_id)
    fixtures = db.scalars(query.order_by(OfficialFixture.id)).all()
    created_matches = 0
    updated_matches = 0
    discovered_teams = 0

    for fixture in fixtures:
        if not _is_women_fixture(fixture) or not _is_finished(fixture):
            continue
        if fixture.home_score is None or fixture.away_score is None:
            continue
        source = db.get(OfficialDataSource, fixture.source_id)
        if not source:
            continue

        before_home = db.scalar(select(ScoutingTeam).where(ScoutingTeam.name == fixture.home_team))
        before_away = db.scalar(select(ScoutingTeam).where(ScoutingTeam.name == fixture.away_team))
        _ensure_scouting_team(db, fixture.home_team, source, fixture)
        _ensure_scouting_team(db, fixture.away_team, source, fixture)
        discovered_teams += int(before_home is None) + int(before_away is None)

        key = _match_key(fixture)
        row = db.scalar(select(MatchLibraryItem).where(MatchLibraryItem.external_key == key))
        if not row:
            row = _find_same_match(db, fixture)
        metadata = {
            "_aquametric": {
                "competition_level": 3,
                "source_tier": "federation_official",
                "evidence_scope": "official_result_only",
                "individual_stats_available": False,
                "fixture_id": fixture.id,
                "source_id": source.id,
                "start_text": fixture.start_text,
            }
        }
        if not row:
            row = MatchLibraryItem(
                external_key=key,
                title=f"{fixture.home_team} vs {fixture.away_team} — {fixture.competition}",
                competition=fixture.competition or "Official competition",
                season=_season_label(fixture.season),
                entity_type="club",
                team_a=fixture.home_team,
                team_b=fixture.away_team,
                score_a=fixture.home_score,
                score_b=fixture.away_score,
                quarter_scores_json="[]",
                video_url="",
                video_kind="official_result",
                official_source_url=fixture.source_url or source.url or "",
                analysis_status="official_result_only",
                tactical_summary="Official final result only. No player presence, scoring, shot, save or tactical action is inferred from the team score.",
                team_stats_json=json.dumps(metadata),
            )
            db.add(row)
            created_matches += 1
        else:
            # A richer canonical match may already exist. Do not erase richer data.
            row.official_source_url = row.official_source_url or fixture.source_url or source.url or ""
            if not row.team_stats_json or row.analysis_status == "official_result_only":
                row.team_stats_json = json.dumps(metadata)
            if row.analysis_status in {"", "official_result_only"}:
                row.analysis_status = "official_result_only"
            updated_matches += 1

    db.commit()
    return {
        "created_matches": created_matches,
        "updated_matches": updated_matches,
        "discovered_teams": discovered_teams,
    }
