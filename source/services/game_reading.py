"""Game-reading score for AquaMetric prospect dossiers.

This is intentionally separate from the global /100 score so a prolific scorer
cannot automatically inherit an elite reading-of-the-game grade. The score is
built from already evidence-bound dimensions (decision, tactics, transition,
impact, etc.) and is confidence-shrunk when coverage is limited.
"""


def _weighted_mean(pairs):
    pairs = [(float(v), float(w)) for v, w in pairs if v is not None and w > 0]
    if not pairs:
        return None
    den = sum(w for _, w in pairs)
    return round(sum(v * w for v, w in pairs) / den, 1)


def _weights_for_role(role: str):
    r = (role or "").lower()
    if any(k in r for k in ("goalkeeper", "keeper", "gard")):
        return {
            "decision": .35,
            "tactics": .30,
            "defence": .20,
            "transition": .10,
            "impact": .05,
        }
    if "centre" in r or "center" in r:
        return {
            "decision": .34,
            "tactics": .31,
            "impact": .15,
            "attack": .10,
            "defence": .05,
            "discipline": .05,
        }
    return {
        "decision": .38,
        "tactics": .32,
        "transition": .15,
        "impact": .10,
        "discipline": .05,
    }


def _label(score):
    if score is None:
        return "NON ÉVALUÉE"
    if score >= 88:
        return "LECTURE ÉLITE"
    if score >= 82:
        return "TRÈS FORTE"
    if score >= 75:
        return "FORTE"
    if score >= 68:
        return "BONNE"
    if score >= 60:
        return "À CONFIRMER"
    return "PROVISOIRE"


def _confidence_label(confidence):
    if confidence >= .80:
        return "ÉLEVÉE"
    if confidence >= .62:
        return "SOLIDE"
    if confidence >= .44:
        return "MODÉRÉE"
    if confidence > 0:
        return "FAIBLE"
    return "INSUFFISANTE"


def add_game_reading_score(evaluation):
    """Attach a conservative reading-of-the-game grade to an evaluation dict."""
    dimensions = evaluation.get("dimensions") or {}
    sources = evaluation.get("dimension_sources") or {}
    weights = _weights_for_role(evaluation.get("role", ""))

    available = [
        (name, dimensions.get(name), weight)
        for name, weight in weights.items()
        if dimensions.get(name) is not None
    ]
    total_weight = sum(weights.values()) or 1.0
    covered_weight = sum(weight for _, _, weight in available)
    coverage = round(covered_weight / total_weight, 2)

    if len(available) < 2 or coverage < .45:
        evaluation["game_reading"] = {
            "score": None,
            "raw_score": None,
            "label": "NON ÉVALUÉE",
            "confidence_score": 0.0,
            "confidence_label": "INSUFFISANTE",
            "coverage": coverage,
            "components": {name: dimensions.get(name) for name in weights},
            "sources": sorted({s for name, _, _ in available for s in sources.get(name, [])}),
            "summary": "Données insuffisantes pour isoler la lecture de jeu sans extrapoler à partir des buts ou de la réputation.",
        }
        return evaluation

    raw = _weighted_mean([(value, weight) for _, value, weight in available])
    base_conf = float(evaluation.get("confidence_score") or 0.0)
    video_matches = int(evaluation.get("video_analyzed_matches") or 0)
    public_matches = int(evaluation.get("public_rated_matches") or 0)
    deep_review = evaluation.get("deep_review")

    # Evidence quality matters as much as the raw tactical/decision dimensions.
    confidence = (
        base_conf * .50
        + coverage * .28
        + min(.10, video_matches * .035)
        + min(.05, public_matches * .01)
        + (.05 if deep_review else 0.0)
    )
    confidence = round(min(.95, confidence), 2)

    # Keep weak samples close to neutral instead of publishing fake precision.
    shrink = .58 + .42 * confidence
    score = round(50 + ((raw or 50) - 50) * shrink, 1)

    unique_sources = sorted({s for name, _, _ in available for s in sources.get(name, [])})
    components = {name: dimensions.get(name) for name in weights}
    strongest = sorted(
        [(name, value) for name, value, _ in available],
        key=lambda item: item[1],
        reverse=True,
    )[:2]
    strength_text = ", ".join(f"{name.replace('_', ' ')} {value}/100" for name, value in strongest)
    summary = (
        f"Lecture de jeu calculée séparément de la production offensive. Meilleurs signaux actuels : {strength_text}. "
        "La note privilégie choix, compréhension tactique, anticipation et gestion des moments du match."
    )

    evaluation["game_reading"] = {
        "score": score,
        "raw_score": raw,
        "label": _label(score),
        "confidence_score": confidence,
        "confidence_label": _confidence_label(confidence),
        "coverage": coverage,
        "components": components,
        "sources": unique_sources,
        "summary": summary,
    }
    return evaluation
