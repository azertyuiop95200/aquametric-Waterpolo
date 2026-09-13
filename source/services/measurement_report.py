"""Complete measured statistics shared by match reports, exports and players.

Totals describe the confirmed sample, never unobserved actions in the match.
Unknown event types and structured measurements remain visible in the ledger.
"""
from collections import Counter, defaultdict
from services.event_evidence import verified_events
from services.ultimate_analytics import ultimate_event_report, note_tags, NUMERIC_TAGS
from services.ratings import build_detailed_evaluation


LABELS = {
    "basic": "Statistiques", "coverage": "Couverture des annotations",
    "losses": "Pertes de balle", "shots": "Tirs (buts inclus)", "passes": "Passes",
    "decisions": "Décisions", "pressure": "Pression", "periods": "Périodes",
    "phases": "Phases de jeu", "possessions": "Possessions identifiées",
    "qualitative": "Constats étayés", "event_counts": "Toutes les actions enregistrées",
    "physical_measurements": "Mesures physiques renseignées", "tag_breakdowns": "Contexte et mesures détaillés",
    "events": "Actions confirmées", "goals": "Buts", "assists": "Passes décisives",
    "shots_on_target": "Tirs cadrés (buts inclus)", "shots_off_target": "Tirs non cadrés",
    "shots_blocked": "Tirs bloqués", "scoring_efficiency_pct": "Efficacité au tir (%)",
    "shot_accuracy_pct": "Tirs cadrés (%)", "passes_completed": "Passes réussies",
    "passes_failed": "Passes manquées", "pass_attempts": "Passes tentées",
    "pass_completion_pct": "Réussite des passes (%)", "turnovers": "Pertes",
    "ball_wins": "Actions défensives positives", "exclusions_earned": "Exclusions provoquées",
    "exclusions_committed": "Exclusions commises", "key_passes": "Passes clés",
    "actions_created": "Actions créées", "duels_won": "Duels gagnés", "duels_lost": "Duels perdus",
    "saves": "Arrêts", "touches": "Ballons touchés", "centre_touches": "Ballons touchés au centre",
    "interceptions": "Interceptions", "recoveries": "Récupérations", "blocks": "Contres",
    "fouls": "Fautes", "penalties_earned": "Penalties provoqués", "penalties_committed": "Penalties commis",
    "fast_recoveries": "Replis rapides", "late_recoveries": "Replis tardifs",
    "distance_m": "Distance renseignée (m)", "shot_speed_kmh": "Vitesse de tir renseignée (km/h)",
    "release_time_s": "Temps de déclenchement (s)", "sprint_5m_s": "Sprint 5 m (s)",
    "sprint_10m_s": "Sprint 10 m (s)", "max_swim_speed_mps": "Vitesse de nage (m/s)",
    "total": "Total", "count": "Nombre", "mean": "Moyenne", "max": "Maximum",
    "min": "Minimum", "zones": "Zones", "types": "Types", "hands": "Mains",
    "rows": "Détail", "reasons": "Causes", "pressures": "Pressions", "outcomes": "Issues",
    "period": "Période", "label": "Libellé", "key": "Catégorie", "share": "Part (%)",
    "efficiency_pct": "Efficacité (%)", "accuracy_pct": "Cadrage (%)",
    "attempts": "Tentatives", "completed": "Réussies", "failed": "Manquées",
    "completion_pct": "Réussite (%)", "coverage_pct": "Couverture (%)",
    "evaluation": "Évaluation sur les actions confirmées", "overall": "Note globale",
    "dimensions": "Dimensions de la note", "confidence_score": "Confiance du modèle",
    "sample_size": "Taille de l’échantillon", "strengths": "Points forts observés",
    "improvements": "Axes de progression", "physical": "Évaluation physique",
}


def observed_report(events, perspective=None):
    selected = verified_events(events)
    if perspective is not None:
        selected = [e for e in selected if getattr(getattr(e, "context_meta", None), "perspective", "for") == perspective]
    report = ultimate_event_report(selected, "all")
    if not selected:
        report["basic"] = {key: (0 if key == "events" else None) for key in report["basic"]}
    report["event_counts"] = dict(Counter(e.event_type for e in selected))
    tags = defaultdict(Counter)
    numeric = defaultdict(list)
    for event in selected:
        for key, value in note_tags(event).items():
            if key in NUMERIC_TAGS:
                numeric[key].append(value)
            else:
                tags[key][str(value)] += 1
    report["physical_measurements"] = {key: {
        "count": len(values), "mean": round(sum(values)/len(values), 3),
        "min": min(values), "max": max(values),
    } for key, values in numeric.items()}
    report["tag_breakdowns"] = {key: dict(counts) for key, counts in tags.items()}
    return report


def player_statistics(events):
    """Called only with the owner's scoped query; IDs, never names, identify people."""
    selected = verified_events(events)
    by_match = defaultdict(list)
    for event in selected:
        by_match[getattr(event, "match_id", None)].append(event)
    role = getattr(getattr(selected[0], "player", None), "primary_role", "") if selected else ""
    def report(rows):
        return {**observed_report(rows), "evaluation": build_detailed_evaluation(rows, role=role)}
    return {"aggregate": report(selected), "match_count": len(by_match),
            "matches": [{"match_id": mid, "report": report(rows)} for mid, rows in by_match.items()]}


def match_statistics(match):
    all_events = list(match.events or [])
    selected = verified_events(all_events)
    groups = defaultdict(list)
    for event in selected:
        side = getattr(getattr(event, "context_meta", None), "perspective", "for")
        groups[(side, event.player_id)].append(event)
    players = []
    for (side, pid), rows in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1] or -1)):
        person = getattr(rows[0], "player", None)
        players.append({"player_id": pid, "perspective": side,
            "name": person.name if person else "Actions non attribuées",
            "cap_number": getattr(person, "cap_number", None),
            "report": {**observed_report(rows), "evaluation": build_detailed_evaluation(rows, role=getattr(person, "primary_role", "")) if pid is not None else {"rated": False, "overall": None}}})
    return {"version": "measured-statistics-v1", "scope": "confirmed_sample",
        "labels": LABELS, "team": observed_report(selected, "for"),
        "opponent": observed_report(selected, "against"), "players": players,
        "excluded_unverified_events": len(all_events)-len(selected),
        "note": "Les nombres décrivent les actions confirmées dans l’échantillon. Un zéro dans cet échantillon ne prouve pas l’absence de cette action sur tout le match. Les mesures physiques sont celles renseignées, pas une calibration vérifiée automatiquement."}


def flatten_measurements(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from flatten_measurements(item, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from flatten_measurements(item, f"{prefix}[{index}]")
    else:
        yield {"metric": prefix, "value": value}
