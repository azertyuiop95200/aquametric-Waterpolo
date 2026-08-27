from __future__ import annotations

import asyncio
import inspect
import os
import re
import subprocess
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

import main as core
import models
from db import SessionLocal

app = core.app


# ---------------------------------------------------------------------------
# Security hardening for the public Render demo
# ---------------------------------------------------------------------------

ALLOWED_HOSTS = [
    "aquametric-web-demo.onrender.com",
    "*.onrender.com",
    "localhost",
    "127.0.0.1",
    "testserver",
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_RULES = {
    "/login": (8, 60),
    "/register": (5, 60),
    "/demo-login": (10, 60),
}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _same_origin(request: Request) -> bool:
    host = request.headers.get("host", "")
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if not value:
            continue
        try:
            parsed = urlparse(value)
            return parsed.netloc == host
        except Exception:
            return False
    # Some non-browser clients omit both headers. SameSite cookies remain an
    # additional protection; do not break legitimate forms solely for absence.
    return True


def _rate_rule(path: str) -> tuple[int, int] | None:
    if path in _RATE_RULES:
        return _RATE_RULES[path]
    if "upload" in path.lower() or "video" in path.lower():
        return (12, 60)
    return None


class AquaMetricSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"} and not _same_origin(request):
            return JSONResponse({"detail": "Cross-site request rejected"}, status_code=403)

        rule = _rate_rule(request.url.path)
        if rule:
            limit, window = rule
            now = time.monotonic()
            key = f"{_client_ip(request)}:{request.url.path}"
            bucket = _RATE_BUCKETS[key]
            while bucket and bucket[0] < now - window:
                bucket.popleft()
            if len(bucket) >= limit:
                return JSONResponse(
                    {"detail": "Too many requests. Please retry shortly."},
                    status_code=429,
                    headers={"Retry-After": str(window)},
                )
            bucket.append(now)

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'self'; "
            "form-action 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self' https:; "
            "frame-src https://www.youtube.com https://www.youtube-nocookie.com;",
        )
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path not in {"/health", "/static"}:
            response.headers.setdefault("Cache-Control", "no-store")
        return response


app.add_middleware(AquaMetricSecurityMiddleware)

# Public interactive API documentation is unnecessary on the demo instance.
app.router.routes[:] = [
    route
    for route in app.router.routes
    if getattr(route, "path", None) not in {"/docs", "/redoc", "/openapi.json"}
]

# Validate that uploaded files really contain a video stream when ffprobe is
# available. The original extension/content-type/size checks remain in place.
_original_save_video_upload = getattr(core, "save_video_upload", None)


def _extract_saved_path(result: Any) -> Path | None:
    candidates = result if isinstance(result, (tuple, list)) else [result]
    for value in candidates:
        if isinstance(value, Path):
            return value
        if isinstance(value, str):
            p = Path(value)
            if p.exists():
                return p
    return None


def _verify_video_stream(path: Path | None) -> None:
    if not path or not path.exists():
        return
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        if proc.returncode != 0 or "video" not in proc.stdout.lower():
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid video stream")
    except FileNotFoundError:
        # Render image normally contains ffprobe via ffmpeg. If unavailable,
        # retain the original application validation rather than breaking upload.
        return


if _original_save_video_upload:
    if inspect.iscoroutinefunction(_original_save_video_upload):
        async def _secure_save_video_upload(*args, **kwargs):
            result = await _original_save_video_upload(*args, **kwargs)
            _verify_video_stream(_extract_saved_path(result))
            return result
    else:
        def _secure_save_video_upload(*args, **kwargs):
            result = _original_save_video_upload(*args, **kwargs)
            _verify_video_stream(_extract_saved_path(result))
            return result
    core.save_video_upload = _secure_save_video_upload


# ---------------------------------------------------------------------------
# Evidence-backed roster refresh and coach directory
# ---------------------------------------------------------------------------

FFN_FRANCE_2026 = "https://www.ffnatation.fr/sites/default/files/2026-01/DP%20FUNCHAL%202026_VF.pdf"
FFN_ELITE_2026 = "https://www.ffnatation.fr/actualites/actu-grand-public/lille-champion-de-france-2026"
FFN_ELITE_START = "https://www.ffnatation.fr/actualites/actualite-grand-public/lelite-feminine-demarre-tres-fort"
FFN_ELITE_DAY2 = "https://www.ffnatation.fr/actualites/actu-grand-public/une-deuxieme-journee-animee-en-elite-feminine"
GRANVILLE_SOURCE = "https://granville-water-polo.fr/"


