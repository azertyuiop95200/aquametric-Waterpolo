"""Google OpenID Connect sign-in to the SAME AquaMetric account, not a new
password or a temporary guest workspace. Browser consent remains with Google.
"""
from __future__ import annotations

import os
import secrets
from urllib.parse import urlparse

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import hash_password, verify_password
from db import get_db
from models import GoogleIdentity, User

router = APIRouter()
_oauth = OAuth()
_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
_client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
_redirect = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
_enabled = bool(_client_id and _client_secret and _redirect)

if _enabled:
    parsed = urlparse(_redirect)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path != "/auth/google/callback":
        raise RuntimeError("GOOGLE_OAUTH_REDIRECT_URI must be HTTPS with path /auth/google/callback")
    _oauth.register(
        name="google",
        client_id=_client_id,
        client_secret=_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope":"openid email profile"},
    )


def google_ready() -> bool:
    return _enabled


def safe_next(value: str) -> str:
    # Never accept arbitrary redirections after OAuth / password linking.
    return value if value in {"/dashboard", "/matches/new", "/analysis-history", "/analysis-library"} else "/matches/new"


def verified_identity(userinfo: dict) -> tuple[str, str, str, bool]:
    """Only data from Authlib's cryptographically verified ID token qualifies."""
    if not isinstance(userinfo,dict):
        raise HTTPException(400,"Réponse Google invalide.")
    subject=str(userinfo.get("sub","")).strip()
    email=str(userinfo.get("email","")).strip().lower()
    issuer=str(userinfo.get("iss","")).strip()
    audience=userinfo.get("aud")
    confirmed=userinfo.get("email_verified") is True
    if (not 1<=len(subject)<=255 or not email or len(email)>255 or "@" not in email or
        issuer not in {"https://accounts.google.com", "accounts.google.com"} or
        audience!=_client_id or not confirmed):
        raise HTTPException(403,"L'identité Google n'a pas pu être vérifiée.")
    authoritative = email.endswith("@gmail.com") or email.endswith("@googlemail.com")
    # Workspace domains are not automatically linked to old password accounts:
    # hosted_domain can be correct, but requires a deliberate linking decision.
    return subject,email,str(userinfo.get("name") or "")[:120],authoritative


def finish_google_signin(request:Request, db:Session, userinfo:dict):
    subject,email,name,authoritative = verified_identity(userinfo)
    identity = db.scalar(select(GoogleIdentity).where(GoogleIdentity.sub==subject))
    if identity:
        user=db.get(User,identity.user_id)
        if not user:
            raise HTTPException(409,"Compte Google associé introuvable.")
    else:
        user=db.scalar(select(User).where(func.lower(User.email)==email))
        if user and not authoritative:
            # Third-party emails with email_verified are not necessarily still
            # controlled by Google. Ask for the old AquaMetric password once.
            request.session["google_pending_link"]={"sub":subject,"email":email,"name":name}
            return RedirectResponse("/auth/google/link",status_code=303)
        if not user:
            user=User(email=email,password_hash=hash_password(secrets.token_urlsafe(40)),
                      name=name,country="")
            db.add(user)
            db.flush()
        # Reject linking a second unrelated Google identity to one account.
        existing=db.scalar(select(GoogleIdentity).where(GoogleIdentity.user_id==user.id))
        if existing and existing.sub!=subject:
            raise HTTPException(409,"Ce compte AquaMetric est déjà lié à un autre compte Google.")
        db.add(GoogleIdentity(sub=subject,user_id=user.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409,"Compte Google modifié simultanément. Réessaie.") from None
    destination=safe_next(request.session.get("google_login_next","/matches/new"))
    request.session.clear()
    request.session["user_id"]=user.id
    return RedirectResponse(destination,status_code=303)


@router.get("/auth/google")
async def google_login(request:Request,next:str="/matches/new"):
    if not _enabled:
        raise HTTPException(503,"Connexion Google non configurée sur ce serveur.")
    request.session["google_login_next"]=safe_next(next)
    # Authlib stores the CSRF state and nonce in the existing signed session
    # and validates the token and issuer using Google's OIDC discovery/JWKS.
    return await _oauth.google.authorize_redirect(
        request,_redirect,prompt="select_account"
    )


@router.get("/auth/google/callback")
async def google_callback(request:Request,db:Session=Depends(get_db)):
    if not _enabled:
        raise HTTPException(503,"Connexion Google non configurée.")
    try:
        token=await _oauth.google.authorize_access_token(request)
        userinfo=token.get("userinfo")
    except Exception:
        # Never disclose tokens, access codes or provider response in a page.
        return RedirectResponse("/login?google_error=1",status_code=303)
    return finish_google_signin(request,db,userinfo)


@router.get("/auth/google/link",response_class=HTMLResponse)
def google_link_page(request:Request):
    pending=request.session.get("google_pending_link")
    if not pending:
        return RedirectResponse("/login",status_code=303)
    from main import render
    return render(request,"google_link.html",email=pending["email"])


@router.post("/auth/google/link")
def google_link_password(request:Request,password:str=Form(...),
                         db:Session=Depends(get_db)):
    pending=request.session.get("google_pending_link")
    if not pending:
        raise HTTPException(403,"Aucune liaison Google en cours.")
    email=pending.get("email","")
    user=db.scalar(select(User).where(func.lower(User.email)==email))
    if not user or not verify_password(password,user.password_hash):
        from main import render
        return render(request,"google_link.html",email=email,
                      error="Mot de passe AquaMetric incorrect.",status_code=403)
    subject=pending["sub"]
    if db.scalar(select(GoogleIdentity).where(GoogleIdentity.user_id==user.id)):
        raise HTTPException(409,"Ce compte est déjà lié à Google.")
    if db.scalar(select(GoogleIdentity).where(GoogleIdentity.sub==subject)):
        raise HTTPException(409,"Identité Google déjà associée.")
    db.add(GoogleIdentity(sub=subject,user_id=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"Liaison déjà effectuée.") from None
    destination=safe_next(request.session.get("google_login_next","/matches/new"))
    request.session.clear()
    request.session["user_id"]=user.id
    return RedirectResponse(destination,status_code=303)
