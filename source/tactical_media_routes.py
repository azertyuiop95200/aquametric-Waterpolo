from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db import get_db
from models import Match, MediaArtifact, User
from services.media import MediaGenerationError, create_clip, create_screenshot
from services.tactical_engine import analyze_match_tactics
from services.video import timestamped_video_url

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", BASE_DIR / "evidence"))
router = APIRouter()

PHASE_PRIORITY = {
    "power_play": 0,
    "penalty_kill": 1,
    "counterattack": 2,
    "defensive_recovery": 3,
    "even_attack": 4,
    "even_defence": 5,
}

PHASE_GUIDE = {
    "power_play": {
        "objective": "Créer un décalage gardienne/bloc avant le tir et obtenir une finition propre en Zone+.",
        "watch": "Entrée en supériorité, largeur, fixation, vitesse de circulation, passe supplémentaire, qualité du dernier tir.",
        "risk": "Tir précipité, ballon arrêté, défense non déplacée ou perte qui déclenche une contre-attaque.",
        "question": "Qu'est-ce qui a réellement déplacé la défense avant le tir ?",
    },
    "penalty_kill": {
        "objective": "Protéger l'axe et la cage en 5 contre 6 tout en conservant une ligne de vue utile à la gardienne.",
        "watch": "Compacité, rotations, bras de bloc, communication, fermeture du centre et replacement après chaque passe.",
        "risk": "Rotation tardive, double sortie sur la même joueuse, diagonale ouverte ou écran qui masque la gardienne.",
        "question": "Quel déplacement défensif ouvre ou ferme la meilleure ligne de tir adverse ?",
    },
    "counterattack": {
        "objective": "Transformer la récupération en avantage numérique ou positionnel avant le repli adverse.",
        "watch": "Première réaction, nage des couloirs, passe de sortie, lecture du surnombre et choix tir/passe.",
        "risk": "Passe forcée, mauvais espacement, finition trop tôt ou transition abandonnée avant création d'un avantage.",
        "question": "Le gain vient-il de la première réaction, de la passe de sortie ou du choix final ?",
    },
    "defensive_recovery": {
        "objective": "Stopper la transition adverse, protéger l'axe puis reconstruire les match-ups.",
        "watch": "Sprint de repli, protection du centre, communication, prise de la joueuse la plus dangereuse et retour à six.",
        "risk": "Ball-watching, retard dans l'axe, croisement non communiqué ou poursuite d'une mauvaise joueuse.",
        "question": "Qui protège d'abord l'axe et à quel moment les responsabilités sont-elles redistribuées ?",
    },
    "even_attack": {
        "objective": "Créer un avantage en attaque placée par circulation, jeu au centre, drive ou écran.",
        "watch": "Espacement, occupation du centre, timing des drives, côté fort/faible, qualité de la passe d'entrée et sélection du tir.",
        "risk": "Attaque statique, centre isolé, drive sans espace ou tir sans déséquilibre préalable.",
        "question": "Quel mouvement crée l'avantage avant la dernière passe ou le tir ?",
    },
    "even_defence": {
        "objective": "Contrôler le centre et les lignes de pénétration sans offrir un tir extérieur trop propre.",
        "watch": "Pression ballon, position devant/derrière le centre, aide, drop éventuel, communication et bloc gardienne-défense.",
        "risk": "Aide trop profonde, centre libéré, retard au drive ou mauvais partage entre pression et protection de zone.",
        "question": "La défense gagne-t-elle la possession par pression, aide ou contrôle du centre ?",
    },
}


def _user(request: Request, db: Session) -> User:
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


def sequence_review(seq: dict) -> dict:
    phase = seq.get("phase") or "even_attack"
    guide = PHASE_GUIDE.get(phase, PHASE_GUIDE["even_attack"])
    time_to_shot = seq.get("time_to_first_shot")
    if time_to_shot is None:
        tempo = "Aucun tir tagué dans cette séquence"
    elif time_to_shot <= 5:
        tempo = f"Tir très rapide après {time_to_shot:.1f}s"
    elif time_to_shot <= 12:
        tempo = f"Construction intermédiaire : premier tir après {time_to_shot:.1f}s"
    else:
        tempo = f"Circulation longue : premier tir après {time_to_shot:.1f}s"

    outcome_bits = [f"{seq.get('passes', 0)} passes taguées", f"{seq.get('shots_for', 0)} tirs"]
    if seq.get("goals_for"):
        outcome_bits.append(f"{seq['goals_for']} but")
    if seq.get("losses_for"):
        outcome_bits.append(f"{seq['losses_for']} perte")
    if seq.get("goals_against"):
        outcome_bits.append(f"{seq['goals_against']} but encaissé")

    alerts = []
    if seq.get("losses_for"):
        alerts.append("La possession se termine par une perte : vérifier la décision et la sécurité de passe.")
    if seq.get("shots_for", 0) == 0 and phase in {"power_play", "counterattack", "even_attack"}:
        alerts.append("Aucun tir tagué : vérifier si l'avantage a réellement été transformé en occasion.")
    if seq.get("goals_against"):
        alerts.append("But adverse dans la séquence : isoler la première rupture défensive, pas seulement la finition.")
    if phase == "defensive_recovery" and seq.get("late_recovery", 0) > seq.get("fast_recovery", 0):
        alerts.append("Le repli tardif domine dans les tags disponibles.")

    return {
        "objective": guide["objective"],
        "watch": guide["watch"],
        "risk": guide["risk"],
        "question": guide["question"],
        "tempo": tempo,
        "outcome": " · ".join(outcome_bits),
        "alerts": alerts,
    }


