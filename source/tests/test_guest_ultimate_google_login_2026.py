"""AquaMetric Google SSO account recovery + private bounded Guest Ultimate."""
import uuid
from fastapi.testclient import TestClient
import pytest

from main import app
import main
import google_oauth_routes as google
from db import SessionLocal
from models import User, GoogleIdentity, Match


def create_password_account(client, email):
    resp=client.post("/register",data={"email":email,"password":"ExistingPassword123!"},
                     follow_redirects=False)
    assert resp.status_code==303,resp.text[:300]


def google_claim(email,sub):
    return {"iss":"https://accounts.google.com",
            "aud":"test-google-client-id",
            "sub":sub,"email":email,"email_verified":True,"name":"AquaMetric Verified"}


def test_google_sso_preserves_original_gmail_account_and_matches(monkeypatch):
    monkeypatch.setattr(google,"_client_id","test-google-client-id")
    email=f"former-{uuid.uuid4().hex}@gmail.com"
    sub="google-sub-"+uuid.uuid4().hex
    with TestClient(app) as coach:
        create_password_account(coach,email)
        match=coach.post("/analysis/url/create",data={
            "team_name":"Original Owner","opponent":"Opponent",
            "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU",
            "input_device":"phone"},follow_redirects=False)
        assert match.status_code==303
        match_id=int(match.headers["location"].split("/matches/")[1].split("/")[0])
        coach.post("/logout",follow_redirects=False)
        with SessionLocal() as db:
            existing_id=db.query(User).filter(User.email==email).first().id
            coach.get("/")
            response=google.finish_google_signin(coach,db,google_claim(email,sub)) if False else None
        # Exercise signed session, not only a mocked raw profile.
        monkeypatch.setattr(google,"_enabled",True)
        class OAuthStub:
            async def authorize_access_token(self,request):
                return {"userinfo":google_claim(email,sub)}
        monkeypatch.setattr(google._oauth,"google",OAuthStub(),raising=False)
        callback=coach.get("/auth/google/callback",follow_redirects=False)
        assert callback.status_code==303,callback.text
        with SessionLocal() as db:
            identity=db.query(GoogleIdentity).filter(GoogleIdentity.sub==sub).one()
            assert identity.user_id==existing_id
            assert db.query(User).filter(User.email==email).count()==1
        assert coach.get(f"/matches/{match_id}/analysis/result").status_code==200
        # A second sign in finds stable Google subject, not a duplicate account.
        coach.post("/logout",follow_redirects=False)
        second=coach.get("/auth/google/callback",follow_redirects=False)
        assert second.status_code==303
        assert coach.get(f"/matches/{match_id}/analysis/result").status_code==200


def test_google_third_party_mail_requires_original_password(monkeypatch):
    monkeypatch.setattr(google,"_client_id","test-google-client-id")
    monkeypatch.setattr(google,"_enabled",True)
    email=f"coach-{uuid.uuid4().hex}@example.org"
    sub="thirdparty-"+uuid.uuid4().hex
    with TestClient(app) as coach:
        create_password_account(coach,email)
        coach.post("/logout",follow_redirects=False)
        class OAuthStub:
            async def authorize_access_token(self,request):
                return {"userinfo":google_claim(email,sub)}
        monkeypatch.setattr(google._oauth,"google",OAuthStub(),raising=False)
        response=coach.get("/auth/google/callback",follow_redirects=False)
        assert response.status_code==303
        assert response.headers["location"]=="/auth/google/link"
        with SessionLocal() as db:
            assert db.query(GoogleIdentity).filter(GoogleIdentity.sub==sub).count()==0
        page=coach.get("/auth/google/link")
        assert page.status_code==200
        assert "Associer" in page.text
        incorrect=coach.post("/auth/google/link",data={"password":"not the correct one"},follow_redirects=False)
        assert incorrect.status_code==403
        linked=coach.post("/auth/google/link",data={"password":"ExistingPassword123!"},follow_redirects=False)
        assert linked.status_code==303
        with SessionLocal() as db:
            assert db.query(GoogleIdentity).filter(GoogleIdentity.sub==sub).count()==1


