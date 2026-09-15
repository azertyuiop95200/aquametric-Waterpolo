"""Transport fixtures are labelled synthetic; these do not certify model accuracy."""
import io
import json
import time
import uuid
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db import Base
from models import Club, Event, Match, Player, Team, User, VideoActionAnalysis
from services.video_action_schema import ActionObservation, EVENT_LABELS, SegmentObservation
from services.video_action_provider import VideoActionError
from services.video_action_runner import normalize_observations, run_video_actions, segment_plan
from services.video_action_report import action_report, automatic_player_history


def action(kind="goal", second=3, side="for", cap=4, **extra):
    return ActionObservation(second=second, event_type=kind, side=side, cap_number=cap, confidence=.86,
        evidence="Fixture synthétique : action visible au timestamp fourni.",
        identity_evidence=f"Fixture : bonnet {cap} visible.", team_evidence="Fixture : équipe identifiée par le bandeau.",
        **extra).model_dump()


def payload(actions=None):
    return {"scene": "water_polo", "actions": actions if actions is not None else [action()],
            "observability": [{"family": "shooting", "status": "limited", "reason": "Fixture synthétique."}],
            "summary": "Réponse simulée pour vérifier le transport et les calculs, sans valider un vrai match."}


@pytest.fixture
def db_match():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="fixture@example.test", password_hash="unused")
        db.add(user); db.flush()
        club = Club(name="Fixture club", owner_id=user.id)
        db.add(club); db.flush()
        team = Team(name="Fixture team", owner_id=user.id, club_id=club.id)
        db.add(team); db.flush()
        match = Match(owner_id=user.id, team_id=team.id, opponent="Fixture opponent")
        db.add(match); db.commit()
        yield db, match
    engine.dispose()


def save_run(db, match, actions, duration=120, source_path=""):
    plan, _ = segment_plan(duration)
    for segment in plan:
        segment["status"] = "complete"
        segment["result"] = normalize_observations(payload([a for a in actions if segment["start"] <= a["second"] < segment["end"]]), segment)
    run = VideoActionAnalysis(match_id=match.id, fingerprint=uuid.uuid4().hex, status="complete", model="synthetic-fixture",
        source_path=source_path, source_kind="upload", segments_json=json.dumps(plan), duration_seconds=duration,
        updated_at=time.time(), message="Fixture de test : transport, pas validation d’un match.")
    db.add(run); db.commit()
    return run


def test_mosaic_mapping_keeps_original_time_and_reports_missing_recording():
    plan, duration = segment_plan(10, {"source_start_second":100,"source_duration_seconds":260,"playback_rate":2,"parallel_segments":4})
    assert duration == 160
    assert [(p["start"],p["end"]) for p in plan] == [(100,120),(140,160),(180,200),(220,240)]
    assert sum(p["end"]-p["start"] for p in plan) == 80  # half the requested scope, not 100%
    normalized = normalize_observations(payload([action(second=3)]), plan[2])
    assert normalized["actions"][0]["second"] == 183


def test_schema_requires_evidence_and_rejects_unmeasured_physics():
    row = action()
    row.update(team_evidence="", identity_evidence="")
    parsed = ActionObservation.model_validate(row)
    assert parsed.side == "unknown" and parsed.cap_number is None
    with pytest.raises(ValueError):
        ActionObservation.model_validate({**row,"distance_m":350})
    with pytest.raises(ValueError):
        ActionObservation.model_validate({**row,"second":float("nan")})
    with pytest.raises(ValueError):
        ActionObservation.model_validate({**row,"event_type":"invented"})


def test_overlap_replay_and_invalid_timestamps_do_not_inflate_counts():
    plan, _ = segment_plan(120)
    observed = normalize_observations(payload([action(second=1),action(second=2),action(second=3,is_replay=True)]), plan[1])
    assert len(observed["actions"]) == 1 and observed["actions"][0]["second"] == 60
    assert observed["ignored"] == {"replays":1,"overlap":1,"duplicates":0}
    with pytest.raises(VideoActionError, match="horodatage"):
        normalize_observations(payload([action(second=600)]), plan[0])
    with pytest.raises(VideoActionError):
        normalize_observations({**payload(),"scene":"unreadable"}, plan[0])


