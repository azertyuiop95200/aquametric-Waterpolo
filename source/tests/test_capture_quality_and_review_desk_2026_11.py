"""Regression: a YouTube anti-bot screen must not become water-polo data."""
import uuid

import cv2
import numpy as np
from fastapi.testclient import TestClient

from main import app
from services.capture_source_quality import _looks_blocked, capture_source_quality, capture_is_unverified
from services.quick_tag_analytics import reviewed_match_metrics
from services.source_match_facts import declared_match_facts


VIDEO = "https://www.youtube.com/watch?v=f_WzRHjybgU"


def _screens(tmp_path, *, moving=False):
    records=[]
    for i in range(8):
        image=np.full((250,500,3),(26,25,24),dtype=np.uint8)
        cv2.putText(image,"Sign in to confirm you're not a bot",(10,90),
                    cv2.FONT_HERSHEY_SIMPLEX,0.6,(245,245,245),2)
        if moving:
            cv2.rectangle(image,(10+i*45,120),(90+i*45,225),(242,95,30),-1)
        path=tmp_path/f"{i}.jpg"
        assert cv2.imwrite(str(path),image)
        records.append({"path":path,"wall_second":i*30,"index":i})
    return records


def test_recognize_known_youtube_verification_language():
    assert _looks_blocked("Sign in to confirm you're not a bot")
    assert _looks_blocked("Please verify you are human")
    assert not _looks_blocked("Water polo game 9 : 25 final score")


def test_static_youtube_challenge_is_blocked(tmp_path):
    records=_screens(tmp_path)
    found=capture_source_quality(tmp_path,{},records=records,
                                 ocr=lambda image:"Sign in to confirm you're not a bot")
    assert found["status"]=="blocked"
    assert found["ocr_blocker_detected"] is True
    assert capture_is_unverified(found)
    assert found["frames_checked"]==6


def test_static_unknown_content_is_not_marked_as_measured_game(tmp_path):
    found=capture_source_quality(tmp_path,{},records=_screens(tmp_path),ocr=lambda image:"")
    assert found["status"]=="static_unverified"
    assert capture_is_unverified(found)


def test_visual_movement_can_pass_source_gate_without_claiming_sport(tmp_path):
    found=capture_source_quality(tmp_path,{},records=_screens(tmp_path,moving=True),ocr=lambda image:"")
    assert found["status"]=="playable_candidate"
    assert not capture_is_unverified(found)


def test_title_result_is_separate_from_measured_actions():
    facts=declared_match_facts(VIDEO)
    assert facts["home_goals"]==9
    assert facts["away_goals"]==25
    assert facts["goal_difference_home"]==-16
    assert facts["claim_only"]
    assert declared_match_facts("https://www.youtube.com/watch?v=abcXYZ_1234") is None
    empty=reviewed_match_metrics([],VIDEO)
    assert empty["team"]["tagged_events"]==0
    assert empty["team"]["shot_conversion_pct"] is None
    assert empty["timeline"]==[]


def test_review_metric_math_does_not_invent_unrecorded_shots():
    rows=[
        {"confidence":"CONFIRMED","perspective":"for","event_type":"goal","second":100,
         "phase":"power_play","player_id":7,"player":"Joueuse 7"},
        {"confidence":"CONFIRMED","perspective":"for","event_type":"goal","second":200,
         "phase":"even_attack","player_id":7,"player":"Joueuse 7"},
        {"confidence":"CONFIRMED","perspective":"for","event_type":"shot_off_target","second":280,
         "phase":"even_attack","player_id":7,"player":"Joueuse 7"},
        {"confidence":"CONFIRMED","perspective":"against","event_type":"turnover","second":300,
         "phase":"counterattack","player_id":None,"player":""},
        {"confidence":"LOW","perspective":"for","event_type":"goal","second":400,
         "phase":"even_attack","player_id":7,"player":"Joueuse 7"},
    ]
    report=reviewed_match_metrics(rows,VIDEO)
    assert report["verified_count"]==4
    assert report["team"]["tagged_goals"]==2
    assert report["team"]["tagged_shots"]==3
    assert report["team"]["shot_conversion_pct"]==66.7
    assert report["opponent"]["tagged_turnovers"]==1
    assert report["phases"]["power_play"]["for"]["tagged_goals"]==1
    assert report["players"][0]["tagged_shots"]==3
    assert report["timeline"][0]["url"].endswith("t=100s")


def test_real_match_can_be_manually_tagged_from_its_report():
    with TestClient(app) as client:
        email=f"review-{uuid.uuid4().hex}@example.com"
        signup=client.post("/register",data={"email":email,"password":"Password123!"},follow_redirects=False)
        assert signup.status_code==303
        created=client.post("/analysis/url/create",
            data={"team_name":"Granville WP","opponent":"CN Marseille","category":"Women",
                  "competition":"Élite féminine","input_device":"desktop","video_url":VIDEO},
            follow_redirects=False)
        assert created.status_code==303
        match_id=int(created.headers["location"].split("/matches/")[1].split("/")[0])
        url=f"/matches/{match_id}/analysis/result"
        before=client.get(url)
        assert before.status_code==200, before.text[:300]
        assert 'id="annotation"' in before.text
        assert "Résultat annoncé par la source" in before.text
        assert "Les buts annoncés dans le titre YouTube ne sont pas additionnés" in before.text
        denied=client.post(f"/matches/{match_id}/events",
            data={"event_type":"goal","second":"124.5","perspective":"for",
                  "phase_tag":"power_play","return_to":"report"},
            follow_redirects=False)
        assert denied.status_code==400
        result=client.post(f"/matches/{match_id}/events",
            data={"event_type":"goal","second":"124.5","perspective":"for",
                  "phase_tag":"power_play","observed":"1","return_to":"report"},
            follow_redirects=False)
        assert result.status_code==303
        assert result.headers["location"]==url+"#annotation"
        rendered=client.get(url)
        assert rendered.status_code==200
        assert "1 action(s) confirmée(s)" in rendered.text
        assert "Conversion des tirs annotés" in rendered.text
        assert "124.5" in rendered.text or "02:04" in rendered.text
        portable=client.get(url.replace("/result","/report.html"))
        assert portable.status_code==200
        assert "Résultats" not in portable.text or "Buts observés" in portable.text
        assert "Buts observés" in portable.text
