"""Atomic revision of a private reference; caller checks match ownership."""
import json
from sqlalchemy import update
from models import MatchReviewReference, MatchReviewRevision

def replace_reference(db, prior, payload, canonical, digest, home_color, expected_digest):
    if prior.digest == digest and prior.home_color == home_color:
        return False
    if not expected_digest or expected_digest != prior.digest:
        raise ValueError("Choisir explicitement la version actuelle à remplacer.")
    if prior.home_color != home_color:
        raise ValueError("La couleur de notre équipe doit rester identique.")
    if json.loads(prior.payload_json)["timeline"] != payload["timeline"]:
        raise ValueError("La nouvelle référence ne correspond pas à la même chronologie vidéo.")
    old_digest, old_color, old_payload = prior.digest, prior.home_color, prior.payload_json
    result = db.execute(update(MatchReviewReference).where(
        MatchReviewReference.id==prior.id, MatchReviewReference.digest==old_digest
    ).values(digest=digest,payload_json=canonical).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise ValueError("Révision concurrente : recharger le rapport.")
    db.add(MatchReviewRevision(reference_id=prior.id,digest=old_digest,home_color=old_color,payload_json=old_payload))
    return True
