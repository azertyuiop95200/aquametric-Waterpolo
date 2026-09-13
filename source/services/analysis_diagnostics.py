"""User-visible outcomes derived from saved evidence, including legacy reports."""
from services.autonomous_engine import _valid_score_rows, _status_kind


def analysis_diagnostics(automatic: dict, verified_events: list) -> dict:
    observations = automatic.get("observations") or []
    candidates = automatic.get("candidates") or []
    summary = automatic.get("summary") or {}
    # Do not equate a DB row, playback completion or a visual peak with a
    # measured sporting event. Historical 'complete' reports need this too.
    scores = _valid_score_rows(observations)
    scores = [r for r in scores if _status_kind(r) not in {"replay", "break"}
              and float(r.get("ocr_confidence") or 0) >= .65]
    latest = None
    for index, row in enumerate(scores):
        pair = (row["home_score"], row["away_score"])
        if any((old["home_score"], old["away_score"]) == pair
               and float(old["second"]) < float(row["second"])
               for old in scores[:index]):
            latest = {"left": pair[0], "right": pair[1], "second": row["second"]}
    reason = summary.get("ocr_reason") or ("scoreboard_unreadable" if not observations else "")
    messages = {
        "ocr_unavailable": "Le moteur de lecture du score est indisponible sur le serveur.",
        "no_scoreboard_regions": "Aucune zone de tableau de score n’a été localisée.",
        "no_frames": "Aucune image de capture exploitable n’est disponible.",
        "scoreboard_unreadable": "Aucune lecture exploitable du score n’a été enregistrée.",
    }
    return {
        "outcome": "partial" if observations or verified_events else "no_measurements",
        "message": messages.get(reason, "Résultats partiels : la couverture exhaustive du match n’est pas établie."),
        "ocr_reason": reason,
        "observations": len(observations),
        "verified_events": len(verified_events),
        "goal_candidates": sum(str(c.get("event_type", "")).startswith("goal_candidate_") for c in candidates),
        "unclassified_candidates": sum(c.get("event_type") == "unclassified_action_candidate" for c in candidates),
        "latest_repeated_score": latest,
    }
