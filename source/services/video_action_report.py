"""Same automatic measurements in the web report, export and personal history."""
from __future__ import annotations

import json
import hashlib
import time
from collections import Counter, defaultdict
from types import SimpleNamespace

from sqlalchemy import select
from models import Match, Player, VideoActionAnalysis
from services.measurement_report import LABELS
from services.ultimate_analytics import descriptive_event_report
from services.video_action_provider import provider_configuration
from services.video_action_schema import EVENT_LABELS, FAMILIES

PHYSICAL_LIMITS = {
    "distance_m": "Suivi continu du même joueur et calibration du bassin requis.",
    "shot_speed_kmh": "Suivi de la balle, cadence réelle suffisante et calibration 3D requis.",
    "release_time_s": "Détection image par image du début du geste et du lâcher requise.",
    "sprint_5m_s": "Trajectoire calibrée sur 5 m et chronométrage requis.",
    "sprint_10m_s": "Trajectoire calibrée sur 10 m et chronométrage requis.",
    "max_swim_speed_mps": "Trajectoire calibrée et identité suivie en continu requises.",
    "playing_time_seconds": "Rotations et présence dans le bassin à vérifier sur toute la durée.",
    "fatigue": "Le modèle vidéo ne mesure pas la fatigue physiologique.",
    "overall_rating": "Aucune note globale fiable sans validation des actions et de leur couverture.",
}
AUTO_LABELS = {**LABELS, **EVENT_LABELS, "events": "Actions détectées retenues",
               "goalkeeper_restart": "Relances du gardien", "rotation_in": "Entrées", "rotation_out": "Sorties",
               "playing_time_seconds": "Temps de jeu", "fatigue": "Fatigue", "overall_rating": "Note globale",
               "by_period": "Par période", "by_phase": "Par phase", "cage_zones": "Zones de la cage",
               "hand": "Main utilisée", "observed_possessions": "Possessions bornées observées"}


def latest_run(db, match_id):
    return db.scalar(select(VideoActionAnalysis).where(VideoActionAnalysis.match_id == match_id)
                     .order_by(VideoActionAnalysis.created_at.desc(), VideoActionAnalysis.id.desc()))


def run_progress(db, match, *, run=None):
    run = run or latest_run(db, match.id)
    config = provider_configuration()
    if not run:
        return {"status": "not_started" if config["configured"] else "not_configured", "active": False,
                "completed": 0, "total": 0, "revision": "", "message": config["message"], "configured": config["configured"],
                "availability_code": config["availability_code"]}
    segments = json.loads(run.segments_json or "[]")
    completed = sum(s.get("status") == "complete" for s in segments)
    stale = run.status in {"running", "queued"} and time.time() - run.updated_at > 300
    return {"run_id": run.id, "status": "interrupted" if stale else run.status,
            "active": not stale and run.status in {"queued", "running"}, "completed": completed,
            "total": len(segments), "revision": f"{run.id}:{run.status}:{completed}:{stale}",
            "message": "Le traitement a été interrompu ; les séquences terminées sont conservées." if stale else run.message,
            "configured": config["configured"], "availability_code": config["availability_code"]}


def _action_family(kind):
    if kind in {"goal", "shot_on_target", "shot_off_target", "shot_blocked"}: return "shot"
    if kind in {"assist", "key_pass", "pass_complete", "bad_pass"}: return "pass"
    if kind in {"touch", "centre_touch"}: return "touch"
    return kind


def canonical_actions(actions):
    """Prevent counting goal+shot and assist+pass for the same visible action."""
    priorities = {"goal": 4, "shot_on_target": 3, "assist": 4, "key_pass": 3,
                  "pass_complete": 2, "centre_touch": 2}
    result = []
    for action in sorted(actions, key=lambda row: (row["second"], -priorities.get(row["event_type"], 0))):
        family = _action_family(action["event_type"])
        duplicate = next((old for old in reversed(result[-10:]) if
                         old["side"] == action["side"] and old["cap_number"] == action["cap_number"]
                         and _action_family(old["event_type"]) == family
                         and abs(old["second"] - action["second"]) <= (
                             .75 if action["cap_number"] and old["segment_index"] != action["segment_index"] else .15)), None)
        if duplicate:
            # Contradictory outcomes are not resolved by taking the higher
            # confidence score. Keep the observation in the ledger for review.
            types = {duplicate["event_type"], action["event_type"]}
            compatible = types <= {"goal", "shot_on_target"} or types <= {"assist", "key_pass", "pass_complete"} or types <= {"touch", "centre_touch"} or len(types) == 1
            if not compatible:
                duplicate["counted"] = False
                duplicate["conflict"] = "Issues contradictoires dans les détections de la même action."
                action["counted"] = False
                action["conflict"] = duplicate["conflict"]
                result.append(action)
            elif priorities.get(action["event_type"], 0) > priorities.get(duplicate["event_type"], 0):
                result[result.index(duplicate)] = action
            continue
        result.append(action)
    return result