def P(name, year=None, nat="FRA", role=None):
    return {"name": name, "birth_year": year, "nationality": nat, "role": role}


ROSTER_OVERRIDES = {
    "Équipe de France Femmes - Senior": {
        "aliases": ["france women senior", "france senior women", "france femmes senior", "equipe de france femmes senior", "équipe de france féminine"],
        "season": "Funchal 2026",
        "status": "OFFICIAL — Funchal 2026 event roster",
        "source": FFN_FRANCE_2026,
        "source_note": "Official FFN European Championship roster. Event roster, not a permanent all-season roster.",
        "players": [
            P("Lara Andres", 2006, "FRA", "Polyvalente"), P("Arianna Banchi", 2006, "FRA", "Polyvalente"),
            P("Kahena Benlekbir", 2002, "FRA", "Ailière / demi"), P("Jade Boughrara", 2005, "FRA", "Polyvalente"),
            P("Camelia Bouloukbachi", 2003, "FRA", "Arrière pointe / demi"), P("Léopoldine Burle", 2009, "FRA", "Ailière"),
            P("Lana Di Fraja", 2006, "FRA", "Polyvalente"), P("Emma Duflos", 2007, "FRA", "Polyvalente"),
            P("Valentine Heurtaux", 2005, "FRA", "Polyvalente"), P("Elhyne Kilic-Pegourie", 2007, "FRA", "Pointe"),
            P("Eszter Lefebvre", 2003, "FRA", "Gardienne"), P("Ona Pourtau Sire", 2009, "FRA", "Polyvalente"),
            P("Tiziana Raspo", 2005, "FRA", "Arrière pointe"), P("Romane Secheresse", 2009, "FRA", "Gardienne"),
            P("Ema Vernoux", 2004, "FRA", "Ailière / demi"),
        ],
    },
    "Granville Water Polo": {
        "aliases": ["granville"], "season": "2026-27", "status": "2026-27 roster pending official publication",
        "source": GRANVILLE_SOURCE,
        "source_note": "Club 2026-27 page is public; player names below are the observed 2025-26 group until the club publishes the new roster.",
        "players": [P(n) for n in ["Rumina Edgerton","Morgane Le Berre","Capucine Pillais","Cléo Kubas","Luce Berthonneau","Amandine Laîné","Sofia Dan","Eleni Bovali","Clémence Letourneur","Mauranne Cosnefroy","Hanae Pezres","Sofia Kolovou","Mariia Lytvyniuk","Maëlle Hequin","Carmen Sourdrille-Arnal"]],
    },
    "Lille UC Métropole Water-Polo": {
        "aliases": ["lille"], "season": "2025-26 observed", "status": "OFFICIAL MATCH-SHEET OBSERVED — 2026-27 confirmation pending",
        "source": FFN_ELITE_2026, "source_note": "Players observed in official FFN 2025-26 Elite competition evidence; not silently treated as confirmed 2026-27 roster.",
        "players": [P("Eszter Lefebvre",2003),P("Anna Pal",2001,"HUN"),P("Elhyne Kilic-Pegourie",2007),P("Lara Andres",2006),P("Giulia Sponza",2008,"ITA"),P("Clémence Goulu",2010),P("Lana Di Fraja",2006),P("Cecilia Nardini",1999,"ITA"),P("Lily Vernoux",2007),P("Carmen Baringo Romero",1998,"ESP"),P("Myriam Lizotte",1999,"CAN"),P("Maéline Ribeiro de Souza",2011,"BEL"),P("Eszter Kozár",2002,"FIN"),P("Mariam Diara Ndiaye",2007,"USA")],
    },
    "Union St-Bruno Bordeaux": {
        "aliases": ["bordeaux", "union saint-bruno"], "season": "2025-26 observed", "status": "OFFICIAL MATCH-SHEET OBSERVED — 2026-27 confirmation pending",
        "source": FFN_ELITE_2026, "source_note": "Official FFN match and Final Four evidence, 2025-26.",
        "players": [P("Pasiphaé Martineaud-Peret",2005),P("Justine Turbeau",2004),P("Robyn Jennifer Currie",2002,"CAN"),P("Juliette Ribes",2004),P("Chloé Faure",1993),P("Lou Jean Michel",2003),P("Kenza Chadly",1999),P("Anne-Fleur Doucereux",1993),P("Marion Horcholle",1997),P("Noor El Ouaret",2011),P("Sherihene Ben Mouna",2008),P("Elizabeth Grace Estelle Birch",2002,"CAN"),P("Romane Secheresse",2009),P("Maëlle Lartigaut",2008)],
    },
    "Olympic Nice Natation": {
        "aliases": ["nice", "olympic nice"], "season": "2025-26 observed", "status": "OFFICIAL MATCH-SHEET OBSERVED — 2026-27 confirmation pending",
        "source": FFN_ELITE_2026, "source_note": "Official FFN Elite evidence, 2025-26.",
        "players": [P("Mary Jane Bailey",2004,"USA"),P("Elise Cugnart",1997),P("Anna Karatekin",2007,"ESP"),P("Reese Dueringer",2008,"USA"),P("Michaela Naneva",2002,"BUL"),P("Elodie Delorme",2010),P("Marie Barbieux",1991),P("Mackenzie Larson",2003,"USA"),P("Maëva Cutellas",1987),P("Lise Accordino",2003),P("Eva Manuel",2011),P("Yara Wakrim",2011),P("Sarah Sellaoui",2010),P("Ella Vuattoux",2012)],
    },
    "Grand Nancy Aquatique Club": {
        "aliases": ["nancy", "grand nancy"], "season": "2025-26 observed", "status": "OFFICIAL MATCH-SHEET OBSERVED — 2026-27 confirmation pending",
        "source": FFN_ELITE_START, "source_note": "Official FFN Elite evidence, 2025-26.",
        "players": [P("Sophia Lima de Freitas",2004,"BRA"),P("Emma Gurcan",2002,"CAN"),P("Hamiyet Süzmeçelik",2006,"TUR"),P("Lilia Hariss",2007),P("Tiziana Raspo",2005),P("Kahena Benlekbir",2002),P("Agustina Todoroff",1995,"CRO"),P("Karen de Miranda da Silva",2006,"BRA"),P("Lilou Stauder",2009),P("Lucie Fanara",2002),P("Jenny Ritz",1976),P("Sandra Pacheco Herce",2000,"ESP"),P("Lou Counil",1985),P("Clémence Grosdemange",2009)],
    },
    "Taverny Sports Nautiques 95": {
        "aliases": ["taverny"], "season": "2025-26 observed", "status": "OFFICIAL MATCH-SHEET OBSERVED — 2026-27 confirmation pending",
        "source": FFN_ELITE_START, "source_note": "Aggregated official FFN 2025-26 match evidence.",
        "players": [P("Zélie Calime",2011),P("Jade Boughrara",2005),P("Nancy Ajem",2006),P("Eléonore Rigault",2008),P("Oriane Lafin",1990),P("Aurore Mayet Toussaint",1999),P("Justine Moizant",2008),P("Olivia Soler",2012),P("Zia Wasterlain",2012),P("Sohane Bentaleb",2009),P("Feryel Bentaleb",2009),P("Anna Bonaventure",2009),P("Anastasiia Zelenko",None,"UKR"),P("Marine Lanoëlle")],
    },
    "Toulon Waterpolo": {
        "aliases": ["toulon", "toulon water-polo"], "season": "2025-26 observed", "status": "OFFICIAL MATCH-SHEET OBSERVED — 2026-27 confirmation pending",
        "source": FFN_ELITE_DAY2, "source_note": "Aggregated official FFN 2025-26 match evidence.",
        "players": [P("Chloé Vidal",2003),P("Charlotte Giana",2009),P("Emma Duflos",2007),P("Illyana Boughanmi",2010),P("Chloé Bony",1999),P("Aurore Faye",1997),P("Sarah Amcher",2000),P("Valentine Heurtaux",2005),P("Magdouline Boucif",2011),P("Lou-Ann Fourmont",2003),P("Léopoldine Burle",2009),P("Camille Blaize",1991),P("Cassandre Abt",2004),P("Cassandra Touret",2006),P("Anaelle Grass"),P("Maïwenn Le Gall")],
    },
    "Sporting Club des Nageurs de Choisy le Roi": {
        "aliases": ["choisy", "scn choisy"], "season": "2025-26 observed", "status": "OFFICIAL MATCH-SHEET OBSERVED — 2026-27 confirmation pending",
        "source": FFN_ELITE_DAY2, "source_note": "Players observed on official FFN 2025-26 match sheets; line-ups varied during the season.",
        "players": [P("Nathalie Merle",1985),P("Ranya Boutarbouche",2010),P("Estrella Guingan-Beltran",2009),P("Ranya El Ayeb",2008),P("Annaelle Picard",2002),P("Yasmine El Ayeb",2009),P("Mya Rambecki",2008),P("Stephanie Jean",1988),P("Sarah Aissou",1984),P("Elwyn Velon-Mayet",2005),P("Lina Oudia",2009),P("Clara Da Luz",2005),P("Hanane Zeghough",2009)],
    },
}

