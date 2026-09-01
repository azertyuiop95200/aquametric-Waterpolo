import json
from pathlib import Path

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import get_db
from models import (
    User,
    Match,
    Event,
    MediaArtifact,
    AnalysisJob,
    VisionAnalysis,
    MatchLibraryItem,
    LibraryPlayerMatchStat,
)
from services.video import youtube_embed

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=BASE_DIR / "templates")
router = APIRouter()


def _user(request: Request, db: Session):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _safe_json(raw, fallback):
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, type(fallback)) else fallback
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _quarter_review(quarters):
    """Build a coach review from facts that can be computed from period scores.

    The function deliberately describes *where* the score changed, never *why*.
    Tactical causes remain a video/report question until evidence confirms them.
    """
    rows = []
    cumulative_a = 0
    cumulative_b = 0
    biggest = None
    previous_lead = 0
    lead_changes = 0
    for index, pair in enumerate(quarters, start=1):
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        try:
            a, b = int(pair[0]), int(pair[1])
        except (TypeError, ValueError):
            continue
        cumulative_a += a
        cumulative_b += b
        diff = a - b
        cumulative_diff = cumulative_a - cumulative_b
        lead = 1 if cumulative_diff > 0 else (-1 if cumulative_diff < 0 else 0)
        if previous_lead and lead and lead != previous_lead:
            lead_changes += 1
        if lead:
            previous_lead = lead
        if diff > 0:
            label = "avantage équipe A"
        elif diff < 0:
            label = "avantage équipe B"
        else:
            label = "quart équilibré"
        row = {
            "quarter": index,
            "a": a,
            "b": b,
            "diff": diff,
            "abs_diff": abs(diff),
            "cumulative_a": cumulative_a,
            "cumulative_b": cumulative_b,
            "cumulative_diff": cumulative_diff,
            "label": label,
        }
        rows.append(row)
        if biggest is None or row["abs_diff"] > biggest["abs_diff"]:
            biggest = row

    first_half_a = sum(r["a"] for r in rows[:2])
    first_half_b = sum(r["b"] for r in rows[:2])
    second_half_a = sum(r["a"] for r in rows[2:])
    second_half_b = sum(r["b"] for r in rows[2:])
    final_a = rows[-1]["cumulative_a"] if rows else 0
    final_b = rows[-1]["cumulative_b"] if rows else 0
    final_margin = abs(final_a - final_b)
    total_goals = final_a + final_b
    half_diff = first_half_a - first_half_b
    second_diff = second_half_a - second_half_b
    second_half_reversal = bool(half_diff and second_diff and ((half_diff > 0) != (second_diff > 0)))

    if biggest:
        turning = (
            f"Q{biggest['quarter']} est la période la plus déséquilibrée dans la preuve disponible "
            f"({biggest['a']}–{biggest['b']}). Cela identifie une bascule statistique à revoir ; "
            "la cause tactique ne doit être attribuée qu'avec une vidéo ou un rapport qui la documente."
        )
    else:
        turning = "Aucun détail par quart n'est disponible : la lecture reste limitée au score final et aux sources publiées."

    if not rows:
        coach_title = "Construire la preuve avant de construire l'explication"
        coach_questions = [
            "Quelle source manque pour découper le match par périodes ?",
            "Quelles affirmations peut-on faire avec le score final uniquement ?",
            "Quel replay ou rapport faut-il ajouter avant une conclusion tactique ?",
        ]
        coach_drill = "Rejouer une situation neutre du même contexte seulement après avoir identifié une preuve exploitable."
        pattern = "insufficient_period_data"
    elif second_half_reversal:
        coach_title = "Réaction après la mi-temps : identifier ce qui change réellement"
        coach_questions = [
            "Quelle différence de score apparaît entre la première et la deuxième moitié ?",
            "Sur le replay, quel changement de décision est visible avant de parler de système ?",
            "Le changement tient-il sur plusieurs possessions ou seulement sur une série courte ?",
        ]
        coach_drill = "Deux manches de 4 minutes avec pause coach : imposer une adaptation mesurable entre les deux."
        pattern = "second_half_reversal"
    elif final_margin <= 2:
        coach_title = "Match serré : qualité de décision sous pression"
        coach_questions = [
            "Quelles possessions des deux derniers quarts ont le plus de valeur score/temps ?",
            "Qui devient safety avant le tir dans une possession à un but d'écart ?",
            "Quelle option doit être refusée pour conserver une meilleure deuxième action ?",
        ]
        coach_drill = "Scénarios +1 / égalité / −1 avec 90 secondes restantes et score réellement compté."
        pattern = "close_finish"
    elif biggest and biggest["quarter"] == 4 and biggest["abs_diff"] >= 3:
        coach_title = "Dernier quart décisif : finir ou renverser le match"
        coach_questions = [
            "Comment le score à l'entrée du Q4 doit-il modifier le niveau de risque ?",
            "Quelles possessions offrent une contre-attaque évitable après perte ou tir ?",
            "Le replay montre-t-il une meilleure exécution, une fatigue adverse ou seulement une série de finition ?",
        ]
        coach_drill = "Dernier quart simulé avec le score réel à l'entrée du Q4 ; objectif décision avant résultat."
        pattern = "decisive_fourth"
    elif biggest and biggest["quarter"] == 3 and biggest["abs_diff"] >= 3:
        coach_title = "Troisième quart décisif : qualité de reprise après la pause"
        coach_questions = [
            "Quelle équipe impose la première série positive après la mi-temps ?",
            "Sur vidéo, les premières possessions montrent-elles un changement répétable ?",
            "Comment éviter qu'une série de deux erreurs devienne un quart entier perdu ?",
        ]
        coach_drill = "Reprise de mi-temps : quatre possessions préparées, score imposé, bilan après chaque paire."
        pattern = "decisive_third"
    elif biggest and biggest["quarter"] == 1 and biggest["abs_diff"] >= 3:
        coach_title = "Début de match : entrer immédiatement dans le niveau d'intensité"
        coach_questions = [
            "Quelle différence est déjà créée après huit minutes ?",
            "Le replay permet-il d'identifier des possessions répétées qui expliquent le départ ?",
            "Comment répondre au premier run sans sortir du plan de jeu ?",
        ]
        coach_drill = "Premier quart à haute contrainte : score de départ 0–0, bilan des quatre premières possessions."
        pattern = "decisive_start"
    elif lead_changes:
        coach_title = "Match à bascules : reconnaître quand l'avantage change de camp"
        coach_questions = [
            "À quel quart le cumul change-t-il de leader ?",
            "Quelles décisions précèdent le changement de dynamique sur le replay ?",
            "Comment stabiliser deux possessions après avoir repris l'avantage ?",
        ]
        coach_drill = "Mini-matchs de 3 minutes ; à chaque changement de leader, obligation d'une possession contrôlée."
        pattern = "lead_changes"
    elif final_margin >= 8:
        coach_title = "Écart important : maintenir les standards de décision"
        coach_questions = [
            "À quel moment l'écart devient-il structurel dans le score ?",
            "Quelles mauvaises habitudes apparaissent éventuellement quand le résultat semble acquis ?",
            "Comment continuer à travailler sécurité, repli et sélection de tirs ?",
        ]
        coach_drill = "Jouer à +6 avec critères de qualité : zéro perte centrale, safety identifié, tir après avantage créé."
        pattern = "large_margin"
    elif total_goals >= 28:
        coach_title = "Match à fort volume de buts : contrôler chaque transition"
        coach_questions = [
            "Le score élevé vient-il d'un rythme de possessions élevé ou d'une efficacité élevée ?",
            "Combien de buts suivent une perte ou une transition sur la vidéo ?",
            "Quelle équipe protège mieux la possession suivante après avoir marqué ?",
        ]
        coach_drill = "Transition continue : but ne compte double que si le replacement défensif est déjà organisé."
        pattern = "high_scoring"
    else:
        coach_title = "Identifier la période qui construit réellement l'écart"
        coach_questions = [
            "Quel quart produit la plus grande différence mesurable ?",
            "Quelle cause peut être vérifiée dans le replay ou le rapport, et laquelle reste une hypothèse ?",
            "Quelle décision peut être reproduite à l'entraînement sans inventer le contexte ?",
        ]
        coach_drill = "Rejouer le quart statistiquement le plus décisif avec score et temps imposés."
        pattern = "standard_swing"

    return {
        "quarters": rows,
        "biggest": biggest,
        "first_half": (first_half_a, first_half_b),
        "second_half": (second_half_a, second_half_b),
        "final": (final_a, final_b),
        "final_margin": final_margin,
        "total_goals": total_goals,
        "lead_changes": lead_changes,
        "second_half_reversal": second_half_reversal,
        "turning": turning,
        "pattern": pattern,
        "coach_title": coach_title,
        "coach_questions": coach_questions,
        "coach_drill": coach_drill,
    }