def test_google_rejects_unverified_email_or_wrong_issuer_and_redirects(monkeypatch):
    monkeypatch.setattr(google,"_client_id","test-google-client-id")
    with TestClient(app) as client:
        with SessionLocal() as db:
            for field,value in [("aud","attacker-client"),("iss","https://evil.example"),
                                ("email_verified",False),("sub","")]:
                profile=google_claim("test@gmail.com","google-safe-sub")
                profile[field]=value
                with pytest.raises(Exception):
                    google.finish_google_signin(client,db,profile)
        assert google.safe_next("https://evil.example/") == "/matches/new"
        assert google.safe_next("//evil.example/") == "/matches/new"
        assert google.safe_next("/analysis-history") == "/analysis-history"


def test_guest_ultimate_without_password_isolated_with_real_report(monkeypatch):
    monkeypatch.setattr(main,"GUEST_ULTIMATE_ENABLED",True)
    with TestClient(app) as visitor, TestClient(app) as stranger:
        landing=visitor.get("/guest")
        assert landing.status_code==200
        assert 'id="guestUltimateLaunch"' in landing.text
        entry=visitor.get("/guest/ultimate",follow_redirects=False)
        assert entry.status_code==303
        assert entry.headers["location"]=="/matches/new"
        screen=visitor.get("/matches/new")
        assert screen.status_code==200
        assert 'id="quickYoutubeAnalysis"' in screen.text
        match=visitor.post("/analysis/url/create",data={
            "team_name":"Guest Coach","opponent":"Guest Opponent",
            "input_device":"desktop",
            "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU",
            "youtube_duration_minutes":"2"},follow_redirects=False)
        assert match.status_code==303,match.text
        mid=int(match.headers["location"].split("/matches/")[1].split("/")[0])
        report=visitor.get(f"/matches/{mid}/analysis/result")
        assert report.status_code==200
        assert 'id="liveAutomaticStats"' in report.text
        assert 'id="spatialDashboard"' in report.text
        assert 'id="quickTagMatch"' in report.text
        assert 'En invité' in report.text
        assert visitor.get(f"/matches/{mid}/analysis/actions/live").json()["counted_events"]==0
        assert visitor.post(f"/matches/{mid}/analysis/youtube/direct",
            data={"duration_minutes":"2"},follow_redirects=False).status_code==403
        assert visitor.post(f"/matches/{mid}/analysis/actions/start",follow_redirects=False).status_code==403
        assert visitor.post(f"/matches/{mid}/analysis/browser-capture/session",follow_redirects=False).status_code==403
        stranger.get("/guest/ultimate",follow_redirects=False)
        assert stranger.get(f"/matches/{mid}/analysis/result").status_code==404


def test_guest_ultimate_enforces_three_matches_and_30mb_limit(monkeypatch):
    monkeypatch.setattr(main,"GUEST_ULTIMATE_ENABLED",True)
    with TestClient(app) as visitor:
        visitor.get("/guest/ultimate",follow_redirects=False)
        for n in range(3):
            response=visitor.post("/analysis/url/create",data={
                "team_name":"Demo A","opponent":"Demo B",
                "input_device":"phone",
                "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU"},follow_redirects=False)
            assert response.status_code==303
        fourth=visitor.post("/analysis/url/create",data={
            "team_name":"Demo A","opponent":"Demo B",
            "input_device":"phone",
            "video_url":"https://www.youtube.com/watch?v=f_WzRHjybgU"},follow_redirects=False)
        assert fourth.status_code==429
    with TestClient(app) as other:
        other.get("/guest/ultimate",follow_redirects=False)
        video=other.post("/matches",data={"team_name":"Guest MP4","opponent":"B",
            "return_to_report":"1"},files={"video_file":("small.mp4",b"x"*1000,"video/mp4")},
            follow_redirects=False)
        assert video.status_code==303
        assert video.headers["location"].endswith("/analysis/result")
        # Exceed the per-guest cap with streaming chunks; must return 413.
        huge=other.post("/matches",data={"team_name":"Guest MP4","opponent":"B",
            "return_to_report":"1"},files={"video_file":("huge.mp4",b"x"*(31*1024*1024),"video/mp4")},
            follow_redirects=False)
        assert huge.status_code==413