COACHES = {
    "Équipe de France Femmes - Senior": [
        {"name":"Lorène Derenty","role":"Entraîneur en chef","status":"OFFICIAL","confidence":100,"source":FFN_FRANCE_2026,"evaluation":"Head coach officially named by the FFN for the current national-team cycle."},
        {"name":"Stefania Giuliani","role":"Entraîneur adjoint","status":"OFFICIAL — Funchal 2026 staff","confidence":100,"source":FFN_FRANCE_2026,"evaluation":"Assistant coach listed in the official Funchal 2026 FFN staff."},
    ],
    "Granville Water Polo": [
        {"name":"Veronika Lapina","role":"Entraîneure groupe féminin","status":"CLUB OFFICIAL 2025-26 — 2026-27 role to confirm","confidence":78,"source":GRANVILLE_SOURCE,"evaluation":"Officially documented with the women’s N1 group in 2025-26. Exact Elite 2026-27 role remains pending public confirmation."},
    ],
    "Lille UC Métropole Water-Polo": [
        {"name":"Anestis Pesmatzoglou","role":"Coach","status":"FFN MATCH-SHEET CONFIRMED","confidence":90,"source":"https://waterpolo.ffnatation.fr/","evaluation":"Coach identity is supported by an official FFN match sheet; current 2026-27 appointment should be re-confirmed when the new season staff list is published."},
    ],
    "Union St-Bruno Bordeaux": [
        {"name":"Tristan Colaço","role":"Coach","status":"FFN CURRENT-SEASON EVIDENCE","confidence":92,"source":FFN_ELITE_2026,"evaluation":"Named by the FFN in 2026 Elite coverage as the Bordeaux coach."},
    ],
    "Olympic Nice Natation": [
        {"name":"Elie Carreau","role":"Coach","status":"FFN CURRENT-SEASON EVIDENCE","confidence":92,"source":FFN_ELITE_2026,"evaluation":"Named by the FFN in 2026 Elite coverage as the Nice coach."},
    ],
    "Grand Nancy Aquatique Club": [
        {"name":"Rémi Garsau","role":"Coach","status":"FFN CURRENT-SEASON EVIDENCE","confidence":94,"source":FFN_ELITE_START,"evaluation":"Named by the FFN in current Elite coverage as leading the Nancy women’s team."},
    ],
    "Toulon Waterpolo": [
        {"name":"Raphaël Pirat","role":"Coach","status":"FFN CURRENT-SEASON EVIDENCE","confidence":94,"source":FFN_ELITE_DAY2,"evaluation":"Named by the FFN in current Elite coverage as leading Toulon."},
    ],
}