def _event_proxy(action):
    tags = {key: action.get(key) for key in ("phase", "period", "zone", "cage_zone", "hand", "shot_type", "pass_type", "cause", "pressure", "decision")
            if action.get(key) not in {None, "unknown", ""}}
    return SimpleNamespace(second=action["second"], event_type=action["event_type"],
                           confidence="AUTOMATIC", player=None, player_id=None,
                           note=" ".join(f"{key}={value}" for key, value in tags.items()),
                           context_meta=SimpleNamespace(perspective=action["side"], phase_tag=action.get("phase", "unknown"), quality_tag=""))


def summarize_actions(actions):
    report = descriptive_event_report([_event_proxy(action) for action in actions])
    if not actions:
        report["basic"] = {key: 0 if key == "events" else None for key in report["basic"]}
    report["event_counts"] = {key: (sum(a["event_type"] == key for a in actions) if actions else None) for key in EVENT_LABELS}
    report["cage_zones"] = dict(Counter(a["cage_zone"] for a in actions if a["event_type"] in {"goal", "shot_on_target", "shot_off_target", "shot_blocked"} and a.get("cage_zone") != "unknown"))
    report["by_period"] = _group_summary(actions, "period")
    report["by_phase"] = _group_summary(actions, "phase")
    report["tag_breakdowns"] = {key: dict(Counter(str(a[key]) for a in actions if a.get(key) not in {None,"unknown",""}))
                                for key in ("zone","cage_zone","hand","shot_type","pass_type","cause","pressure","decision")}
    report["observed_possessions"] = bounded_possessions(actions)
    # Remove prose that calls automatically inferred tags 'confirmed' and the
    # annotation-based readiness score, which is not sporting accuracy.
    report.pop("qualitative", None)
    report.pop("coverage", None)
    return report


def bounded_possessions(actions):
    """Only pair observed boundaries inside the same continuous analysed clip."""
    opened = {}
    intervals = []
    for action in sorted(actions, key=lambda a: a["second"]):
        side = action["side"]
        if side == "unknown":
            continue
        if action["event_type"] == "possession_start":
            opened[side] = action
        elif action["event_type"] == "possession_end":
            start = opened.pop(side, None)
            if start and start["segment_index"] == action["segment_index"] and start["second"] < action["second"]:
                observed = [a for a in actions if a["side"] == side and start["second"] <= a["second"] <= action["second"]]
                shots = [a for a in observed if a["event_type"] in {"goal", "shot_on_target", "shot_off_target", "shot_blocked"}]
                intervals.append({"start_second": start["second"], "end_second": action["second"],
                                  "video_duration_seconds": round(action["second"] - start["second"], 3),
                                  "passes": sum(a["event_type"] in {"assist","key_pass","pass_complete","bad_pass"} for a in observed),
                                  "shots": len(shots), "goals": sum(a["event_type"] == "goal" for a in shots),
                                  "first_shot_after_seconds": round(shots[0]["second"] - start["second"], 3) if shots else None})
    return {"count": len(intervals) if intervals else None, "intervals": intervals,
            "note": "Bornes de possession proposées par le modèle dans une même séquence continue. Durées en temps vidéo, pas en chrono de jeu ; aucune extrapolation aux possessions manquantes."}


def _group_summary(actions, key):
    groups = defaultdict(list)
    for action in actions:
        groups[str(action.get(key) or "unknown")].append(action)
    return {name: descriptive_event_report([_event_proxy(action) for action in rows])["basic"] for name, rows in groups.items()}


