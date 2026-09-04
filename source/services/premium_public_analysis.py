from __future__ import annotations

import json
from collections import Counter, defaultdict
from statistics import mean
from urllib.parse import urlencode

from sqlalchemy import select

from models import LibraryPlayerMatchStat, MatchLibraryItem
from services.video import youtube_embed


def _safe_json(raw, fallback):
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, type(fallback)) else fallback
    except Exception:
        return fallback


def _pct(n, d):
    return round(100.0 * float(n) / float(d), 1) if d else None


def _pair_score(quarters):
    rows = []
    ca = cb = 0
    previous_lead = 0
    lead_changes = 0
    for idx, pair in enumerate(quarters, start=1):
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        try:
            a, b = int(pair[0]), int(pair[1])
        except (TypeError, ValueError):
            continue
        ca += a; cb += b
        lead = 1 if ca > cb else (-1 if ca < cb else 0)
        if previous_lead and lead and lead != previous_lead:
            lead_changes += 1
        if lead:
            previous_lead = lead
        rows.append({
            "quarter": idx, "a": a, "b": b, "diff": a - b,
            "cumulative_a": ca, "cumulative_b": cb,
            "margin": abs(a-b),
        })
    return rows, lead_changes


def _team_history(db, team_name: str, current_id: int, limit: int = 24):
    if not team_name:
        return []
    items = db.scalars(select(MatchLibraryItem).where(MatchLibraryItem.id != current_id)).all()
    out = []
    for item in items:
        if item.team_a != team_name and item.team_b != team_name:
            continue
        if item.score_a is None or item.score_b is None:
            continue
        for_side = item.score_a if item.team_a == team_name else item.score_b
        against = item.score_b if item.team_a == team_name else item.score_a
        out.append({
            "id": item.id,
            "competition": item.competition,
            "season": item.season,
            "opponent": item.team_b if item.team_a == team_name else item.team_a,
            "goals_for": int(for_side), "goals_against": int(against),
            "result": "W" if for_side > against else ("D" if for_side == against else "L"),
        })
    return out[:limit]


def _history_summary(rows):
    if not rows:
        return {"matches": 0, "wins": 0, "draws": 0, "losses": 0, "avg_for": None, "avg_against": None, "win_pct": None}
    wins = sum(1 for r in rows if r["result"] == "W")
    draws = sum(1 for r in rows if r["result"] == "D")
    losses = sum(1 for r in rows if r["result"] == "L")
    return {
        "matches": len(rows), "wins": wins, "draws": draws, "losses": losses,
        "avg_for": round(mean(r["goals_for"] for r in rows), 1),
        "avg_against": round(mean(r["goals_against"] for r in rows), 1),
        "win_pct": _pct(wins, len(rows)),
    }


def _scorer_report(rows, team_name: str, team_goals: int | None):
    team_rows = [r for r in rows if (r.team_name or "") == team_name]
    scorers = [r for r in team_rows if r.goals is not None and int(r.goals or 0) > 0]
    scorers.sort(key=lambda r: int(r.goals or 0), reverse=True)
    known_total = sum(int(r.goals or 0) for r in scorers)
    denominator = int(team_goals) if team_goals is not None and int(team_goals) > 0 else known_total
    cards = []
    for rank, row in enumerate(scorers, start=1):
        goals = int(row.goals or 0)
        cards.append({
            "rank": rank,
            "name": row.player_name,
            "goals": goals,
            "share_pct": _pct(goals, denominator),
            "shots": row.shots,
            "shooting_pct": _pct(goals, row.shots) if row.shots else None,
            "assists": row.assists,
            "steals": row.steals,
            "exclusions": row.exclusions,
            "saves": row.saves,
            "source_quality": row.source_quality,
            "note": row.note or "",
        })
    concentration = cards[0]["share_pct"] if cards else None
    spread = len(cards)
    balance = "balanced" if spread >= 6 and (concentration or 0) < 35 else "concentrated" if (concentration or 0) >= 45 else "mixed"
    return {
        "rows": cards, "known_goals": known_total, "team_goals": denominator,
        "coverage_pct": _pct(known_total, denominator) if denominator else None,
        "scorers": spread, "top_share_pct": concentration, "balance": balance,
    }


def _habit(kind, title, text, evidence, strength="MODERATE"):
    return {"kind": kind, "title": title, "text": text, "evidence": evidence, "strength": strength}