def _norm(value: str | None) -> str:
    value = (value or "").lower().replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a").replace("ï", "i")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(value)).strip("-")


def _catalog_for_team(team_name: str):
    n = _norm(team_name)
    for canonical, data in ROSTER_OVERRIDES.items():
        if _norm(canonical) == n or any(_norm(a) in n or n in _norm(a) for a in data.get("aliases", [])):
            return canonical, data
    return None, None


def _coaches_for_team(team_name: str):
    canonical, _ = _catalog_for_team(team_name)
    if canonical and canonical in COACHES:
        return COACHES[canonical]
    n = _norm(team_name)
    for key, coaches in COACHES.items():
        if _norm(key) == n:
            return coaches
    return []


def _confidence_100(raw: Any) -> int | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 1:
        value *= 100
    return int(max(0, min(100, round(value))))


def _player_evaluation(db, name: str, role: str | None = None):
    Profile = getattr(models, "PlayerIntelligenceProfile", None)
    Metric = getattr(models, "PlayerMatchMetric", None)
    profile = None
    metrics = []
    if Profile is not None:
        try:
            profile = db.query(Profile).filter(Profile.canonical_name == name).first()
        except Exception:
            profile = None
    if profile is not None and Metric is not None:
        try:
            metrics = db.query(Metric).filter(Metric.profile_id == profile.id).all()
        except Exception:
            metrics = []

    confidence = _confidence_100(getattr(profile, "confidence_score", None)) if profile else None
    match_metrics = [m for m in metrics if getattr(m, "library_match_id", None) is not None]
    match_ids = {getattr(m, "library_match_id", None) for m in match_metrics if getattr(m, "library_match_id", None) is not None}

    direct = []
    for m in match_metrics:
        key = str(getattr(m, "metric", "")).strip().lower()
        if key in {"rating", "overall_rating", "aquametric_rating", "player_rating"}:
            try:
                direct.append(float(getattr(m, "value", 0)))
            except Exception:
                pass
    if direct:
        rating = sum(direct) / len(direct)
        if rating <= 10:
            rating *= 10
        rating = int(round(max(0, min(100, rating))))
        basis = f"{len(match_ids)} linked match(es), explicit rating metric"
    elif len(match_ids) >= 2 and len(match_metrics) >= 6:
        totals = defaultdict(float)
        for m in match_metrics:
            key = str(getattr(m, "metric", "")).strip().lower()
            try:
                totals[key] += float(getattr(m, "value", 0) or 0)
            except Exception:
                continue
        games = max(1, len(match_ids))
        score = 55.0
        positive_weights = {"goals":1.6,"assists":1.3,"steals":1.2,"blocks":0.8,"exclusions_drawn":0.8,"key_passes":0.8,"saves":0.35}
        negative_weights = {"turnovers":1.2,"exclusions":0.45,"bad_passes":0.7}
        for key, weight in positive_weights.items():
            score += weight * (totals.get(key, 0.0) / games)
        for key, weight in negative_weights.items():
            score -= weight * (totals.get(key, 0.0) / games)
        if role and "gard" in _norm(role):
            for key in ("save_percentage", "save_pct"):
                if key in totals:
                    pct = totals[key] / max(1, sum(1 for m in match_metrics if str(getattr(m, "metric", "")).lower() == key))
                    if pct <= 1:
                        pct *= 100
                    score += (pct - 40) * 0.35
        rating = int(round(max(35, min(95, score))))
        basis = f"{len(match_ids)} linked matches / {len(match_metrics)} match metrics"
    else:
        rating = None
        basis = "Insufficient linked match data for a defensible performance score"

    if rating is None:
        text = "Performance rating not calculated yet. The profile is available, but AquaMetric will not invent a score from roster presence alone."
    elif rating >= 82:
        text = "Very high provisional impact in the available match evidence. Re-check as the sample grows."
    elif rating >= 72:
        text = "Strong provisional performance profile in the available evidence, with positive overall impact."
    elif rating >= 62:
        text = "Positive-to-solid provisional performance in the available sample; more matches are needed for stability."
    elif rating >= 52:
        text = "Mixed/neutral provisional performance in the available sample; strengths and weaknesses remain context-dependent."
    else:
        text = "Below-average provisional output in the available sample; this is not a fixed judgement of player level."

    metric_preview = []
    for m in match_metrics[:24]:
        metric_preview.append({
            "metric": getattr(m, "metric", "metric"),
            "value": getattr(m, "value", None),
            "unit": getattr(m, "unit", None),
            "provenance": getattr(m, "provenance", None),
            "confidence": _confidence_100(getattr(m, "confidence_score", None)),
        })
    return {"rating": rating, "confidence": confidence, "basis": basis, "evaluation": text, "metrics": metric_preview, "profile_id": getattr(profile, "id", None) if profile else None}


