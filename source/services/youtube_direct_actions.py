"""Public YouTube -> Gemini Interactions, direct URL, per-clip validated actions.

Google's video understanding guide explicitly supports a public YouTube URI
as a video input, optionally with static start_offset/end_offset. No scraping,
YouTube cookie theft, cross-site fetch, downloaded copies or bypass of login.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import select

from models import VideoActionAnalysis
from services.video_action_provider import VideoActionError, provider_configuration, request_gemini_interaction
from services.video_action_runner import normalize_observations
from services.video_action_schema import VERSION, SegmentObservation, extraction_prompt

DURATION_LIMIT = 4 * 60 * 60
SEGMENT_SECONDS = 60
AUTO_BUDGET_SECONDS = 340
_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def canonical_public_youtube(url: str) -> str:
    """Only well-formed YouTube IDs on exact allow-listed hosts.

    Never pass a user-supplied generic URL to an outbound AI provider.
    """
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        raise ValueError("URL YouTube invalide.") from None
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        raise ValueError("Lien YouTube public HTTPS obligatoire.")
    identifier = ""
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            identifiers = parse_qs(parsed.query).get("v", [])
            identifier = identifiers[0] if len(identifiers) == 1 else ""
        elif parsed.path.startswith(("/shorts/", "/live/", "/embed/")):
            identifier = parsed.path.strip("/").split("/")[1] if len(parsed.path.strip("/").split("/")) == 2 else ""
    elif host == "youtu.be":
        identifier = parsed.path.strip("/")
    if not _YOUTUBE_ID.fullmatch(identifier):
        raise ValueError("Lien YouTube non reconnu ou identifiant de vidéo invalide.")
    return "https://www.youtube.com/watch?v=" + identifier


def action_plan(duration: float, start: float = 0.0, end: float | None = None) -> list[dict]:
    try:
        duration, start = float(duration), float(start)
        end = duration if end is None else float(end)
    except (TypeError, ValueError):
        raise ValueError("Durée ou intervalle invalide.") from None
    from math import isfinite
    if (not all(isfinite(v) for v in (duration,start,end))
            or not 0 < duration <= DURATION_LIMIT or not 0 <= start < end <= duration
            or end-start < 5):
        raise ValueError("Intervalle vidéo invalide ou supérieur à 4 heures.")
    plan=[]
    index=0
    pos=start
    while pos < end - 0.001:
        boundary=min(end,pos+SEGMENT_SECONDS)
        plan.append({
            "index":index, "start":round(pos,3), "end":round(boundary,3),
            "clip_start":round(pos,3),"clip_end":round(boundary,3),
            "status":"pending", "pane":0, "panes":1, "rate":1.0,
            "capture_start":round(pos,3), "capture_duration":round(boundary-pos,3),
        })
        index+=1
        pos=boundary
    return plan


def run_fingerprint(match, url: str, duration: float, start: float, end: float) -> str:
    identity=["direct-youtube-actions-v1",VERSION,match.id,match.owner_id,
        url,round(duration,3),round(start,3),round(end,3),
        provider_configuration()["model"],match.team.name,match.opponent]
    return hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode()).hexdigest()


def prepare_run(db, match, duration: float, *,start=0.0, end=None, video_url: str | None = None) -> tuple[VideoActionAnalysis, bool]:
    # A match may consist of several independent public YouTube quarter clips.
    # Keep a distinct fingerprint/clock for each source video.
    url=canonical_public_youtube(video_url or match.video_url)
    config=provider_configuration()
    if not config["configured"]:
        raise VideoActionError("not_configured",config["message"])
    actual_end=float(duration if end is None else end)
    plan=action_plan(duration,start,actual_end)
    fingerprint=run_fingerprint(match,url,duration,start,actual_end)
    run=db.scalar(select(VideoActionAnalysis).where(VideoActionAnalysis.fingerprint==fingerprint))
    now=time.time()
    if run:
        if run.status=="complete":
            return run, False
        if run.status in {"running","queued"} and now-float(run.updated_at or 0)<480:
            return run, False
        old=json.loads(run.segments_json or "[]")
        if len(old)!=len(plan):
            raise VideoActionError("plan_changed","Le plan de traitement existant ne correspond plus aux informations vidéo.")
        for i,entry in enumerate(old):
            if entry.get("status")=="complete":
                plan[i]=entry
            # Any stale 'running' is reattempted; completed clips are retained.
        run.segments_json=json.dumps(plan,ensure_ascii=False)
        run.status="queued"
        run.message="Reprise des séquences YouTube non traitées."
    else:
        run=VideoActionAnalysis(match_id=match.id,fingerprint=fingerprint,model=config["model"],
            source_kind="youtube_direct",source_path=url,status="queued",
            segments_json=json.dumps(plan,ensure_ascii=False),duration_seconds=actual_end-start,
            message="Analyse directe des images YouTube publiques en attente.")
        db.add(run)
    run.updated_at=now
    db.commit()
    db.refresh(run)
    return run, True


def _extract_observation(payload: dict) -> dict:
    if not isinstance(payload,dict) or payload.get("status")!="completed":
        raise VideoActionError("invalid_response","Le moteur n’a pas confirmé la fin de la séquence YouTube.")
    text=payload.get("output_text") or "".join(
        part.get("text","") for step in payload.get("steps",[])
        if step.get("type")=="model_output"
        for part in step.get("content",[]) if part.get("type")=="text"
    )
    try:
        return SegmentObservation.model_validate_json(text).model_dump()
    except (ValueError,TypeError,AttributeError):
        raise VideoActionError("invalid_response","La réponse du moteur vidéo ne contient pas d'actions validables.") from None


def analyze_public_youtube_segment(url: str, segment: dict, *,team: str, opponent: str,
                                   timeout: float=85) -> dict:
    config=provider_configuration()
    if not config["configured"]:
        raise VideoActionError("not_configured",config["message"])
    canonical=canonical_public_youtube(url)
    start,end=segment["clip_start"],segment["clip_end"]
    processing={"type":"static","start_offset":f"{start:g}s","end_offset":f"{end:g}s","fps":2.0}
    prompt=extraction_prompt(team,opponent)+(
        "\nLa vidéo distante n'est analysée que de "+f"{start:g}s à {end:g}s. "
        "Les timestamps de la réponse doivent être LOCAUX à cette sélection (0 à "
        +f"{end-start:g} secondes), pas les secondes absolues de YouTube. "
        "N'ajoute aucune action sans preuve visible ; si la vidéo est inaccessible "
        "ou privée, retourne scene='unreadable', actions=[]."
    )
    body={"model":config["model"],"store":False,
        "input":[{"type":"video","uri":canonical,"processing":processing},
                 {"type":"text","text":prompt}],
        "generation_config":{"max_output_tokens":16000},
        "response_format":{"type":"text","mime_type":"application/json",
            "schema":SegmentObservation.model_json_schema()}}
    try:
        response=request_gemini_interaction(body,timeout)
        if response.status_code in {401,403}:
            raise VideoActionError("credentials","Le fournisseur vidéo refuse la configuration du compte.")
        if response.status_code==429:
            raise VideoActionError("quota","Quota du moteur vidéo dépassé : les minutes déjà traitées sont conservées.")
        if response.status_code in {400,404,422}:
            raise VideoActionError("youtube_unavailable",
                "Le fournisseur ne peut pas accéder à cette vidéo YouTube publique ou à l'intervalle demandé.")
        if response.status_code!=200:
            raise VideoActionError("provider",f"Le fournisseur vidéo répond HTTP {response.status_code}.")
        return normalize_observations(_extract_observation(response.json()),segment)
    except VideoActionError:
        raise
    except httpx.TimeoutException:
        raise VideoActionError("timeout","La reconnaissance YouTube a dépassé le délai autorisé.") from None
    except (httpx.HTTPError,ValueError,TypeError):
        raise VideoActionError("connection","Erreur de communication avec le moteur vidéo direct.") from None


def _single_interval(url, segment, team, opponent, deadline):
    try:
        seconds=deadline-time.monotonic()
        if seconds<15:
            raise VideoActionError("budget","Temps de traitement atteint : les autres séquences restent à reprendre.")
        result=analyze_public_youtube_segment(url,segment,team=team,opponent=opponent,
                                             timeout=min(85,seconds-3))
        return {"status":"complete","result":result}
    except VideoActionError as exc:
        return {"status":"failed","error_code":exc.code,"error":str(exc)}
    except Exception:
        return {"status":"failed","error_code":"provider","error":"Séquence YouTube non analysable ; réessaie ou importe un MP4."}


def run_direct_youtube_actions(match_id: int, run_id: int):
    from db import SessionLocal
    from models import Match
    with SessionLocal() as db:
        run=db.get(VideoActionAnalysis,run_id)
        match=db.get(Match,match_id)
        if not run or not match or run.match_id!=match.id or run.source_kind!="youtube_direct":
            return
        plan=json.loads(run.segments_json or "[]")
        run.status="running"
        run.message="Vidéo YouTube publique transmise au modèle par intervalles ; comptage provisoire."
        run.updated_at=time.time()
        db.commit()
        deadline=time.monotonic()+AUTO_BUDGET_SECONDS
        stopped=False
        try:
            # Two independent segments at once; only this orchestrator writes
            # the SQLAlchemy session. Each provider call receives no DB handle.
            with ThreadPoolExecutor(max_workers=2,thread_name_prefix="youtube-direct") as pool:
                active={}
                todo=iter(s for s in plan if s["status"]!="complete")
                while True:
                    while not stopped and len(active)<2 and deadline-time.monotonic()>20:
                        seg=next(todo,None)
                        if seg is None:
                            break
                        seg["status"]="running"
                        active[pool.submit(_single_interval,run.source_path,dict(seg),
                            match.team.name,match.opponent,deadline)]=seg
                    if not active:
                        break
                    done,_=wait(active,timeout=6,return_when=FIRST_COMPLETED)
                    for future in done:
                        seg=active.pop(future)
                        seg.pop("result",None);seg.pop("error_code",None);seg.pop("error",None)
                        seg.update(future.result())
                        if seg.get("error_code") in {"credentials","quota","youtube_unavailable","budget"}:
                            stopped=True
                    run.segments_json=json.dumps(plan,ensure_ascii=False)
                    run.updated_at=time.time()
                    db.commit()
            completed=sum(s["status"]=="complete" for s in plan)
            run.status="complete" if completed==len(plan) and plan else "partial" if completed else "failed"
            run.message=f"{completed}/{len(plan)} intervalles YouTube traités. Détections provisoires à contrôler."
        except Exception:
            db.rollback()
            run.status="partial" if any(s.get("status")=="complete" for s in plan) else "failed"
            run.message="Analyse YouTube interrompue ; conserve les intervalles déjà traités et relance."
        run.updated_at=time.time()
        run.segments_json=json.dumps(plan,ensure_ascii=False)
        db.commit()