def enrich_sequence_cards(match: Match, report: dict, artifacts: list[MediaArtifact]) -> list[dict]:
    cards = []
    for seq in report.get("sequences", []):
        start = float(seq.get("start", 0))
        near = [a for a in artifacts if abs(float(a.second or 0) - start) <= 8]
        near.sort(key=lambda a: (0 if a.source == "tactical_study_pack" else 1, abs(float(a.second or 0) - start), a.id or 0))
        clip = next((a for a in near if a.artifact_type == "clip"), None)
        screenshot = next((a for a in near if a.artifact_type == "screenshot"), None)
        bookmark = next((a for a in near if a.external_url), None)
        clip_url = f"/matches/{match.id}/evidence/{clip.id}" if clip and clip.file_path else ""
        screenshot_url = f"/matches/{match.id}/evidence/{screenshot.id}" if screenshot and screenshot.file_path else ""
        open_url = ""
        if clip_url:
            open_url = clip_url
        elif bookmark:
            open_url = bookmark.external_url
        elif match.video_url:
            open_url = timestamped_video_url(match.video_url, start)
        cards.append({
            **seq,
            "review": sequence_review(seq),
            "clip": clip,
            "screenshot": screenshot,
            "clip_url": clip_url,
            "screenshot_url": screenshot_url,
            "open_url": open_url,
        })
    return cards


def _already_exists(match: Match, artifact_type: str, second: float) -> bool:
    return any(
        a.source == "tactical_study_pack"
        and a.artifact_type == artifact_type
        and abs(float(a.second or 0) - second) <= 0.75
        for a in match.media_artifacts
    )


@router.post("/matches/{match_id}/intelligence/study-pack")
def build_tactical_study_pack(match_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(404)

    report = analyze_match_tactics(match)
    sequences = sorted(
        report.get("sequences", []),
        key=lambda s: (PHASE_PRIORITY.get(s.get("phase"), 9), float(s.get("start", 0))),
    )[:12]
    if not sequences:
        return RedirectResponse(f"/matches/{match_id}/intelligence#video-review", status_code=303)

    created = 0
    if match.video_source == "upload" and match.video_path:
        source_path = UPLOAD_DIR / Path(match.video_path).name
        if not source_path.exists():
            raise HTTPException(404, detail="Uploaded source video is missing.")
        for seq in sequences:
            start = float(seq.get("start", 0))
            duration = max(1.0, float(seq.get("duration", 0) or 0))
            first_shot = seq.get("time_to_first_shot")
            focus_offset = float(first_shot) if first_shot is not None else min(3.0, duration * 0.45)
            focus_second = start + max(1.0, min(5.0, focus_offset))
            label = (seq.get("phase") or "tactical").replace("_", " ").title()
            review = sequence_review(seq)
            note = f"{review['tempo']}. {review['outcome']}. À observer: {review['watch']}"

            if not _already_exists(match, "clip", start):
                try:
                    generated = create_clip(source_path, EVIDENCE_DIR, focus_second, before=2.0, after=4.5)
                    db.add(MediaArtifact(
                        match_id=match.id,
                        artifact_type="clip",
                        analysis_type="tactic",
                        title=f"{label} · micro-extrait",
                        note=note[:1000],
                        second=start,
                        start_second=generated.start_second,
                        end_second=generated.end_second,
                        file_path=generated.filename,
                        mime_type=generated.mime_type,
                        is_downloadable=True,
                        source="tactical_study_pack",
                    ))
                    created += 1
                except MediaGenerationError:
                    pass

            if not _already_exists(match, "screenshot", start):
                try:
                    generated = create_screenshot(source_path, EVIDENCE_DIR, focus_second)
                    db.add(MediaArtifact(
                        match_id=match.id,
                        artifact_type="screenshot",
                        analysis_type="tactic",
                        title=f"{label} · image clé",
                        note=note[:1000],
                        second=start,
                        start_second=generated.start_second,
                        end_second=generated.end_second,
                        file_path=generated.filename,
                        mime_type=generated.mime_type,
                        is_downloadable=True,
                        source="tactical_study_pack",
                    ))
                    created += 1
                except MediaGenerationError:
                    pass
    elif match.video_url:
        for seq in sequences:
            start = float(seq.get("start", 0))
            if _already_exists(match, "bookmark", start):
                continue
            label = (seq.get("phase") or "tactical").replace("_", " ").title()
            review = sequence_review(seq)
            db.add(MediaArtifact(
                match_id=match.id,
                artifact_type="bookmark",
                analysis_type="tactic",
                title=f"{label} · repère vidéo",
                note=f"{review['tempo']}. {review['outcome']}."[:1000],
                second=start,
                start_second=start,
                end_second=start,
                external_url=timestamped_video_url(match.video_url, start),
                is_downloadable=False,
                source="tactical_study_pack",
            ))
            created += 1
    else:
        raise HTTPException(400, detail="This match has no video source.")

    db.commit()
    return RedirectResponse(f"/matches/{match_id}/intelligence#video-review", status_code=303)