def action_report(db, match, *, run=None):
    run = run or latest_run(db, match.id)
    progress = run_progress(db, match, run=run)
    result = {**progress, "labels": AUTO_LABELS, "events": [], "players": [], "available": False,
              "team": summarize_actions([]), "opponent": summarize_actions([]), "unassigned": summarize_actions([]),
              "segments": [], "coverage_percent": 0, "processed_seconds": 0, "duration_seconds": 0,
              "physical": [{"metric": key, "label": AUTO_LABELS.get(key, key), "value": None, "reason": value} for key, value in PHYSICAL_LIMITS.items()],
              "families": [], "scope": "automatic_detections", "model": run.model if run else "",
              "note": "Statistiques calculées sur les actions détectées automatiquement, sans validation humaine. Les zéros signifient aucune détection dans cet échantillon. Les images manquantes, actions masquées ou bonnets illisibles peuvent modifier les totaux. La couverture traitée ne mesure pas la précision du modèle."}
    if not run:
        return result
    segments = json.loads(run.segments_json or "[]")
    rows = []
    visibility = defaultdict(list)
    processed = 0
    for segment in segments:
        payload = segment.get("result", {})
        if segment["status"] == "complete":
            processed += segment["end"] - segment["start"]
            for action in payload.get("actions", []):
                rows.append({**action, "counted": action["confidence"] >= .65})
            for item in payload.get("observability", []):
                visibility[item["family"]].append({**item, "start": segment["start"], "end": segment["end"]})
        result["segments"].append({"index": segment["index"], "start": segment["start"], "end": segment["end"],
                                   "status": segment["status"], "summary": payload.get("summary", ""),
                                   "scene": payload.get("scene", ""), "error": segment.get("error", ""),
                                   "error_code": segment.get("error_code", ""), "ignored": payload.get("ignored", {})})
    rows = canonical_actions(rows)
    for action in rows:
        identity = [run.id, action["segment_index"], action["second"], action["event_type"], action["side"], action["cap_number"]]
        action["key"] = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
        action["label"] = EVENT_LABELS[action["event_type"]]
        action["identity"] = f"Bonnet {action['cap_number']}" if action["cap_number"] else "Bonnet indéterminé"
        action["clip_url"] = f"/matches/{match.id}/analysis/actions/{run.id}/{action['key']}/clip"
    counted = [a for a in rows if a["counted"]]
    result.update(available=bool(counted), events=rows, event_count=len(counted),
                  excluded_count=len(rows) - len(counted), processed_seconds=round(processed, 2),
                  duration_seconds=run.duration_seconds,
                  coverage_percent=round(min(100, processed / run.duration_seconds * 100), 1) if run.duration_seconds else 0,
                  team=summarize_actions([a for a in counted if a["side"] == "for"]),
                  opponent=summarize_actions([a for a in counted if a["side"] == "against"]),
                  unassigned=summarize_actions([a for a in counted if a["side"] == "unknown"]))
    groups = defaultdict(list)
    for action in counted:
        groups[(action["side"], action["cap_number"])].append(action)
    for (side, number), actions in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1] or 0)):
        result["players"].append({"side": side, "cap_number": number,
                                  "name": f"Bonnet {number}" if number else "Actions sans bonnet lisible",
                                  "identity_status": "visual_candidate" if number else "unresolved",
                                  "report": summarize_actions(actions), "event_keys": [a["key"] for a in actions]})
    result["families"] = [{"key": key, "label": label, "observations": visibility[key]} for key, label in FAMILIES.items()]
    return result


def automatic_player_history(db, player, owner_id):
    """Tentative cap association, scoped to this owner's team; no name matching."""
    if not player.cap_number:
        return []
    same_cap = db.scalars(select(Player.id).where(Player.team_id == player.team_id, Player.cap_number == player.cap_number)).all()
    if len(same_cap) != 1:
        return []
    matches = db.scalars(select(Match).where(Match.team_id == player.team_id, Match.owner_id == owner_id)
                        .order_by(Match.id.desc())).all()
    history = []
    for match in matches:
        if not latest_run(db, match.id):
            continue
        report = action_report(db, match)
        person = next((p for p in report["players"] if p["side"] == "for" and p["cap_number"] == player.cap_number), None)
        if person:
            history.append({"match_id": match.id, "opponent": match.opponent, "report": person["report"],
                            "coverage_percent": report["coverage_percent"], "cap_number": player.cap_number})
    return history


def attach_export_clips(report, media):
    for action in report["events"]:
        marker = f"action_key={action['key']} "
        clip = next((m for m in media if str(m.get("note", "")).startswith(marker)), None)
        if clip is None:
            # A materialized review window can contain several actions. Link it
            # when its real bounds contain the action; never imply a missing file.
            clip = next((m for m in media if float(m.get("start_second") or 0) <= action["second"] < float(m.get("end_second") or 0)), None)
        action["export_clip_url"] = clip["file_url"] if clip else ""
