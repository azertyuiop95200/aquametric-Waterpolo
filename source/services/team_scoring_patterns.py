from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import select

from models import AutonomousAnalysis, LibraryPlayerMatchStat, Match, MatchLibraryItem
from services.ultimate_analytics import SHOT_EVENTS, note_tags
from services.video import timestamped_video_url

PHASE_LABELS = {
    "even_attack": "6v6 attaque placée",
    "even_defence": "6v6 défense",
    "power_play": "6v5",
    "penalty_kill": "5v6",
    "counterattack": "Contre-attaque",
    "defensive_recovery": "Repli",
    "centre_play": "Jeu centre",
    "restart": "Remise en jeu",
    "auto": "Phase non renseignée",
}

SIGNIFICANT_BUILDUP = {
    "assist", "key_pass", "action_created", "centre_touch", "exclusion_earned",
    "penalty_earned", "interception", "recovery", "pass_complete", "duel_won",
    "counterattack_start", "power_play_start",
}
LOSS_EVENTS = {"turnover", "bad_pass"}


def _pct(n, d):
    return round(100.0 * float(n) / float(d), 1) if d else None


def _meta(event):
    context = getattr(event, "context_meta", None)
    return {
        "perspective": getattr(context, "perspective", "for") if context else "for",
        "phase": getattr(context, "phase_tag", "auto") if context else "auto",
        "quality": getattr(context, "quality_tag", "") if context else "",
    }


def _side_events(match, perspective: str):
    events = sorted(list(match.events or []), key=lambda e: float(e.second or 0))
    if perspective == "against":
        return [e for e in events if _meta(e)["perspective"] == "against"]
    return [e for e in events if _meta(e)["perspective"] != "against"]


def _phase(event):
    return _meta(event)["phase"] or "auto"


