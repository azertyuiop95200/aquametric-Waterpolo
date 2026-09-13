from types import SimpleNamespace as NS
from collections import Counter

from services.measurement_report import match_statistics, player_statistics, observed_report, flatten_measurements
from services.ratings import build_detailed_evaluation
from services.ultimate_analytics import note_tags


def event(kind, player_id=1, side="for", confidence="CONFIRMED", note="", match_id=1, second=10):
    return NS(id=second, event_type=kind, player_id=player_id, match_id=match_id,
        player=NS(id=player_id, name="Même nom", cap_number=3) if player_id else None,
        second=second, confidence=confidence, note=note,
        context_meta=NS(perspective=side, phase_tag="power_play", quality_tag=""))


def test_every_recorded_event_and_tag_survives_match_and_player_reports():
    types = ["goal", "shot_on_target", "shot_off_target", "shot_blocked", "assist", "key_pass",
        "touch", "centre_touch", "duel_won", "duel_lost", "pass_complete", "block", "interception",
        "recovery", "save", "bad_pass", "turnover", "foul", "exclusion", "exclusion_committed",
        "exclusion_earned", "penalty_earned", "penalty_committed", "fast_recovery", "late_recovery", "action_created", "custom_measured_action"]
    rows = [event(kind, second=index, note="period=1 zone=centre possession=1 sprint_5m_s=2.1 cage_zone=top_left") for index, kind in enumerate(types)]
    result = match_statistics(NS(events=rows))
    assert result["team"]["event_counts"] == dict(Counter(types))
    basic = result["team"]["basic"]
    assert basic["shots"] == 4
    assert basic["assists"] == 1
    assert basic["touches"] == 2
    assert basic["exclusions_committed"] == 2
    assert result["players"][0]["report"]["basic"] == result["team"]["basic"]
    assert result["players"][0]["report"]["evaluation"]["sample_size"] == len(rows)
    assert result["team"]["physical_measurements"]["sprint_5m_s"]["mean"] == 2.1
    assert result["team"]["tag_breakdowns"]["cage_zone"] == {"top_left": len(rows)}
    paths = {r["metric"] for r in flatten_measurements(result["team"])}
    assert "event_counts.custom_measured_action" in paths
    assert "physical_measurements.sprint_5m_s.mean" in paths


def test_unconfirmed_events_never_inflate_stats_or_rating_and_names_do_not_merge():
    rows = [event("goal"), event("goal", confidence="LOW"), event("save", player_id=2, side="against"), event("touch", player_id=None)]
    result = match_statistics(NS(events=rows))
    assert result["team"]["basic"]["goals"] == 1
    assert result["opponent"]["basic"]["saves"] == 1
    assert result["excluded_unverified_events"] == 1
    assert len(result["players"]) == 3
    assert build_detailed_evaluation([rows[1]])["rated"] is False


def test_personal_possessions_are_scoped_to_match_and_period():
    rows = [event("goal", match_id=1, note="possession=1 period=1"),
            event("pass_complete", match_id=2, note="possession=1 period=1"),
            event("turnover", match_id=2, note="possession=1 period=2")]
    personal = player_statistics(rows)
    assert personal["match_count"] == 2
    assert personal["aggregate"]["possessions"]["possessions"] == 3
    assert personal["aggregate"]["basic"]["shots"] == 1


def test_empty_and_invalid_measurements_stay_unknown():
    assert observed_report([])["basic"]["goals"] is None
    tags = note_tags(event("goal", note="shot_speed_kmh=nan distance_m=-3 release_time_s=inf"))
    assert not tags


def test_public_stats_do_not_merge_homonyms_duplicates_or_missing_values():
    from services.public_player_statistics import public_player_rows
    rows = [NS(team_name="A", player_name="Même nom", library_match_id=1, goals=2),
            NS(team_name="A", player_name="Même nom", library_match_id=1, goals=2),
            NS(team_name="B", player_name="Même nom", library_match_id=1, goals=5)]
    a, b = public_player_rows(rows, [], {})
    assert a["goals"] == 2 and b["goals"] == 5
    assert a["matches"] == 1 and a["metric_coverage"]["goals"] == 1
    assert a["saves"] is None and a["ambiguous_name"]
    rows.append(NS(team_name="A", player_name="Même nom", library_match_id=1, goals=3))
    a, b = public_player_rows(rows, [], {})
    assert a["goals"] is None and a["conflicts"] == 1


def test_saved_match_player_page_and_zip_share_all_measurements():
    import uuid, json, zipfile
    from io import BytesIO
    from fastapi.testclient import TestClient
    from main import app
    from db import SessionLocal
    from models import Match, Player, Event
    with TestClient(app) as client:
        client.post("/register", data={"name":"Stats", "email":f"stats-{uuid.uuid4().hex}@example.com", "password":"test-password123"})
        response = client.post("/analysis/url/create", data={"team_name":"Stats team", "opponent":"Opponent", "video_url":"https://youtu.be/Guo_UU282pI"}, follow_redirects=False)
        mid = int(response.headers["location"].split("/matches/")[1].split("/")[0])
        with SessionLocal() as db:
            match = db.get(Match, mid)
            person = Player(team_id=match.team_id, name="Joueuse test complète", cap_number=4)
            db.add(person); db.flush(); pid = person.id
            db.add_all([Event(match_id=mid, player_id=pid, event_type="assist", confidence="CONFIRMED", note="period=1 pass_type=centre_entry"),
                Event(match_id=mid, player_id=pid, event_type="goal", confidence="VERIFIED", note="period=1 zone=centre shot_speed_kmh=72"),
                Event(match_id=mid, player_id=pid, event_type="goal", confidence="LOW")])
            db.commit()
        for url in [f"/matches/{mid}/analysis/result", f"/matches/{mid}/analysis/report.html", f"/players/{pid}"]:
            page = client.get(url)
            assert page.status_code == 200
            assert "Statistiques" in page.text and "Passes décisives" in page.text
            assert "72" in page.text
        archive_response = client.get(f"/matches/{mid}/analysis/export.zip")
        assert archive_response.status_code == 200
        with zipfile.ZipFile(BytesIO(archive_response.content)) as archive:
            def read(suffix):
                return archive.read(next(n for n in archive.namelist() if n.endswith(suffix))).decode()
            snapshot = json.loads(read("/analysis.json"))
            assert snapshot["statistics"]["team"]["basic"]["goals"] == 1
            assert snapshot["ultimate"]["team"]["basic"]["goals"] == 1
            assert snapshot["statistics"]["players"][0]["player_id"] == pid
            assert "basic.assists,1" in read("/all_player_measurements.csv")
            assert "physical_measurements.shot_speed_kmh.mean,72" in read("/all_match_measurements.csv")
            assert "Statistiques individuelles du match" in read("/report.html")
