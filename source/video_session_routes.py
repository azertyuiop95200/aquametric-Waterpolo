from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import Match, User
from services.deep_analysis_sequences import sequence_gallery, sequence_summary
from services.player_deep_metrics import player_deep_metrics, team_player_totals
from services.team_scoring_patterns import build_team_scoring_patterns
from services.video import youtube_embed

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

CHAPTERS = [
    {"title":"Duel & contact physique","focus":"Micro-technique","keywords":["duel","exclusion","penalty","foul","contact"],"observe":["Inside water et position des hanches","Premier puis deuxième contact","Orientation du corps avant le duel","Issue du duel et possession suivante"],"correction":"Créer l'avantage de hanches avant de chercher la force ; protéger la balle et l'axe ballon-but.","drill":"4 x 45 s duel orienté : réception, inside water, sortie propre puis repli immédiat."},
    {"title":"Jeu sans ballon & séparation","focus":"Timing","keywords":["drive","action_created","created","catch","separation"],"observe":["Slow-fast / stop-go","Départ synchronisé avec la passe","Espace créé pour une partenaire","Replacement après drive"],"correction":"Déclencher le changement de rythme avant la fenêtre de passe, pas après.","drill":"3v3 sans tir pendant 12 s : point uniquement si le drive crée une réception ou un décalage."},
    {"title":"Centre / centre-back","focus":"Duel intérieur","keywords":["centre","center","2m","exclusion_earned"],"observe":["Seal / re-seal","Front, 3/4 ou behind","Contrôle des hanches","Origine et timing de l'aide"],"correction":"Le centre doit créer une ligne de passe claire ; la défense protège d'abord l'axe et re-front selon la balle.","drill":"6 possessions centre/centre-back avec balle changeant de côté avant chaque entrée."},
    {"title":"Passe clé & manipulation","focus":"Ball movement","keywords":["assist","key_pass","pass","one-more","skip"],"observe":["Orientation avant réception","Fixation avant passe","One-more / skip","Passe qui crée réellement le tir"],"correction":"Fixer une défenseure avant de libérer la balle ; privilégier la passe qui améliore le tir suivant.","drill":"4v4 + 2 jokers : tir autorisé seulement après une fixation et une passe +1."},
    {"title":"Lecture avant réception","focus":"Game IQ","keywords":["decision","turnover","bad_pass","score","period"],"observe":["Scan centre-gardienne-aide","Chrono / score","Position de la défense faible","Décision prise avant T0"],"correction":"Imposer un double scan avant réception et supprimer les décisions prises après le contrôle de balle.","drill":"Jeu 5v5 : coach annonce une contrainte 1 s avant réception, décision en une touche logique."},
    {"title":"M-zone & défenses hybrides","focus":"Collectif","keywords":["block","interception","recovery","defence","defense"],"observe":["Qui sort sur la balle","Qui couvre O6","Distances entre X2-X3-X4","Retour dans le gap après la passe"],"correction":"La rotation doit être déclenchée par la trajectoire de balle, avec responsabilité explicite sur centre et aile faible.","drill":"6v6 zone dynamique : arrêt vidéo/coach après chaque deuxième passe pour vérifier personnel et responsabilités."},
    {"title":"Attaquer la zone","focus":"Contre-mesures","keywords":["power_play","key_pass","shot","attack","drive"],"observe":["Défenseure déplacée en premier","Fixation avant renversement","Entrée centre / post","Qualité du tir créé"],"correction":"Déplacer la zone avant de chercher le tir ; attaquer le close-out ou le gap créé par la rotation.","drill":"6v6 : deux renversements minimum, puis attaque du gap avec centre actif."},
    {"title":"Sprint & contre-attaque","focus":"Transition +","keywords":["counterattack","transition"],"observe":["Départ avant changement officiel","Largeur des couloirs","Première passe","Fixation du 2v1 / 3v2"],"correction":"Identifier immédiatement première nageuse, porteuse et couloir de sécurité ; fixer avant de transmettre.","drill":"Vagues 3v2 puis 4v3, obligation de fixer une défenseure avant la dernière passe."},
    {"title":"Repli défensif","focus":"Transition −","keywords":["defensive_recovery","fast_recovery","late_recovery","recovery"],"observe":["Première nage vers l'axe","Safety","Pression sur première passe","Reconstruction des match-ups"],"correction":"Protéger le danger central avant de retrouver sa joueuse initiale ; communiquer le switch en course.","drill":"3v2 retour : défense marque un point si elle transforme la situation en 3v3 avant le tir."},
    {"title":"6v5 / 5v6","focus":"Special teams","keywords":["power_play","penalty_kill","exclusion","penalty"],"observe":["6 attaquantes vs 5 défenseures + GK","Rotation après fake","Shot block proche / croisé","Retour de l'exclue"],"correction":"Respecter le personnel réel : 6 O contre 5 X + gardienne ; fermer une ligne sans en ouvrir deux.","drill":"6v5 départ figé puis 8 s libres ; défense annonce verbalement la rotation et le retour de l'exclue."},
    {"title":"Tir & gardienne","focus":"Finir","keywords":["goal","shot","save","block"],"observe":["Zone de tir","Préparation et release","Bloc défensif","Position gardienne / rebond"],"correction":"Créer le tir avant l'armé : jambes, angle et lecture du bloc doivent précéder la finition.","drill":"Série de 8 tirs par zone avec contrainte de lecture bloc/gardienne avant chaque armé."},
    {"title":"Intelligence de match","focus":"Décision","keywords":["period","score","turnover","late","decision","automatic"],"observe":["Score et période","Risque de la possession","Action précédente","Conséquence sur la possession suivante"],"correction":"Évaluer chaque décision par contexte de match, pas uniquement par résultat immédiat.","drill":"4 scénarios score/chrono : choisir rythme, faute/no-foul, sécurité et type de possession."},
]

