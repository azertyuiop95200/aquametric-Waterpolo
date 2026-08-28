from __future__ import annotations

import asyncio
import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models import OfficialDataSource, OfficialFixture, OfficialStanding, OfficialTeamStat, DataRefreshRun
from services.official_fixture_evidence import promote_official_fixtures

REQUEST_TIMEOUT = float(os.getenv("OFFICIAL_DATA_HTTP_TIMEOUT", "10"))
USER_AGENT = "AquaMetric/0.4 official-water-polo-data (+research/analysis platform)"

SEED_SOURCES = [
    dict(name="World Aquatics — Water Polo calendar", provider="World Aquatics", region="International", url="https://www.worldaquatics.com/water-polo/calendar", parser_kind="status_only", refresh_interval_hours=12),
    dict(name="World Aquatics — Water Polo rankings", provider="World Aquatics", region="International", url="https://www.worldaquatics.com/water-polo/rankings", parser_kind="status_only", refresh_interval_hours=24),
    dict(name="European Aquatics — Schedule & Results", provider="European Aquatics", region="Europe", url="https://europeanaquatics.org/events/schedule-and-results/", parser_kind="status_only", refresh_interval_hours=12),
    dict(name="RFEN — Competition discovery", provider="RFEN", region="Spain", url="https://rfen.es/especialidades/waterpolo/competiciones/", parser_kind="rfen_discovery", refresh_interval_hours=24),
    dict(name="FFN — Water-polo regulations", provider="FFN", region="France", url="https://www.ffnatation.fr/reglements-du-water-polo", parser_kind="status_only", refresh_interval_hours=24),
    dict(name="FIN — Pallanuoto", provider="FIN", region="Italy", url="https://www.federnuoto.it/home/pallanuoto.html", parser_kind="status_only", refresh_interval_hours=24),
    dict(name="MVLSZ — Hungarian water polo", provider="MVLSZ", region="Hungary", url="https://waterpolo.hu/", parser_kind="status_only", refresh_interval_hours=24),
]

RFEN_ALLOWED = re.compile(r"(?:Divisi[oó]n de Honor|Primera Divisi[oó]n|Segunda Divisi[oó]n).*(?:Masculina|Femenina)", re.I)
MATCH_LABEL = re.compile(r"^Jornada\s+\d+\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+(.+)$", re.I)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def seed_official_sources(db: Session) -> None:
    for item in SEED_SOURCES:
        found = db.scalar(select(OfficialDataSource).where(OfficialDataSource.name == item["name"]))
        if not found:
            db.add(OfficialDataSource(**item))
    db.commit()