def _match_habits(item, quarter_rows, team_a_scorers, team_b_scorers, hist_a, hist_b):
    positive_a, risk_a, positive_b, risk_b, shared = [], [], [], [], []
    if quarter_rows:
        biggest = max(quarter_rows, key=lambda q: q["margin"])
        if biggest["margin"] >= 3:
            winner = item.team_a if biggest["diff"] > 0 else item.team_b
            shared.append(_habit("tendency", "Quart de bascule", f"Q{biggest['quarter']} crée la plus grande rupture du match, au bénéfice de {winner}.", f"Q{biggest['quarter']} {biggest['a']}–{biggest['b']}"))
        first_a = sum(q["a"] for q in quarter_rows[:2]); first_b = sum(q["b"] for q in quarter_rows[:2])
        second_a = sum(q["a"] for q in quarter_rows[2:]); second_b = sum(q["b"] for q in quarter_rows[2:])
        if second_a - second_b >= 3:
            positive_a.append(_habit("positive", "Deuxième moitié forte", f"{item.team_a} gagne nettement la deuxième moitié.", f"2e moitié {second_a}–{second_b}"))
        if second_b - second_a >= 3:
            positive_b.append(_habit("positive", "Deuxième moitié forte", f"{item.team_b} gagne nettement la deuxième moitié.", f"2e moitié {second_b}–{second_a}"))
        if first_a - first_b >= 3 and second_a < second_b:
            risk_a.append(_habit("negative", "Avantage initial moins bien prolongé", f"{item.team_a} construit un avantage avant la pause mais perd la deuxième moitié.", f"1re {first_a}–{first_b} · 2e {second_a}–{second_b}"))
        if first_b - first_a >= 3 and second_b < second_a:
            risk_b.append(_habit("negative", "Avantage initial moins bien prolongé", f"{item.team_b} construit un avantage avant la pause mais perd la deuxième moitié.", f"1re {first_b}–{first_a} · 2e {second_b}–{second_a}"))
        q4 = next((q for q in quarter_rows if q["quarter"] == 4), None)
        if q4 and q4["diff"] >= 3:
            positive_a.append(_habit("positive", "Fin de match dominante", f"{item.team_a} ferme fortement le match au Q4.", f"Q4 {q4['a']}–{q4['b']}"))
        if q4 and q4["diff"] <= -3:
            positive_b.append(_habit("positive", "Fin de match dominante", f"{item.team_b} ferme fortement le match au Q4.", f"Q4 {q4['b']}–{q4['a']}"))

    for team, report, positive, risk in [
        (item.team_a, team_a_scorers, positive_a, risk_a),
        (item.team_b, team_b_scorers, positive_b, risk_b),
    ]:
        if report["scorers"] >= 6 and (report["top_share_pct"] or 0) < 35:
            positive.append(_habit("positive", "Scoring réparti", f"{team} implique de nombreuses buteuses sans dépendance extrême à une seule joueuse.", f"{report['scorers']} buteuses connues · top share {report['top_share_pct'] or '—'}%"))
        if (report["top_share_pct"] or 0) >= 45:
            risk.append(_habit("negative", "Scoring très concentré", f"Une seule joueuse représente une part très importante des buts connus de {team}.", f"Top share {report['top_share_pct']}%"))

    for team, hist, positive, risk in [
        (item.team_a, hist_a, positive_a, risk_a), (item.team_b, hist_b, positive_b, risk_b)
    ]:
        if hist["matches"] >= 4:
            if (hist["win_pct"] or 0) >= 70:
                positive.append(_habit("positive", "Tendance de résultats forte", f"{team} gagne régulièrement dans l'échantillon disponible.", f"{hist['wins']}/{hist['matches']} victoires · {hist['win_pct']}%"))
            if hist["avg_against"] is not None and hist["avg_against"] <= 9:
                positive.append(_habit("positive", "Volume encaissé contenu", f"{team} reste à un niveau moyen de buts encaissés relativement bas dans l'historique disponible.", f"{hist['avg_against']} buts encaissés/match"))
            if hist["avg_against"] is not None and hist["avg_against"] >= 14:
                risk.append(_habit("negative", "Volume encaissé élevé", f"L'historique disponible montre un volume moyen de buts encaissés élevé pour {team}.", f"{hist['avg_against']} buts encaissés/match"))
    return {"team_a_positive": positive_a, "team_a_risks": risk_a, "team_b_positive": positive_b, "team_b_risks": risk_b, "shared": shared}


def _video_reference(item):
    if item.video_url:
        return {"url": item.video_url, "embed": youtube_embed(item.video_url) or "", "label": "Replay lié au dossier", "verified": True}
    # Curated official/high-quality references already used elsewhere in AquaMetric.
    pairs = {
        frozenset({"Russia", "Spain"}): ("https://www.youtube.com/watch?v=VvuJSTuuUI8", "Russie–Espagne · World Cup 2026"),
        frozenset({"United States", "Spain"}): ("https://www.youtube.com/watch?v=a5Ja269h5G8", "USA–Espagne · World Cup 2026"),
        frozenset({"Spain", "Netherlands"}): ("https://www.youtube.com/watch?v=Z-8PwbnKBWU", "Espagne–Pays-Bas · Mondiaux 2025"),
        frozenset({"Hungary", "Spain"}): ("https://www.youtube.com/watch?v=HfkCCOpLIBA", "Hongrie–Espagne · Mondiaux 2025"),
        frozenset({"Greece", "United States"}): ("https://www.youtube.com/watch?v=Ek1kBvUjivc", "Grèce–USA · Mondiaux 2025"),
        frozenset({"Greece", "Hungary"}): ("https://www.youtube.com/watch?v=TseN9CGbfQw", "Grèce–Hongrie · Mondiaux 2025"),
        frozenset({"France", "Israel"}): ("https://www.youtube.com/watch?v=fWFM4kB8nvw", "France–Israël · référence 2026"),
    }
    key = frozenset({item.team_a, item.team_b})
    if key in pairs:
        url, label = pairs[key]
        return {"url": url, "embed": youtube_embed(url) or "", "label": label, "verified": True}
    return {"url": "", "embed": "", "label": "", "verified": False}