def test_provider_sends_actual_video_stateless_with_validated_schema(monkeypatch, tmp_path):
    import httpx
    import services.video_action_provider as provider
    monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    monkeypatch.setenv("GEMINI_API_KEY","fixture-secret-not-a-real-key")
    path = tmp_path / "fixture.mp4"; path.write_bytes(b"synthetic-fixture-bytes")
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"status":"completed", "steps":[
            {"type":"thought", "content":[{"type":"text","text":"not-json"}]},
            {"type":"model_output", "content":[{"type":"text","text":json.dumps(payload())}]}]})
    original = httpx.Client
    monkeypatch.setattr(provider.httpx,"Client",lambda **kw: original(transport=httpx.MockTransport(handler), trust_env=False, **kw))
    result = provider.analyze_video_segment(path,team="Fixture team",opponent="Fixture opponent")
    assert result["actions"][0]["event_type"] == "goal"
    body = json.loads(requests[0].content)
    assert not body["store"] and body["input"][0]["processing"]["fps"] == 4
    assert body["input"][0]["data"] and body["response_format"]["schema"]
    assert "fixture-secret" not in json.dumps(body)
    assert requests[0].url.host == "generativelanguage.googleapis.com"


@pytest.mark.parametrize("status,expected", [(401,"credentials"),(403,"credentials"),(429,"quota"),(502,"provider")])
def test_provider_failures_are_clear_and_never_echo_secret(monkeypatch, tmp_path, status, expected):
    import httpx
    import services.video_action_provider as provider
    monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1"); monkeypatch.setenv("GEMINI_API_KEY","secret")
    path=tmp_path/"fixture.mp4";path.write_bytes(b"fixture")
    original=httpx.Client
    monkeypatch.setattr(provider.httpx,"Client",lambda **kw: original(trust_env=False, transport=httpx.MockTransport(
        lambda _: httpx.Response(status,text="secret raw provider exception")), **kw))
    with pytest.raises(VideoActionError) as error:
        provider.analyze_video_segment(path,team="a",opponent="b")
    assert error.value.code == expected and "secret" not in str(error.value)


def test_unconfigured_is_explicit_and_does_not_process_or_claim_measurements(db_match, tmp_path, monkeypatch):
    import services.video_action_runner as runner
    db, match = db_match
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AQUAMETRIC_VIDEO_ACTIONS", raising=False)
    monkeypatch.setattr(runner,"ffprobe_video", lambda _: pytest.fail("No work without configured provider"))
    run=run_video_actions(db,match,tmp_path/"source.mp4")
    report=action_report(db,match)
    assert run.status == "not_configured" and not report["available"]
    assert report["team"]["basic"]["goals"] is None and report["coverage_percent"] == 0


def test_runner_resumes_only_failed_segments_and_preserves_checkpoints(db_match, tmp_path, monkeypatch):
    import services.video_action_runner as runner
    db, match = db_match
    monkeypatch.setenv("GEMINI_API_KEY","fixture");monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    source=tmp_path/"video.mp4";source.write_bytes(b"fixture")
    monkeypatch.setattr(runner,"ffprobe_video",lambda _: {"ok":True,"duration":125})
    monkeypatch.setattr(runner,"encode_segment",lambda src,dst,s,timeout: dst.write_text(str(s["index"])))
    calls=[]
    def infer(path,**kw):
        index=int(path.read_text()); calls.append(index)
        if index == 1 and calls.count(1) == 1:
            raise VideoActionError("timeout","Fixture interruption")
        return payload([action(second=3,cap=index+1)])
    monkeypatch.setattr(runner,"analyze_video_segment",infer)
    first=run_video_actions(db,match,source)
    assert first.status == "partial" and len(action_report(db,match)["events"]) == 2
    second=run_video_actions(db,match,source)
    assert second.id == first.id and second.status == "complete"
    assert calls.count(0) == 1 and calls.count(2) == 1 and calls.count(1) == 2
    assert len(action_report(db,match)["events"]) == 3
    run_video_actions(db,match,source)
    assert len(calls) == 4
    assert not db.scalars(select(Event)).all()  # automatic results never masquerade as verified actions