@router.get("/analysis-library", response_class=HTMLResponse)
def analysis_library_page_v2(
    request: Request,
    competition: str = Query(""),
    team: str = Query(""),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    stmt = select(MatchLibraryItem).order_by(MatchLibraryItem.created_at.desc(), MatchLibraryItem.id.desc())
    if competition.strip():
        stmt = stmt.where(MatchLibraryItem.competition == competition.strip())
    if team.strip():
        token = f"%{team.strip().lower()}%"
        stmt = stmt.where(
            (func.lower(MatchLibraryItem.team_a).like(token)) |
            (func.lower(MatchLibraryItem.team_b).like(token))
        )
    items = db.scalars(stmt).all()
    competitions = db.scalars(
        select(MatchLibraryItem.competition)
        .where(MatchLibraryItem.competition != "")
        .distinct()
        .order_by(MatchLibraryItem.competition)
    ).all()

    workspace_matches = db.scalars(
        select(Match)
        .where(Match.owner_id == user.id)
        .order_by(Match.created_at.desc(), Match.id.desc())
    ).all()
    workspace_rows = []
    for match in workspace_matches:
        events_count = db.scalar(select(func.count(Event.id)).where(Event.match_id == match.id)) or 0
        media_count = db.scalar(select(func.count(MediaArtifact.id)).where(MediaArtifact.match_id == match.id)) or 0
        latest_job = db.scalar(
            select(AnalysisJob)
            .where(AnalysisJob.match_id == match.id)
            .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
        )
        latest_vision = db.scalar(
            select(VisionAnalysis)
            .where(VisionAnalysis.match_id == match.id)
            .order_by(VisionAnalysis.created_at.desc(), VisionAnalysis.id.desc())
        )
        workspace_rows.append({
            "match": match,
            "events_count": events_count,
            "media_count": media_count,
            "latest_job": latest_job,
            "latest_vision": latest_vision,
            "has_owned_video": bool(match.video_path),
        })

    return TEMPLATES.TemplateResponse(
        request,
        "analysis_library.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "items": items,
            "competitions": competitions,
            "selected_competition": competition,
            "selected_team": team,
            "workspace_rows": workspace_rows,
        },
    )


