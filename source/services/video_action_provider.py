"""Small stateless Gemini video adapter. No credentials reach reports or logs."""
from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
from services.video_action_schema import SegmentObservation, extraction_prompt


class VideoActionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def provider_configuration() -> dict:
    enabled = os.getenv("AQUAMETRIC_VIDEO_ACTIONS", "").lower() in {"1", "true", "on"}
    key_present = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {"enabled": enabled, "configured": enabled and key_present,
            "availability_code": "ready" if enabled and key_present else ("missing_key" if not key_present else "disabled"),
            "model": os.getenv("AQUAMETRIC_VIDEO_MODEL", "gemini-3.8-flash"),
            "message": ("Reconnaissance des actions activée." if enabled and key_present else
                        "La reconnaissance des actions n’est pas activée sur ce serveur. "
                        "L’administrateur doit connecter le moteur vidéo ; le score OCR seul ne mesure pas les actions.")}


def analyze_video_segment(path: Path, *, team: str, opponent: str, timeout: float = 75) -> dict:
    config = provider_configuration()
    if not config["configured"]:
        raise VideoActionError("not_configured", config["message"])
    if not 0 < path.stat().st_size <= 14 * 1024 * 1024:
        raise VideoActionError("media_size", "Séquence absente ou trop volumineuse pour le moteur vidéo.")
    body = {"model": config["model"], "store": False,
            "input": [{"type": "video", "mime_type": "video/mp4",
                       "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                       "processing": {"type": "static", "fps": 4}},
                      {"type": "text", "text": extraction_prompt(team, opponent)}],
            "generation_config": {"max_output_tokens": 18000},
            "response_format": {"type": "text", "mime_type": "application/json",
                                "schema": SegmentObservation.model_json_schema()}}
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=min(10, timeout)), follow_redirects=False) as client:
            response = client.post("https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, json=body)
        if response.status_code in {401, 403}:
            raise VideoActionError("credentials", "Le moteur vidéo refuse la clé ou les droits du serveur.")
        if response.status_code == 429:
            raise VideoActionError("quota", "Le quota du moteur vidéo est atteint. Les séquences terminées sont conservées.")
        if response.status_code != 200:
            raise VideoActionError("provider", f"Le moteur vidéo répond HTTP {response.status_code}. Les résultats déjà reçus sont conservés.")
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("status") != "completed":
            raise ValueError("incomplete interaction")
        output = "".join(part.get("text", "") for step in payload.get("steps", [])
                         if step.get("type") == "model_output" for part in step.get("content", [])
                         if part.get("type") == "text")
        # Validate locally as well. A malformed/truncated response must not
        # become a successful, empty segment or plausible invented totals.
        parsed = SegmentObservation.model_validate_json(output)
        return parsed.model_dump()
    except VideoActionError:
        raise
    except httpx.TimeoutException:
        raise VideoActionError("timeout", "Le moteur vidéo n’a pas répondu à temps pour cette séquence.") from None
    except (ValueError, KeyError, TypeError, AttributeError):
        raise VideoActionError("invalid_response", "Réponse vidéo incomplète ou non conforme ; séquence à reprendre.") from None
    except httpx.HTTPError:
        raise VideoActionError("connection", "Connexion au moteur vidéo interrompue ; séquence à reprendre.") from None
