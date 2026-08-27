import os
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse


class AquaMetricSecurityMiddleware(BaseHTTPMiddleware):
    """Small dependency-free web hardening layer for the demo/production app.

    - security headers / CSP
    - same-origin validation when browsers send Origin on unsafe requests
    - lightweight in-memory throttling for authentication/demo-login endpoints

    It intentionally does not pretend to be a WAF; production deployments can add
    Cloudflare/Render edge controls later without changing application logic.
    """

    def __init__(self, app):
        super().__init__(app)
        self.attempts = defaultdict(deque)
        self.window_seconds = int(os.getenv("AUTH_RATE_WINDOW_SECONDS", "300"))
        self.max_attempts = int(os.getenv("AUTH_RATE_MAX", "20"))

    def _client_key(self, request: Request):
        host = request.client.host if request.client else "unknown"
        return f"{host}:{request.url.path}"

    def _rate_limited(self, request: Request):
        if request.url.path not in {"/login", "/register", "/demo-login"}:
            return False
        key = self._client_key(request)
        now = time.monotonic()
        q = self.attempts[key]
        cutoff = now - self.window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= self.max_attempts:
            return True
        q.append(now)
        return False

    @staticmethod
    def _origin_is_valid(request: Request):
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return True
        origin = request.headers.get("origin")
        if not origin:
            # Non-browser clients/tests frequently omit Origin. Session cookies are
            # SameSite=Lax, so absence alone is not treated as hostile.
            return True
        try:
            parsed = urlparse(origin)
            origin_host = parsed.netloc.lower()
            request_host = request.headers.get("host", "").lower()
            return bool(origin_host and request_host and origin_host == request_host)
        except Exception:
            return False

    async def dispatch(self, request: Request, call_next):
        if self._rate_limited(request):
            return PlainTextResponse("Too many authentication attempts. Try again later.", status_code=429)
        if not self._origin_is_valid(request):
            return PlainTextResponse("Cross-site request blocked.", status_code=403)

        response = await call_next(request)
        csp = (
            "default-src 'self'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'self'; "
            "object-src 'none'; "
            "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https:; media-src 'self' blob: https:; "
            "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com; "
            "connect-src 'self'"
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path in {"/login", "/register"}:
            response.headers.setdefault("Cache-Control", "no-store")
        return response


def install_security(app):
    app.add_middleware(AquaMetricSecurityMiddleware)