TAGS = ["hip advantage","inside water","seal","re-seal","second contact","slow-fast","create the catch","eye manipulation","key pass","skip","one-more","front","3/4 centre","M-zone","piston","switch","shot block","sprint start","lane width","2v1 fix","3v2 fix","safety","recovery","goalkeeper outlet","lefty adjustment","clock management"]

BENCHMARKS = [
    {"id":"a5Ja269h5G8","title":"USA – Espagne","focus":"Décision, finition, transition"},
    {"id":"VvuJSTuuUI8","title":"Russie – Espagne","focus":"Centre, continuité, late game"},
    {"id":"fWFM4kB8nvw","title":"France – Israël","focus":"Entrée centre, sécurité, repli"},
    {"id":"bF-Am10VtF4","title":"Espagne – Grèce U20","focus":"Tempo, duel centre, 3v2"},
    {"id":"HfkCCOpLIBA","title":"Hongrie – Espagne","focus":"Sélection de tirs, zone/press"},
    {"id":"Ek1kBvUjivc","title":"Grèce – USA","focus":"Drive, passe +1, repli"},
    {"id":"TseN9CGbfQw","title":"Grèce – Hongrie","focus":"Lecture bloc, possession"},
    {"id":"Z-8PwbnKBWU","title":"Espagne – Pays-Bas","focus":"Circulation, défense drive, gardienne"},
]


def _require_user(request: Request, db: Session) -> User:
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def _sequence_text(card: dict) -> str:
    values = [card.get("title"), card.get("summary"), card.get("kind"), card.get("phase"), card.get("confidence_label")]
    return " ".join(str(v or "") for v in values).lower()


def _chapter_rows(sequences: list[dict]) -> list[dict]:
    rows = []
    for chapter in CHAPTERS:
        matched = []
        for card in sequences:
            text = _sequence_text(card)
            if any(keyword.lower() in text for keyword in chapter["keywords"]):
                matched.append(card)
            if len(matched) >= 6:
                break
        row = dict(chapter)
        row["sequences"] = matched
        rows.append(row)
    return rows


def _player_rows(match: Match) -> list[dict]:
    match_events = list(match.events or [])
    rows = []
    for player in list(match.team.players or []):
        events = [e for e in match_events if e.player_id == player.id]
        row = player_deep_metrics(player, events)
        if events or any((row.get("statboard") or {}).get(k) for k in ("ball_touches", "goals", "shots", "passes_completed", "turnovers", "saves")):
            rows.append(row)
    rows.sort(key=lambda r: (-int(r.get("event_count") or 0), -int((r.get("statboard") or {}).get("ball_touches") or 0), r.get("name") or ""))
    return rows


@router.get("/analysis/video-session-elite")
def video_session_elite(
    request: Request,
    match_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    user = _require_user(request, db)
    matches = db.scalars(
        select(Match).where(Match.owner_id == user.id).order_by(Match.created_at.desc(), Match.id.desc()).limit(30)
    ).all()

    selected = None
    if match_id is not None:
        selected = db.get(Match, match_id)
        if not selected or selected.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Match not found")
    if selected is None:
        selected = next((m for m in matches if m.video_path or m.video_url), matches[0] if matches else None)

    sequences = []
    summary = {"total": 0, "downloadable_clips": 0}
    players = []
    totals = {}
    attribution = {"assigned": 0, "total": 0, "pct": None}
    scoring = {}
    source_embed = ""
    screenshot_count = 0
    playable_count = 0

    if selected:
        sequences = sequence_gallery(db, selected, max_total=72)
        summary = sequence_summary(sequences)
        players = _player_rows(selected)
        totals = team_player_totals(players)
        events = list(selected.events or [])
        assigned = sum(1 for e in events if e.player_id is not None)
        attribution = {
            "assigned": assigned,
            "total": len(events),
            "pct": round(100.0 * assigned / len(events), 1) if events else None,
        }
        scoring = build_team_scoring_patterns(db, selected)
        source_embed = youtube_embed(selected.video_url) if selected.video_url else ""
        screenshot_count = sum(len(card.get("screenshot_urls", []) or []) for card in sequences)
        playable_count = sum(1 for card in sequences if card.get("clip_url") or card.get("local_segment_url") or card.get("segment_embed"))

    return templates.TemplateResponse(
        request,
        "video_session_elite.html",
        {
            "app_name": "AquaMetric",
            "request": request,
            "user": user,
            "web_demo_mode": False,
            "chapters": _chapter_rows(sequences),
            "tags": TAGS,
            "benchmarks": BENCHMARKS,
            "matches": matches,
            "selected": selected,
            "sequences": sequences,
            "sequence_summary": summary,
            "players": players,
            "player_totals": totals,
            "attribution": attribution,
            "scoring": scoring,
            "source_embed": source_embed,
            "local_video": bool(selected and selected.video_source == "upload" and selected.video_path),
            "screenshot_count": screenshot_count,
            "playable_count": playable_count,
        },
    )
