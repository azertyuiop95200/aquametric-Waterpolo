"""PoloIQ open water-polo detection DATASET integration, not a fake model.

Source: https://universe.roboflow.com/ball-tracking-rrxno/poloiq
License CC BY 4.0 (credit the creator "ball tracking"). Dataset v1,
five detection classes, 4,865 source images. The public project currently
has NO hosted trained model; inference requires a separately trained and
deployed version owned/configured by the AquaMetric administrator.

Detection boxes are image coordinates. Do not promote them to goals,
shot positions, confirmed jersey identity, or full-match statistics.
"""
from __future__ import annotations

import base64
import math
import os
import re
from typing import Any

import cv2
import numpy as np
from fastapi import HTTPException


DATASET = {
    "name": "PoloIQ",
    "source": "Roboflow Universe / ball tracking",
    "url": "https://universe.roboflow.com/ball-tracking-rrxno/poloiq",
    "version_url": "https://universe.roboflow.com/ball-tracking-rrxno/poloiq/dataset/1",
    "version": 1,
    "license": "CC BY 4.0",
    "classes": ["ball", "goal", "goalie_red", "player_dark", "player_white"],
    "source_images": 4865,
    "public_trained_models": 0,
    "purpose": "object_detection_dataset",
    "does_not_detect": ["goal_scored", "shot_attempt", "exclusion", "assist", "confirmed_player_identity"],
}

# The configured model is an OUTPUT of training, not the public dataset URL.
MODEL_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,100}/[1-9][0-9]{0,3}$")
CLASSES = frozenset(DATASET["classes"])
MIN_CONFIDENCE = 0.35
MAX_FRAME_BYTES = 6 * 1024 * 1024


def configured() -> bool:
    model=os.getenv("AQUAMETRIC_POLOIQ_MODEL_ID", "").strip()
    key=os.getenv("ROBOFLOW_API_KEY", "").strip()
    return bool(key and MODEL_ID.fullmatch(model))


def readiness() -> dict[str,Any]:
    configured_now=configured()
    return {
        "configured":configured_now,
        "dataset":DATASET,
        "model_id":os.getenv("AQUAMETRIC_POLOIQ_MODEL_ID","") if configured_now else None,
        "mode":"object_detection_only" if configured_now else "training_dataset_only",
        "reason":"" if configured_now else (
            "Le projet PoloIQ public contient des images annotées, mais aucun modèle entraîné publié. "
            "Entraîner et déployer un détecteur, puis configurer AQUAMETRIC_POLOIQ_MODEL_ID et ROBOFLOW_API_KEY."
        ),
        "video_events_confirmed_automatically":False,
    }


def normalized_detections(payload:dict, *, min_confidence:float=MIN_CONFIDENCE) -> list[dict]:
    """Parse standard Roboflow boxes, explicitly preserving prediction status."""
    if not isinstance(payload,dict):
        raise ValueError("Payload Roboflow invalide.")
    dims=payload.get("image") or {}
    width=float(dims.get("width") or 0)
    height=float(dims.get("height") or 0)
    if not 0<width<=20000 or not 0<height<=20000:
        raise ValueError("Dimensions d'image invalides.")
    raw=payload.get("predictions") or []
    if not isinstance(raw,list) or len(raw)>500:
        raise ValueError("Nombre de détections excessif.")
    result=[]
    for pred in raw:
        if not isinstance(pred,dict) or pred.get("class") not in CLASSES:
            continue
        try:
            conf=float(pred["confidence"])
            x,y,bw,bh=[float(pred[k]) for k in ("x","y","width","height")]
        except (KeyError,TypeError,ValueError):
            continue
        if not all(map(math.isfinite,(conf,x,y,bw,bh))) or conf<min_confidence or conf>1:
            continue
        if bw<=0 or bh<=0 or x<0 or y<0 or x>width or y>height:
            continue
        # Public Roboflow boxes are centers with full dimensions, not 0-1 points.
        x1=max(0,(x-bw/2)/width);y1=max(0,(y-bh/2)/height)
        x2=min(1,(x+bw/2)/width);y2=min(1,(y+bh/2)/height)
        if x1>=x2 or y1>=y2:
            continue
        result.append({
            "class":pred["class"], "confidence":round(conf,4),
            "bbox_normalized":[round(x1,5),round(y1,5),round(x2,5),round(y2,5)],
            "status":"candidate_object_detection_not_a_sporting_event",
        })
    return result


def infer_one_frame(image_bytes:bytes) -> dict:
    """Bounded, opt-in single-image test. Never execute on a 5 GB raw upload."""
    if not configured():
        raise HTTPException(503,"Détecteur PoloIQ non entraîné/configuré sur ce serveur.")
    if not image_bytes or len(image_bytes)>MAX_FRAME_BYTES:
        raise HTTPException(413,"Image vide ou supérieure à 6 Mo.")
    arr=np.frombuffer(image_bytes,dtype=np.uint8)
    img=cv2.imdecode(arr,cv2.IMREAD_COLOR)
    if img is None or img.size==0:
        raise HTTPException(400,"Fournir une vraie image JPEG/PNG décodable.")
    height,width=img.shape[:2]
    if width<128 or height<128 or width>6000 or height>6000:
        raise HTTPException(400,"Taille d'image hors limites.")
    # Reduce bandwidth and avoid sending arbitrary original file metadata.
    if max(width,height)>1280:
        factor=1280/max(width,height)
        img=cv2.resize(img,(int(width*factor),int(height*factor)),interpolation=cv2.INTER_AREA)
    good,compressed=cv2.imencode(".jpg",img,[int(cv2.IMWRITE_JPEG_QUALITY),82])
    if not good:
        raise HTTPException(400,"Image impossible à encoder.")
    model=os.environ["AQUAMETRIC_POLOIQ_MODEL_ID"].strip()
    key=os.environ["ROBOFLOW_API_KEY"].strip()
    import httpx
    endpoint="https://detect.roboflow.com/"+model
    try:
        response=httpx.post(endpoint,
            params={"api_key":key,"confidence":int(MIN_CONFIDENCE*100)},
            data=base64.b64encode(compressed.tobytes()),
            headers={"Content-Type":"application/x-www-form-urlencoded"},
            timeout=25.0)
        response.raise_for_status()
        raw=response.json()
        detections=normalized_detections(raw)
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        # Do not expose signed secrets or provider failure URL in error body.
        raise HTTPException(502,"Service de détection distant indisponible ou réponse invalide.") from None
    return {
        "status":"unverified_object_candidates",
        "detections":detections,
        "count":len(detections),
        "model_id":model,
        "message":"Détections de ballon, cage et silhouettes à confirmer. Aucun tir, but, exclusion, joueuse ou point sur la carte n'a été confirmé automatiquement.",
        "source_dataset":DATASET["url"],
    }