def test_native_capture_actions_recover_missing_webm_duration(db_match, tmp_path, monkeypatch):
    import subprocess
    import services.browser_capture_media as media
    import services.video_action_runner as runner
    from services.media import ffmpeg_executable
    db,match=db_match
    source=tmp_path/"native-mediarecorder.webm"
    subprocess.run([ffmpeg_executable(),"-hide_banner","-loglevel","error","-y","-f","lavfi","-i",
        "testsrc2=size=320x180:rate=16:duration=4","-c:v","libvpx-vp9","-b:v","400k","-an","-f","webm","-live","1",str(source)],check=True,timeout=40)
    monkeypatch.setenv("GEMINI_API_KEY","fixture");monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    monkeypatch.setattr(media.shutil,"which",lambda _:None)
    monkeypatch.setattr(runner,"analyze_video_segment",lambda *args,**kwargs:payload())
    run=run_video_actions(db,match,source,capture_state={"source_start_second":0,"source_duration_seconds":4,"playback_rate":1,"parallel_segments":1})
    assert run.status == "complete",run.message
    report=action_report(db,match)
    assert report["coverage_percent"] >= 95 and report["team"]["basic"]["goals"] == 1
    assert Path(run.source_path).is_file()


def test_all_action_types_appear_in_report_with_separate_teams_caps_and_no_false_identity(db_match):
    db,match=db_match
    actions=[action(kind,second=index+1) for index,kind in enumerate(EVENT_LABELS)]
    actions += [action("goal",second=40,side="against"), action("save",second=41,side="unknown",cap=None)]
    save_run(db,match,actions,duration=55)
    report=action_report(db,match)
    assert report["team"]["event_counts"] == {kind:1 for kind in EVENT_LABELS}
    assert report["team"]["basic"]["shots"] == 4 and report["opponent"]["basic"]["goals"] == 1
    assert report["unassigned"]["basic"]["saves"] == 1
    assert len(report["players"]) == 3
    assert all(metric["value"] is None for metric in report["physical"])
    person=Player(team_id=match.team_id,name="Person test",cap_number=4);db.add(person);db.commit()
    assert len(automatic_player_history(db,person,match.owner_id)) == 1
    assert not automatic_player_history(db,person,match.owner_id+1)


def test_duplicate_pass_goal_and_conflicting_outcomes_are_not_double_counted(db_match):
    db,match=db_match
    save_run(db,match,[action("goal"),action("shot_on_target"),action("assist",second=8),action("pass_complete",second=8),
        action("shot_off_target",second=14),action("goal",second=14)],duration=30)
    report=action_report(db,match)
    assert report["team"]["basic"]["shots"] == 1 and report["team"]["basic"]["passes_completed"] == 1
    assert report["excluded_count"] == 2


def test_possession_times_come_only_from_observed_boundaries(db_match):
    db,match=db_match
    save_run(db,match,[action("possession_start",second=1),action("pass_complete",second=3),action("goal",second=7),action("possession_end",second=8)],duration=30)
    observed=action_report(db,match)["team"]["observed_possessions"]
    assert observed["count"] == 1
    assert observed["intervals"][0]["video_duration_seconds"] == 7
    assert observed["intervals"][0]["first_shot_after_seconds"] == 6


def test_upload_start_responds_with_queued_job_before_processing(tmp_path, monkeypatch):
    from fastapi import BackgroundTasks, Request
    from fastapi.testclient import TestClient
    from main import app
    from db import SessionLocal
    from models import AnalysisJob
    from analysis_product_routes import start_real_analysis, UPLOAD_DIR
    with TestClient(app) as client:
        client.post("/register",data={"name":"Queued fixture","email":f"queue-{uuid.uuid4().hex}@example.test","password":"fixture-password123"})
        response=client.post("/analysis/url/create",data={"team_name":"Queued team","opponent":"Opponent","video_url":"https://example.test/match.mp4"},follow_redirects=False)
        mid=int(response.headers["location"].split("/matches/")[1].split("/")[0])
        with SessionLocal() as db:
            match=db.get(Match,mid)
            source=UPLOAD_DIR/f"fixture-{uuid.uuid4().hex}.mp4";source.parent.mkdir(parents=True,exist_ok=True);source.write_bytes(b"fixture")
            match.video_source="upload";match.video_path=source.name;db.commit()
            request=Request({"type":"http","session":{"user_id":match.owner_id}})
            tasks=BackgroundTasks()
            result=start_real_analysis(mid,request,tasks,include_audio="0",db=db)
            assert result.status_code == 303
            job=db.scalar(select(AnalysisJob).where(AnalysisJob.match_id==mid,AnalysisJob.stage=="video_workflow"))
            assert job and job.status == "queued"
            assert not db.scalars(select(VideoActionAnalysis).where(VideoActionAnalysis.match_id==mid)).all()
            progress=client.get(f"/matches/{mid}/analysis/progress")
            assert progress.json()["active"] and progress.json()["workflow_active"]
            # A second click must not enqueue the same upload twice.
            start_real_analysis(mid,request,BackgroundTasks(),include_audio="0",db=db)
            assert len(db.scalars(select(AnalysisJob).where(AnalysisJob.match_id==mid,AnalysisJob.stage=="video_workflow")).all()) == 1


