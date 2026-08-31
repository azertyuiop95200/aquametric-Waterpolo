from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from db import get_db
from models import (
    User,
    Club,
    Team,
    Player,
    Match,
    ScoutingTeam,
    ScoutingPlayer,
    OfficialFixture,
    OfficialStanding,
    MatchLibraryItem,
)
from services.video import youtube_embed, is_http_url

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _clean(value: str, max_len: int = 180) -> str:
    return (value or "").strip()[:max_len]


def _key(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _catalog_entry(name: str, *, category: str = "", country: str = "", competition: str = "", source: str = ""):
    return {
        "name": _clean(name),
        "category": _clean(category, 40),
        "country": _clean(country, 80),
        "competition": _clean(competition, 180),
        "source": source,
    }


def analysis_team_catalog(db: Session, user_id: int) -> list[dict]:
    """Return every team name currently represented in the AquaMetric database.

    The analysis workspace is intentionally broader than "My team": it combines
    the user's local teams with scouting, official-results and match-library data.
    """
    catalog: dict[str, dict] = {}

    def add(entry: dict):
        name = entry.get("name", "")
        if not name:
            return
        k = _key(name)
        current = catalog.get(k)
        if current is None:
            catalog[k] = entry
            return
        # Prefer richer metadata without changing the canonical display name of
        # an existing workspace/scouting entry.
        for field in ("category", "country", "competition", "source"):
            if not current.get(field) and entry.get(field):
                current[field] = entry[field]

    local_teams = db.scalars(
        select(Team).where(Team.owner_id == user_id).order_by(Team.name)
    ).all()
    for team in local_teams:
        add(_catalog_entry(
            team.name,
            category=team.category,
            country=team.club.country if team.club else "",
            competition=team.club.division if team.club else "",
            source="workspace",
        ))

    scouting_teams = db.scalars(
        select(ScoutingTeam).order_by(ScoutingTeam.country, ScoutingTeam.name)
    ).all()
    for team in scouting_teams:
        add(_catalog_entry(
            team.name,
            category=team.category,
            country=team.country,
            competition=team.competition,
            source="scouting",
        ))

    clubs = db.scalars(
        select(Club)
        .where(or_(Club.owner_id.is_(None), Club.owner_id == user_id))
        .order_by(Club.country, Club.name)
    ).all()
    for club in clubs:
        add(_catalog_entry(
            club.name,
            category=club.category,
            country=club.country,
            competition=club.division,
            source="club",
        ))

    for name, category, competition in db.execute(
        select(OfficialStanding.team_name, OfficialStanding.category, OfficialStanding.competition)
    ).all():
        add(_catalog_entry(name, category=category, competition=competition, source="official-standing"))

    for home, away, category, competition in db.execute(
        select(
            OfficialFixture.home_team,
            OfficialFixture.away_team,
            OfficialFixture.category,
            OfficialFixture.competition,
        )
    ).all():
        add(_catalog_entry(home, category=category, competition=competition, source="official-fixture"))
        add(_catalog_entry(away, category=category, competition=competition, source="official-fixture"))

    for team_a, team_b, competition in db.execute(
        select(MatchLibraryItem.team_a, MatchLibraryItem.team_b, MatchLibraryItem.competition)
    ).all():
        add(_catalog_entry(team_a, competition=competition, source="match-library"))
        add(_catalog_entry(team_b, competition=competition, source="match-library"))

    entries = list(catalog.values())
    entries.sort(key=lambda item: (
        0 if "granville" in _key(item["name"]) else 1,
        _key(item.get("country", "")),
        _key(item["name"]),
    ))
    return entries


def _canonical_catalog_name(catalog: list[dict], name: str) -> str:
    wanted = _key(name)
    for entry in catalog:
        if _key(entry["name"]) == wanted:
            return entry["name"]
    return _clean(name)


def _find_catalog_meta(catalog: list[dict], name: str) -> dict:
    wanted = _key(name)
    for entry in catalog:
        if _key(entry["name"]) == wanted:
            return entry
    return _catalog_entry(name, source="manual")


def _ensure_workspace_team(db: Session, user_id: int, requested_name: str, catalog: list[dict]) -> Team:
    name = _canonical_catalog_name(catalog, requested_name)
    if not name:
        raise HTTPException(400, detail="Team is required.")

    existing = db.scalar(
        select(Team).where(
            Team.owner_id == user_id,
            func.lower(Team.name) == name.lower(),
        )
    )
    if existing:
        return existing

    meta = _find_catalog_meta(catalog, name)
    scouting = db.scalar(
        select(ScoutingTeam).where(func.lower(ScoutingTeam.name) == name.lower()).order_by(ScoutingTeam.id)
    )
    category = _clean((scouting.category if scouting else meta.get("category")) or "Mixed/Other", 30)
    country = _clean((scouting.country if scouting else meta.get("country")) or "International", 80)
    competition = _clean((scouting.competition if scouting else meta.get("competition")) or "", 120)

    club = db.scalar(
        select(Club)
        .where(
            func.lower(Club.name) == name.lower(),
            or_(Club.owner_id.is_(None), Club.owner_id == user_id),
        )
        .order_by(Club.owner_id.is_(None).desc(), Club.id)
    )
    if not club:
        club = Club(
            name=name,
            country=country,
            division=competition,
            category=category,
            owner_id=user_id,
        )
        db.add(club)
        db.flush()

    team = Team(
        name=name,
        club_id=club.id,
        owner_id=user_id,
        category=category,
    )
    db.add(team)
    db.flush()

    # When the selected catalogue team has a sourced roster, make it available
    # immediately to the normal match-analysis/player pipeline.
    if scouting:
        scout_players = db.scalars(
            select(ScoutingPlayer)
            .where(ScoutingPlayer.scouting_team_id == scouting.id)
            .order_by(ScoutingPlayer.cap_number, ScoutingPlayer.name)
        ).all()
        for player in scout_players:
            db.add(Player(
                team_id=team.id,
                name=player.name,
                cap_number=player.cap_number,
                primary_role=_clean(player.role or "AI to infer", 80),
            ))
        db.flush()

    return team


def _default_team_name(catalog: list[dict], local_teams: list[Team]) -> str:
    for team in local_teams:
        if "granville" in _key(team.name):
            return team.name
    for entry in catalog:
        if "granville" in _key(entry["name"]):
            return entry["name"]
    if local_teams:
        return local_teams[0].name
    return catalog[0]["name"] if catalog else ""


@router.get("/matches/new", response_class=HTMLResponse)
def universal_new_match_page(request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    local_teams = db.scalars(
        select(Team).where(Team.owner_id == user.id).order_by(Team.name)
    ).all()
    catalog = analysis_team_catalog(db, user.id)
    # Imported lazily to avoid a circular import while main.py installs extensions.
    import main as core
    return TEMPLATES.TemplateResponse(
        request,
        "match_new.html",
        {
            "request": request,
            "user": user,
            "app_name": core.APP_NAME,
            "web_demo_mode": core.WEB_DEMO_MODE,
            "teams": local_teams,
            "team_catalog": catalog,
            "default_team_name": _default_team_name(catalog, local_teams),
            "max_upload_mb": core.MAX_UPLOAD_MB,
        },
    )


@router.post("/matches")
def universal_create_match(
    request: Request,
    team_name: str = Form(""),
    team_id: str = Form(""),
    opponent: str = Form(...),
    competition: str = Form(""),
    match_date: str = Form(""),
    video_url: str = Form(""),
    video_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    catalog = analysis_team_catalog(db, user.id)

    team = None
    if team_id.strip().isdigit():
        candidate = db.get(Team, int(team_id.strip()))
        if candidate and candidate.owner_id == user.id:
            team = candidate
    if team is None:
        team = _ensure_workspace_team(db, user.id, team_name, catalog)

    opponent = _canonical_catalog_name(catalog, _clean(opponent))
    if not opponent:
        raise HTTPException(400, detail="Opponent is required.")

    video_url = video_url.strip()
    if video_url and not is_http_url(video_url):
        raise HTTPException(400, detail="Only http/https video links are supported.")

    import main as core
    video_source, video_path = "none", ""
    if video_file and video_file.filename:
        video_path = core.save_video_upload(video_file, user.id, team.id)
        video_source = "upload"
    elif video_url:
        video_source = "youtube" if youtube_embed(video_url) else "url"

    match = Match(
        owner_id=user.id,
        team_id=team.id,
        opponent=opponent,
        competition=_clean(competition, 160),
        match_date=_clean(match_date, 32),
        video_source=video_source,
        video_url=video_url,
        video_path=video_path,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return RedirectResponse(f"/matches/{match.id}", status_code=303)