def _periods(db, match_id: int):
    row = db.scalar(
        select(AutonomousAnalysis)
        .where(AutonomousAnalysis.match_id == match_id)
        .order_by(AutonomousAnalysis.created_at.desc(), AutonomousAnalysis.id.desc())
    )
    if not row:
        return []
    try:
        data = json.loads(row.periods_json or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _period_at(second: float, periods: list[dict]):
    for row in periods:
        try:
            start = float(row.get("start_second", 0) or 0)
            end = float(row.get("end_second", start) or start)
            if start <= second <= end:
                return int(row.get("period")) if row.get("period") else None
        except (TypeError, ValueError):
            continue
    return None


def _route_signature(goal, side_events):
    second = float(goal.second or 0)
    buildup = [
        e for e in side_events
        if 0 <= second - float(e.second or 0) <= 12.0 and e.id != goal.id
        and e.event_type in SIGNIFICANT_BUILDUP
    ]
    # Keep the last four meaningful actions and collapse immediate duplicates.
    tokens = []
    for event in buildup[-5:]:
        token = event.event_type
        if not tokens or tokens[-1] != token:
            tokens.append(token)
    tokens.append("goal")
    return tokens[-5:]


def _best_media(match, second: float):
    artifacts = sorted(
        list(match.media_artifacts or []),
        key=lambda a: (
            0 if a.artifact_type == "clip" else 1,
            0 if str(a.source or "").startswith("analysis_") else 1,
            abs(float(a.second or 0) - second),
        ),
    )
    for artifact in artifacts:
        if abs(float(artifact.second or 0) - second) > 2.0:
            continue
        if artifact.file_path:
            return {
                "kind": artifact.artifact_type,
                "url": f"/matches/{match.id}/evidence/{artifact.id}",
                "downloadable": bool(artifact.is_downloadable),
            }
        if artifact.external_url:
            return {"kind": "external", "url": artifact.external_url, "downloadable": False}
    if match.video_url:
        return {"kind": "external", "url": timestamped_video_url(match.video_url, max(0, second - 5)), "downloadable": False}
    return {"kind": "", "url": "", "downloadable": False}


def _habit(kind: str, title: str, text: str, evidence: str, strength: str = "MODERATE"):
    return {"kind": kind, "title": title, "text": text, "evidence": evidence, "strength": strength}


def _current_side_report(match, perspective: str, label: str, periods: list[dict]):
    events = _side_events(match, perspective)
    goals = [e for e in events if e.event_type == "goal"]
    shots = [e for e in events if e.event_type in SHOT_EVENTS]
    losses = [e for e in events if e.event_type in LOSS_EVENTS]
    phase_goals = Counter(_phase(e) for e in goals)
    phase_shots = Counter(_phase(e) for e in shots)
    phase_losses = Counter(_phase(e) for e in losses)
    types = Counter(e.event_type for e in events)

    scorer_counts = Counter(e.player.name for e in goals if e.player and e.player.name)
    goal_sequences = []
    route_counts = Counter()
    assisted_or_key = 0
    after_exclusion = 0
    after_recovery = 0
    for goal in goals:
        route = _route_signature(goal, events)
        signature = " → ".join(route)
        route_counts[signature] += 1
        second = float(goal.second or 0)
        preceding = [e for e in events if 0 <= second - float(e.second or 0) <= 12 and e.id != goal.id]
        if any(e.event_type in {"assist", "key_pass"} for e in preceding):
            assisted_or_key += 1
        if any(e.event_type in {"exclusion_earned", "power_play_start"} for e in preceding):
            after_exclusion += 1
        if any(e.event_type in {"recovery", "interception", "counterattack_start"} for e in preceding):
            after_recovery += 1
        media = _best_media(match, second)
        goal_sequences.append({
            "event_id": goal.id,
            "second": second,
            "period": _period_at(second, periods),
            "phase": _phase(goal),
            "phase_label": PHASE_LABELS.get(_phase(goal), _phase(goal)),
            "scorer": goal.player.name if goal.player else "Non identifiée",
            "route": route,
            "signature": signature,
            "note": goal.note or "",
            "source": goal.source,
            "media": media,
        })

    phase_rows = []
    for key in sorted(set(phase_goals) | set(phase_shots), key=lambda k: (-phase_goals[k], -phase_shots[k], k)):
        phase_rows.append({
            "key": key,
            "label": PHASE_LABELS.get(key, key.replace("_", " ").title()),
            "goals": phase_goals[key],
            "shots": phase_shots[key],
            "goal_share_pct": _pct(phase_goals[key], len(goals)),
            "conversion_pct": _pct(phase_goals[key], phase_shots[key]),
        })

    repeated = [
        {"signature": sig, "count": count, "share_pct": _pct(count, len(goals))}
        for sig, count in route_counts.most_common(8) if count >= 2
    ]

    positive, negative, tendencies = [], [], []
    total_goals = len(goals)
    total_shots = len(shots)
    conversion = _pct(total_goals, total_shots)
    on_target = sum(1 for e in shots if e.event_type in {"goal", "shot_on_target"})
    accuracy = _pct(on_target, total_shots)

    if total_goals >= 2 and phase_rows:
        dominant = phase_rows[0]
        if dominant["goal_share_pct"] is not None and dominant["goal_share_pct"] >= 40:
            tendencies.append(_habit(
                "tendency", "Voie de but dominante",
                f"{dominant['goal_share_pct']}% des buts observés viennent de {dominant['label']}.",
                f"{dominant['goals']} buts sur {total_goals}",
                "HIGH" if dominant["goals"] >= 3 else "MODERATE",
            ))
    if repeated:
        top = repeated[0]
        tendencies.append(_habit(
            "tendency", "Enchaînement répété",
            f"La route « {top['signature']} » apparaît plusieurs fois avant un but.",
            f"{top['count']} occurrences sur {total_goals} buts",
            "HIGH" if top["count"] >= 3 else "MODERATE",
        ))
    if scorer_counts and total_goals >= 3:
        scorer, count = scorer_counts.most_common(1)[0]
        share = _pct(count, total_goals)
        if share and share >= 45:
            tendencies.append(_habit(
                "tendency", "Forte concentration du scoring",
                f"{scorer} représente {share}% des buts identifiés.",
                f"{count}/{total_goals} buts",
                "MODERATE",
            ))

    if total_shots >= 5 and conversion is not None:
        if conversion >= 40:
            positive.append(_habit("positive", "Finition efficace", f"Conversion observée de {conversion}%.", f"{total_goals}/{total_shots} tirs", "HIGH" if total_shots >= 8 else "MODERATE"))
        elif conversion <= 25:
            negative.append(_habit("negative", "Finition à améliorer", f"Conversion observée de {conversion}%.", f"{total_goals}/{total_shots} tirs", "HIGH" if total_shots >= 8 else "MODERATE"))
    if total_shots >= 5 and accuracy is not None:
        if accuracy >= 65:
            positive.append(_habit("positive", "Cadrage régulier", f"{accuracy}% des tirs observés sont cadrés ou marqués.", f"{on_target}/{total_shots} tirs", "MODERATE"))
        elif accuracy <= 40:
            negative.append(_habit("negative", "Trop de tirs hors cadre / bloqués", f"Seulement {accuracy}% des tirs observés atteignent la cible.", f"{on_target}/{total_shots} tirs", "MODERATE"))

    power_starts = types["power_play_start"]
    power_goals = phase_goals["power_play"]
    if power_starts >= 3:
        rate = _pct(power_goals, power_starts)
        if rate is not None and rate >= 45:
            positive.append(_habit("positive", "6v5 productif", f"Buts observés sur {rate}% des démarrages 6v5 tagués.", f"{power_goals}/{power_starts}", "MODERATE"))
        elif rate is not None and rate <= 20:
            negative.append(_habit("negative", "6v5 peu productif", f"Seulement {rate}% des démarrages 6v5 tagués aboutissent à un but observé.", f"{power_goals}/{power_starts}", "MODERATE"))

    if total_goals >= 3:
        share = _pct(after_recovery, total_goals)
        if share is not None and share >= 30:
            positive.append(_habit("positive", "Transition convertie en buts", f"{share}% des buts suivent une récupération/interception/départ de contre dans les 12 s.", f"{after_recovery}/{total_goals} buts", "MODERATE"))
        share = _pct(assisted_or_key, total_goals)
        if share is not None and share >= 40:
            positive.append(_habit("positive", "Création avant finition", f"{share}% des buts ont une passe décisive ou passe clé taguée dans les 12 s précédentes.", f"{assisted_or_key}/{total_goals} buts", "MODERATE"))
        share = _pct(after_exclusion, total_goals)
        if share is not None and share >= 30:
            tendencies.append(_habit("tendency", "Scoring après exclusion provoquée", f"{share}% des buts suivent une exclusion provoquée ou un départ 6v5 dans les 12 s.", f"{after_exclusion}/{total_goals} buts", "MODERATE"))

    if len(losses) >= 3:
        bad = types["bad_pass"]
        if _pct(bad, len(losses)) and _pct(bad, len(losses)) >= 50:
            negative.append(_habit("negative", "Passe comme source principale de pertes", f"{_pct(bad, len(losses))}% des pertes observées sont des mauvaises passes.", f"{bad}/{len(losses)} pertes", "MODERATE"))
        if phase_losses:
            phase, count = phase_losses.most_common(1)[0]
            share = _pct(count, len(losses))
            if share and share >= 45:
                negative.append(_habit("negative", "Pertes concentrées dans une phase", f"{share}% des pertes surviennent en {PHASE_LABELS.get(phase, phase)}.", f"{count}/{len(losses)} pertes", "MODERATE"))

    committed = types["exclusion_committed"] + types["penalty_committed"]
    if committed >= 3:
        negative.append(_habit("negative", "Discipline défensive coûteuse", "Les exclusions/penalties commis se répètent sur ce match.", f"{committed} sanctions taguées", "MODERATE"))

    fast, late = types["fast_recovery"], types["late_recovery"]
    if fast + late >= 3:
        if fast >= late * 1.5 and fast >= 3:
            positive.append(_habit("positive", "Repli rapide récurrent", "Les replis rapides dominent nettement les replis tardifs tagués.", f"{fast} rapides / {late} tardifs", "MODERATE"))
        elif late > fast and late >= 3:
            negative.append(_habit("negative", "Retard de repli récurrent", "Les replis tardifs dépassent les replis rapides tagués.", f"{late} tardifs / {fast} rapides", "MODERATE"))

    phase_tagged = sum(1 for e in goals if _phase(e) != "auto")
    quality = {
        "events": len(events),
        "goals": total_goals,
        "shots": total_shots,
        "phase_tagged_goals": phase_tagged,
        "phase_coverage_pct": _pct(phase_tagged, total_goals),
        "identified_scorers": sum(scorer_counts.values()),
        "scorer_coverage_pct": _pct(sum(scorer_counts.values()), total_goals),
        "readiness": "STRONG" if total_goals >= 5 and phase_tagged >= 3 else "PARTIAL" if total_goals >= 2 else "LOW",
    }

    return {
        "label": label,
        "perspective": perspective,
        "goals": total_goals,
        "shots": total_shots,
        "conversion_pct": conversion,
        "shot_accuracy_pct": accuracy,
        "phase_rows": phase_rows,
        "top_scorers": [{"player": name, "goals": count, "share_pct": _pct(count, total_goals)} for name, count in scorer_counts.most_common(8)],
        "repeated_routes": repeated,
        "goal_sequences": goal_sequences,
        "positive_habits": positive,
        "negative_habits": negative,
        "tendencies": tendencies,
        "data_quality": quality,
    }


def _name_key(value: str):
    text = re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
    aliases = {"espana": "spain", "espagne": "spain", "grece": "greece", "united states": "usa", "united states of america": "usa"}
    return aliases.get(text, text)


def _same_name(a: str, b: str):
    ka, kb = _name_key(a), _name_key(b)
    return bool(ka and kb and (ka == kb or ka in kb or kb in ka))


def _quarter_pair(row):
    if isinstance(row, dict):
        a = row.get("a", row.get("home"))
        b = row.get("b", row.get("away"))
        return a, b
    if isinstance(row, (list, tuple)) and len(row) >= 2:
        return row[0], row[1]
    return None, None


def _public_history(db, team_name: str, limit: int = 12):
    matches = []
    all_items = db.scalars(select(MatchLibraryItem).order_by(MatchLibraryItem.id.desc())).all()
    for item in all_items:
        if not (_same_name(item.team_a, team_name) or _same_name(item.team_b, team_name)):
            continue
        side_a = _same_name(item.team_a, team_name)
        gf = item.score_a if side_a else item.score_b
        ga = item.score_b if side_a else item.score_a
        try:
            quarters = json.loads(item.quarter_scores_json or "[]")
            if not isinstance(quarters, list):
                quarters = []
        except Exception:
            quarters = []
        q_for = []
        for q in quarters:
            a, b = _quarter_pair(q)
            try:
                if a is not None and b is not None:
                    q_for.append(int(a if side_a else b))
            except (TypeError, ValueError):
                continue
        matches.append({
            "id": item.id, "title": item.title, "competition": item.competition, "season": item.season,
            "goals_for": gf, "goals_against": ga, "quarter_goals": q_for,
            "official_source_url": item.official_source_url, "video_url": item.video_url,
        })
        if len(matches) >= limit:
            break

    valid = [m for m in matches if m["goals_for"] is not None and m["goals_against"] is not None]
    avg_for = round(sum(m["goals_for"] for m in valid) / len(valid), 2) if valid else None
    avg_against = round(sum(m["goals_against"] for m in valid) / len(valid), 2) if valid else None
    quarter_totals = defaultdict(list)
    for match in matches:
        for idx, value in enumerate(match["quarter_goals"][:4], start=1):
            quarter_totals[idx].append(value)
    quarter_rows = [
        {"period": q, "avg_goals": round(sum(values) / len(values), 2), "samples": len(values)}
        for q, values in sorted(quarter_totals.items()) if values
    ]

    item_ids = [m["id"] for m in matches]
    scorers = Counter()
    if item_ids:
        stats = db.scalars(select(LibraryPlayerMatchStat).where(LibraryPlayerMatchStat.library_match_id.in_(item_ids))).all()
        for row in stats:
            if _same_name(row.team_name, team_name) and row.goals is not None:
                scorers[row.player_name] += int(row.goals or 0)
    return {
        "team": team_name,
        "matches": matches,
        "match_count": len(matches),
        "score_sample_count": len(valid),
        "avg_goals_for": avg_for,
        "avg_goals_against": avg_against,
        "quarter_profile": quarter_rows,
        "top_scorers": [{"player": name, "goals": goals} for name, goals in scorers.most_common(8)],
        "contract": "Tendance historique publiée : le score et les feuilles de match décrivent des fréquences, pas la cause tactique d'un but sans séquence vidéo horodatée.",
    }


def _owned_history(db, match, limit: int = 10):
    rows = db.scalars(
        select(Match)
        .where(Match.owner_id == match.owner_id, Match.team_id == match.team_id, Match.id != match.id)
        .order_by(Match.created_at.desc(), Match.id.desc())
        .limit(limit)
    ).all()
    phase = Counter()
    goals = 0
    losses = 0
    for row in rows:
        events = _side_events(row, "for")
        for event in events:
            if event.event_type == "goal":
                goals += 1
                phase[_phase(event)] += 1
            if event.event_type in LOSS_EVENTS:
                losses += 1
    return {
        "match_count": len(rows),
        "goals": goals,
        "losses": losses,
        "goal_phase_distribution": [
            {"key": key, "label": PHASE_LABELS.get(key, key), "goals": count, "share_pct": _pct(count, goals)}
            for key, count in phase.most_common()
        ],
        "contract": "Historique workspace privé : uniquement les événements déjà vérifiés/tagués dans les matchs de ce compte.",
    }


def build_team_scoring_patterns(db, match):
    periods = _periods(db, match.id)
    team = _current_side_report(match, "for", match.team.name, periods)
    opponent = _current_side_report(match, "against", match.opponent, periods)
    return {
        "team": team,
        "opponent": opponent,
        "team_owned_history": _owned_history(db, match),
        "team_public_history": _public_history(db, match.team.name),
        "opponent_public_history": _public_history(db, match.opponent),
        "contract": (
            "Une tendance devient visible quand un comportement se répète. AquaMetric sépare les faits du match, "
            "les habitudes observées sur plusieurs matchs et les hypothèses. Aucun score seul n'est converti en cause tactique."
        ),
    }


def _csv_text(headers, rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def append_scoring_patterns_to_zip(zip_buffer: io.BytesIO, report: dict, root: str):
    zip_buffer.seek(0, io.SEEK_END)
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{root}/02_kpis/scoring_patterns.json", json.dumps(report, ensure_ascii=False, indent=2, default=str))
        sequence_rows = []
        habit_rows = []
        for side in ("team", "opponent"):
            data = report.get(side, {})
            for row in data.get("goal_sequences", []):
                sequence_rows.append({
                    "side": side, "second": row.get("second"), "period": row.get("period"),
                    "phase": row.get("phase"), "scorer": row.get("scorer"),
                    "signature": row.get("signature"), "source": row.get("source"),
                    "media_url": row.get("media", {}).get("url", ""),
                })
            for category in ("positive_habits", "negative_habits", "tendencies"):
                for row in data.get(category, []):
                    habit_rows.append({"side": side, "category": category, **row})
        archive.writestr(
            f"{root}/04_sequences/scoring_sequences.csv",
            _csv_text(["side", "second", "period", "phase", "scorer", "signature", "source", "media_url"], sequence_rows),
        )
        archive.writestr(
            f"{root}/02_kpis/team_habits.csv",
            _csv_text(["side", "category", "kind", "title", "text", "evidence", "strength"], habit_rows),
        )
    zip_buffer.seek(0)
    return zip_buffer