def _clean_strings(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return [re.sub(r"\s+", " ", s).strip() for s in soup.stripped_strings if re.sub(r"\s+", " ", s).strip()]


def parse_rfen_fixtures(html: str, source_url: str, competition: str = "") -> list[dict]:
    strings = _clean_strings(html)
    rows: list[dict] = []
    labels = [i for i, token in enumerate(strings) if MATCH_LABEL.match(token)]
    for idx, start in enumerate(labels):
        end = labels[idx + 1] if idx + 1 < len(labels) else min(len(strings), start + 30)
        block = strings[start:end]
        m = MATCH_LABEL.match(block[0])
        if not m:
            continue
        date, time, status_raw = m.groups()
        payload = block[1:]
        # Team names are the first two non-numeric strings after the match label.
        team_positions = [i for i, token in enumerate(payload) if not token.isdigit() and token.lower() not in {"image"}]
        if len(team_positions) < 2:
            continue
        hp, ap = team_positions[0], team_positions[1]
        home = payload[hp]
        away = payload[ap]
        home_nums = [int(x) for x in payload[hp + 1:ap] if x.isdigit()]
        away_nums = [int(x) for x in payload[ap + 1:] if x.isdigit()]
        home_score = home_nums[0] if home_nums else None
        away_score = away_nums[0] if away_nums else None
        key_raw = f"{competition}|{date}|{time}|{home}|{away}"
        rows.append({
            "external_key": hashlib.sha1(key_raw.encode("utf-8")).hexdigest(),
            "competition": competition,
            "season": _season_from_competition(competition),
            "category": "Women" if "femenina" in competition.lower() else ("Men" if "masculina" in competition.lower() else ""),
            "start_text": f"{date} {time}",
            "home_team": home,
            "away_team": away,
            "home_score": home_score,
            "away_score": away_score,
            "status": "final" if "final" in status_raw.lower() else status_raw.lower(),
            "source_url": source_url,
        })
    return rows


def parse_rfen_standings(html: str, source_url: str, competition: str = "") -> list[dict]:
    strings = _clean_strings(html)
    try:
        start = next(i for i, token in enumerate(strings) if token.lower() == "posición")
    except StopIteration:
        return []
    tokens = strings[start + 1:]
    # Skip header labels until the first standalone position integer.
    pos = 0
    while pos < len(tokens) and not (tokens[pos].isdigit() and 1 <= int(tokens[pos]) <= 100):
        pos += 1
    rows = []
    while pos < len(tokens):
        if not tokens[pos].isdigit():
            pos += 1
            continue
        position = int(tokens[pos])
        if position < 1 or position > 100 or pos + 2 >= len(tokens):
            break
        team = tokens[pos + 1]
        if team.isdigit() or team.lower() in {"image"}:
            pos += 1
            continue
        nums = []
        j = pos + 2
        while j < len(tokens) and tokens[j].isdigit() and len(nums) < 9:
            nums.append(int(tokens[j])); j += 1
        if len(nums) < 9:
            pos += 1
            continue
        points, played, won, lost, _pgp, _ppp, gf, ga, diff = nums[:9]
        rows.append({
            "competition": competition,
            "season": _season_from_competition(competition),
            "category": "Women" if "femenina" in competition.lower() else ("Men" if "masculina" in competition.lower() else ""),
            "position": position,
            "team_name": team,
            "points": points,
            "played": played,
            "won": won,
            "lost": lost,
            "goals_for": gf,
            "goals_against": ga,
            "goal_diff": diff,
            "source_url": source_url,
        })
        pos = j
    return rows


RFEN_STAT_METRICS = ["G", "GP", "GP-5P", "PE-F", "EX20", "ED-SS", "EX-PE", "EX-BR", "ED-CS", "TR", "PE"]


def parse_rfen_team_stats(html: str, source_url: str, competition: str = "") -> list[dict]:
    strings = _clean_strings(html)
    try:
        start = next(i for i, token in enumerate(strings) if token.lower() == "nombre")
    except StopIteration:
        return []
    tokens = strings[start + 1:]
    # Skip the metric headers shown immediately after Nombre.
    i = 0
    while i < len(tokens) and tokens[i] in RFEN_STAT_METRICS:
        i += 1
    rows = []
    n = len(RFEN_STAT_METRICS)
    while i < len(tokens):
        team = tokens[i]
        if team.isdigit() or team in RFEN_STAT_METRICS or team.lower() in {"image", "vista", "vista por equipos", "vista por jugadores"}:
            i += 1; continue
        values = tokens[i + 1:i + 1 + n]
        if len(values) < n or not all(v.lstrip("-+").replace(".", "", 1).isdigit() for v in values):
            i += 1; continue
        for metric, raw in zip(RFEN_STAT_METRICS, values):
            rows.append({
                "competition": competition, "season": _season_from_competition(competition),
                "category": "Women" if "femenina" in competition.lower() else ("Men" if "masculina" in competition.lower() else ""),
                "team_name": team, "metric": metric, "value": float(raw), "source_url": source_url,
            })
        i += 1 + n
    return rows

def _season_from_competition(name: str) -> str:
    m = re.search(r"(\d{2}/\d{2})", name)
    return m.group(1) if m else ""


def discover_rfen_competitions(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for a in soup.find_all("a", href=True):
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        if not RFEN_ALLOWED.search(text):
            continue
        href = urljoin(base_url, a["href"])
        m = re.search(r"/competicion/(\d+)/", href)
        if not m:
            continue
        results_url = re.sub(r"/(?:resumen|equipos|estadisticas|resultados)/?$", "/resultados/", href)
        found.append({"name": f"RFEN — {text}", "url": results_url, "competition": text})
    # Deduplicate by URL while keeping newest/first visible label.
    unique = {}
    for item in found:
        unique[item["url"]] = item
    return list(unique.values())


def _find_classification_url(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        if "clasificación" in a.get_text(" ", strip=True).lower() or "clasificacion" in a.get_text(" ", strip=True).lower():
            href = urljoin(base_url, a["href"])
            if "/clasificacion" in href:
                return href
    return None



def _find_statistics_url(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        href = urljoin(base_url, a["href"])
        if ("estadísticas" in text or "estadisticas" in text) and "/estadisticas" in href:
            return href
    return None

def refresh_source(db: Session, source: OfficialDataSource) -> DataRefreshRun:
    run = DataRefreshRun(source_id=source.id, status="started")
    db.add(run); db.commit(); db.refresh(run)
    source.last_checked_at = utcnow()
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(source.url)
            response.raise_for_status()
            html = response.text
            count = 0
            if source.parser_kind == "rfen_discovery":
                discovered = discover_rfen_competitions(html, source.url)
                for item in discovered:
                    existing = db.scalar(select(OfficialDataSource).where(OfficialDataSource.url == item["url"]))
                    if not existing:
                        db.add(OfficialDataSource(
                            name=item["name"], provider="RFEN", region="Spain", url=item["url"],
                            parser_kind="rfen_competition", refresh_interval_hours=12, enabled=True,
                        ))
                        count += 1
                db.commit()
            elif source.parser_kind == "rfen_competition":
                competition = source.name.replace("RFEN — ", "", 1)
                fixtures = parse_rfen_fixtures(html, source.url, competition)
                standings = []
                team_stats = []
                classification_url = _find_classification_url(html, source.url)
                if classification_url:
                    sr = client.get(classification_url); sr.raise_for_status()
                    standings = parse_rfen_standings(sr.text, classification_url, competition)
                stats_url = _find_statistics_url(html, source.url)
                if stats_url:
                    tr = client.get(stats_url); tr.raise_for_status()
                    team_stats = parse_rfen_team_stats(tr.text, stats_url, competition)
                if fixtures:
                    db.execute(delete(OfficialFixture).where(OfficialFixture.source_id == source.id))
                    for item in fixtures:
                        db.add(OfficialFixture(source_id=source.id, **item))
                if standings:
                    db.execute(delete(OfficialStanding).where(OfficialStanding.source_id == source.id))
                    for item in standings:
                        db.add(OfficialStanding(source_id=source.id, **item))
                if team_stats:
                    db.execute(delete(OfficialTeamStat).where(OfficialTeamStat.source_id == source.id))
                    for item in team_stats:
                        db.add(OfficialTeamStat(source_id=source.id, **item))
                count = len(fixtures) + len(standings) + len(team_stats)
                db.commit()
            else:
                # Source freshness is still valuable even when a stable parser/API is not yet available.
                count = source.records_count
            source.last_success_at = utcnow()
            source.last_error = ""
            source.records_count = count
            run.status = "success"
            run.records_count = count
            run.message = f"Checked official source successfully; {count} structured records refreshed."
    except Exception as exc:
        source.last_error = str(exc)[:1000]
        run.status = "failed"
        run.message = source.last_error
    run.completed_at = utcnow()
    db.commit()
    return run


def source_is_due(source: OfficialDataSource, now: datetime | None = None) -> bool:
    if not source.enabled:
        return False
    now = now or utcnow()
    if not source.last_checked_at:
        return True
    return source.last_checked_at + timedelta(hours=max(1, source.refresh_interval_hours)) <= now


def refresh_due_sources(db: Session, force: bool = False, max_sources: int = 20) -> list[DataRefreshRun]:
    sources = db.scalars(select(OfficialDataSource).where(OfficialDataSource.enabled == True).order_by(OfficialDataSource.id)).all()
    runs = []
    for source in sources[:max_sources]:
        if force or source_is_due(source):
            runs.append(refresh_source(db, source))
    # Promote every final structured women's result after a refresh pass. This is
    # idempotent and deliberately creates match/team evidence only, never fake players.
    promote_official_fixtures(db)
    return runs


async def recurring_refresh_loop(session_factory, every_minutes: int = 30):
    while True:
        try:
            db = session_factory()
            try:
                seed_official_sources(db)
                refresh_due_sources(db, force=False)
            finally:
                db.close()
        except Exception:
            pass
        await asyncio.sleep(max(15, every_minutes) * 60)