def test_report_exports_player_page_actual_clip_and_account_isolation(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from db import SessionLocal
    from services.media import _run_ffmpeg
    from services.browser_capture_media import ffprobe_video
    import services.video_action_runner as runner
    monkeypatch.setenv("GEMINI_API_KEY","fixture");monkeypatch.setenv("AQUAMETRIC_VIDEO_ACTIONS","1")
    source=tmp_path/"synthetic-not-a-match.mp4"
    _run_ffmpeg(["-f","lavfi","-i","color=c=blue:s=320x180:r=16:d=6","-an","-c:v","libx264","-pix_fmt","yuv420p",str(source)])
    monkeypatch.setattr(runner,"analyze_video_segment",lambda *a,**kw: payload([action("goal",zone="centre",cage_zone="top_left")]))
    with TestClient(app) as client:
        client.post("/register",data={"name":"Video fixture","email":f"video-{uuid.uuid4().hex}@example.test","password":"fixture-password123"})
        response=client.post("/analysis/url/create",data={"team_name":"Video fixture team","opponent":"Video fixture opponent","video_url":"https://example.test/match.mp4"},follow_redirects=False)
        mid=int(response.headers["location"].split("/matches/")[1].split("/")[0])
        with SessionLocal() as db:
            match=db.get(Match,mid)
            player=Player(team_id=match.team_id,name="Video fixture player",cap_number=4);db.add(player);db.commit();pid=player.id
            run=run_video_actions(db,match,source)
            assert run.status == "complete"
            result=action_report(db,match);clip_url=result["events"][0]["clip_url"]
        for url in [f"/matches/{mid}/analysis/result",f"/matches/{mid}/analysis/report.html",f"/players/{pid}"]:
            page=client.get(url)
            assert page.status_code == 200,page.text
            assert ("Analyse automatique des actions" if "/players/" not in url else "Détections vidéo associées au bonnet") in page.text
        clip=client.get(clip_url)
        assert clip.status_code == 200
        downloaded=tmp_path/"download.mp4";downloaded.write_bytes(clip.content)
        assert ffprobe_video(downloaded)["ok"]
        assert client.get(clip_url).content == clip.content  # cached, not regenerated
        archive=client.get(f"/matches/{mid}/analysis/export.zip")
        with zipfile.ZipFile(io.BytesIO(archive.content)) as pack:
            raw=json.loads(pack.read(next(n for n in pack.namelist() if n.endswith("/analysis.json"))))
            assert raw["video_actions"]["team"]["basic"]["goals"] == 1
            assert raw["statistics"]["team"]["basic"]["goals"] is None
            assert raw["video_actions"]["players"][0]["cap_number"] == 4
            csv=pack.read(next(n for n in pack.namelist() if n.endswith("/automatic_player_measurements.csv"))).decode()
            assert "for,4,automatic_detections,basic.goals,1" in csv
            assert any(n.endswith(".mp4") for n in pack.namelist())
        client.post("/register",data={"name":"Other","email":f"other-{uuid.uuid4().hex}@example.test","password":"fixture-password123"})
        assert client.get(clip_url).status_code == 404
        assert client.get(f"/matches/{mid}/analysis/actions/status").status_code == 404
        assert client.post(f"/matches/{mid}/analysis/actions/start").status_code == 404