# Remove the legacy scouting detail route so the refreshed version wins.
for _route in list(app.router.routes):
    if getattr(_route, "path", None) == "/scouting/{team_id}" and "GET" in (getattr(_route, "methods", set()) or set()):
        app.router.routes.remove(_route)


@app.get("/scouting/{team_id}", response_class=HTMLResponse)
def refreshed_scouting_detail(request: Request, team_id: int):
    db = SessionLocal()
    try:
        Team = getattr(models, "ScoutingTeam")
        Player = getattr(models, "ScoutingPlayer")
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Scouting team not found")
        canonical, catalog = _catalog_for_team(team.name)
        if catalog:
            players = [dict(p) for p in catalog["players"]]
            status = catalog["status"]
            season = catalog["season"]
            source = catalog["source"]
            source_note = catalog["source_note"]
        else:
            rows = db.query(Player).filter(Player.scouting_team_id == team.id).order_by(Player.name).all()
            players = [{"name":p.name,"birth_year":getattr(p,"birth_year",None),"nationality":getattr(p,"nationality",None),"role":getattr(p,"role",None)} for p in rows]
            status = getattr(team, "roster_status", None) or "not refreshed"
            season = getattr(team, "season_label", None) or "—"
            source = getattr(team, "source_url", None)
            source_note = getattr(team, "source_note", None) or "Existing AquaMetric evidence; no fresh override available yet."
        for p in players:
            p["slug"] = _slug(p["name"])
            p["evaluation"] = _player_evaluation(db, p["name"], p.get("role"))
        coaches = []
        for c in _coaches_for_team(team.name):
            cc = dict(c)
            cc["slug"] = _slug(cc["name"])
            coaches.append(cc)
        return core.templates.TemplateResponse(
            "scouting_detail.html",
            {"request":request,"team":team,"players":players,"coaches":coaches,"roster_status":status,"season_label":season,"source_url":source,"source_note":source_note},
        )
    finally:
        db.close()