@router.get("/analysis-library/{item_id}", response_class=HTMLResponse)
def analysis_library_detail_v2(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    item = db.get(MatchLibraryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library match not found")

    quarters = _safe_json(item.quarter_scores_json, [])
    raw_stats = _safe_json(item.team_stats_json, {})
    evidence_meta = raw_stats.get("_aquametric", {}) if isinstance(raw_stats, dict) else {}
    team_stats = {
        k: v for k, v in raw_stats.items()
        if k != "_aquametric" and isinstance(v, dict)
    } if isinstance(raw_stats, dict) else {}

    rows = db.scalars(
        select(LibraryPlayerMatchStat)
        .where(LibraryPlayerMatchStat.library_match_id == item.id)
        .order_by(LibraryPlayerMatchStat.team_name, LibraryPlayerMatchStat.goals.desc().nullslast(), LibraryPlayerMatchStat.player_name)
    ).all()
    teams = {}
    for row in rows:
        teams.setdefault(row.team_name or "Équipe non précisée", []).append(row)

    embed_url = youtube_embed(item.video_url) if item.video_url else ""
    review = _quarter_review(quarters)
    return TEMPLATES.TemplateResponse(
        request,
        "analysis_library_detail.html",
        {
            "request": request,
            "user": user,
            "app_name": "AquaMetric",
            "item": item,
            "quarters": quarters,
            "quarter_review": review,
            "team_stats": team_stats,
            "evidence_meta": evidence_meta,
            "teams": teams,
            "embed_url": embed_url,
        },
    )