def build_public_match_dossier(db, item: MatchLibraryItem):
    quarters = _safe_json(item.quarter_scores_json, [])
    quarter_rows, lead_changes = _pair_score(quarters)
    player_rows = db.scalars(select(LibraryPlayerMatchStat).where(LibraryPlayerMatchStat.library_match_id == item.id)).all()
    scorer_a = _scorer_report(player_rows, item.team_a, item.score_a)
    scorer_b = _scorer_report(player_rows, item.team_b, item.score_b)
    history_a_rows = _team_history(db, item.team_a, item.id)
    history_b_rows = _team_history(db, item.team_b, item.id)
    history_a = _history_summary(history_a_rows)
    history_b = _history_summary(history_b_rows)
    habits = _match_habits(item, quarter_rows, scorer_a, scorer_b, history_a, history_b)
    team_stats = _safe_json(item.team_stats_json, {})
    evidence_meta = team_stats.get("_aquametric", {}) if isinstance(team_stats, dict) else {}
    video = _video_reference(item)

    final_margin = abs(int(item.score_a or 0) - int(item.score_b or 0)) if item.score_a is not None and item.score_b is not None else None
    if final_margin is None:
        game_profile = "score incomplet"
    elif final_margin <= 2:
        game_profile = "match serré"
    elif final_margin >= 8:
        game_profile = "écart important"
    else:
        game_profile = "écart contrôlé"
    biggest = max(quarter_rows, key=lambda q: q["margin"]) if quarter_rows else None

    coverage_signals = {
        "score_final": item.score_a is not None and item.score_b is not None,
        "quarts": bool(quarter_rows),
        "joueuses": bool(player_rows),
        "buteuses_a": bool(scorer_a["rows"]),
        "buteuses_b": bool(scorer_b["rows"]),
        "stats_equipe": bool(team_stats and set(team_stats) != {"_aquametric"}),
        "replay": bool(video["embed"] or video["url"]),
        "source_officielle": bool(item.official_source_url),
    }
    coverage = round(100 * sum(1 for v in coverage_signals.values() if v) / len(coverage_signals))
    readiness = "ELITE PUBLIC" if coverage >= 80 else "STRONG" if coverage >= 60 else "PARTIAL" if coverage >= 35 else "SPARSE"

    coach_questions = [
        f"Pourquoi le Q{biggest['quarter']} produit-il la plus grande rupture ?" if biggest else "Quelle période produit réellement l'écart ?",
        f"Comment limiter la première source de scoring de {item.team_a} sans ouvrir une option plus dangereuse ?",
        f"Comment {item.team_b} protège-t-elle la possession suivante après un but ou une perte ?",
        "La répartition des buteuses reflète-t-elle une vraie variété de création ou seulement la finition ?",
        "Sur le replay, quelle erreur apparaît 2–3 secondes avant les buts importants ?",
    ]
    training = [
        {"title": "Scénario quart décisif", "detail": "Rejouer le quart de bascule avec score et temps réels ; noter décision, safety et qualité de possession."},
        {"title": "Défendre la route de but n°1", "detail": "Forcer l'attaque vers une option secondaire puis mesurer tir créé, perte et repli."},
        {"title": "Transition après événement", "detail": "Après but, tir ou perte : première action obligatoire = identification safety + axe + centre."},
    ]

    return {
        "item": item,
        "quarters": quarter_rows,
        "lead_changes": lead_changes,
        "biggest_quarter": biggest,
        "game_profile": game_profile,
        "scorers_a": scorer_a,
        "scorers_b": scorer_b,
        "history_a": history_a,
        "history_b": history_b,
        "history_a_rows": history_a_rows[:8],
        "history_b_rows": history_b_rows[:8],
        "habits": habits,
        "team_stats": {k:v for k,v in team_stats.items() if k != "_aquametric"} if isinstance(team_stats, dict) else {},
        "evidence_meta": evidence_meta,
        "video": video,
        "coverage": {"score": coverage, "readiness": readiness, "signals": coverage_signals},
        "coach_questions": coach_questions,
        "training": training,
    }