@app.get("/scouting-person/{team_id}/player/{slug}", response_class=HTMLResponse)
def scouting_player_profile(request: Request, team_id: int, slug: str):
    db = SessionLocal()
    try:
        Team = getattr(models, "ScoutingTeam")
        Player = getattr(models, "ScoutingPlayer")
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        canonical, catalog = _catalog_for_team(team.name)
        if catalog:
            pool = [dict(p) for p in catalog["players"]]
            source = catalog["source"]
            status = catalog["status"]
            season = catalog["season"]
        else:
            rows = db.query(Player).filter(Player.scouting_team_id == team.id).all()
            pool = [{"name":p.name,"birth_year":getattr(p,"birth_year",None),"nationality":getattr(p,"nationality",None),"role":getattr(p,"role",None)} for p in rows]
            source = getattr(team,"source_url",None)
            status = getattr(team,"roster_status",None)
            season = getattr(team,"season_label",None)
        person = next((p for p in pool if _slug(p["name"]) == slug), None)
        if not person:
            raise HTTPException(status_code=404, detail="Player not found")
        evaluation = _player_evaluation(db, person["name"], person.get("role"))
        return core.templates.TemplateResponse("person_profile.html", {"request":request,"team":team,"kind":"PLAYER","person":person,"evaluation":evaluation,"source_url":source,"evidence_status":status,"season_label":season})
    finally:
        db.close()


@app.get("/scouting-person/{team_id}/coach/{slug}", response_class=HTMLResponse)
def scouting_coach_profile(request: Request, team_id: int, slug: str):
    db = SessionLocal()
    try:
        Team = getattr(models, "ScoutingTeam")
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        coach = next((dict(c) for c in _coaches_for_team(team.name) if _slug(c["name"]) == slug), None)
        if not coach:
            raise HTTPException(status_code=404, detail="Coach not found")
        person = {"name":coach["name"],"role":coach["role"],"birth_year":None,"nationality":None}
        evaluation = {
            "rating": None,
            "confidence": coach.get("confidence"),
            "basis": "Coach identity/role evidence only; team-performance rating intentionally withheld until a sufficiently linked result sample exists.",
            "evaluation": coach.get("evaluation"),
            "metrics": [],
            "profile_id": None,
        }
        return core.templates.TemplateResponse("person_profile.html", {"request":request,"team":team,"kind":"COACH","person":person,"evaluation":evaluation,"source_url":coach.get("source"),"evidence_status":coach.get("status"),"season_label":"Current evidence"})
    finally:
        db.close()


@app.get("/security-status")
def security_status():
    return {
        "status": "hardened-demo",
        "https_cookie": os.getenv("COOKIE_SECURE", "0") == "1",
        "rate_limits": True,
        "same_origin_guard": True,
        "security_headers": True,
        "trusted_hosts": True,
        "api_docs_public": False,
        "video_stream_validation": True,
        "storage": "ephemeral-demo",
    }
