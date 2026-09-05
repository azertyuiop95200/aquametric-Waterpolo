import os
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse


class AquaMetricSecurityMiddleware(BaseHTTPMiddleware):
    """Dependency-light hardening for AquaMetric web deployments.

    Authentication throttling records failed attempts only. Successful logins and
    registrations do not consume the quota, which protects real users and keeps
    automated product tests representative of normal usage.
    """

    AUTH_PATHS = {"/login", "/register", "/demo-login"}

    def __init__(self, app):
        super().__init__(app)
        self.failures = defaultdict(deque)
        self.window_seconds = int(os.getenv("AUTH_RATE_WINDOW_SECONDS", "300"))
        self.max_failures = int(os.getenv("AUTH_RATE_MAX_FAILURES", os.getenv("AUTH_RATE_MAX", "12")))

    def _client_key(self, request: Request):
        host = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            host = forwarded
        return f"{host}:{request.url.path}"

    def _prune(self, key: str, now: float):
        q = self.failures[key]
        cutoff = now - self.window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def _failure_limited(self, request: Request) -> bool:
        if request.url.path not in self.AUTH_PATHS:
            return False
        q = self._prune(self._client_key(request), time.monotonic())
        return len(q) >= self.max_failures

    def _record_auth_result(self, request: Request, status_code: int):
        if request.url.path not in self.AUTH_PATHS:
            return
        key = self._client_key(request)
        q = self._prune(key, time.monotonic())
        if status_code >= 400:
            q.append(time.monotonic())
        elif status_code < 400:
            q.clear()

    @staticmethod
    def _origin_is_valid(request: Request):
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return True
        origin = request.headers.get("origin")
        if not origin:
            return True
        try:
            parsed = urlparse(origin)
            origin_host = parsed.netloc.lower()
            request_host = request.headers.get("host", "").lower()
            return bool(origin_host and request_host and origin_host == request_host)
        except Exception:
            return False

    async def dispatch(self, request: Request, call_next):
        if self._failure_limited(request):
            return PlainTextResponse("Too many failed authentication attempts. Try again later.", status_code=429)
        if not self._origin_is_valid(request):
            return PlainTextResponse("Cross-site request blocked.", status_code=403)

        response = await call_next(request)
        self._record_auth_result(request, response.status_code)

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

    # V12.2 product routes are deliberately registered before rapid/legacy
    # compatibility routers. FastAPI resolves the first matching route, so the
    # premium library, player matrix and evidence-first video sessions must win.
    from rapid_analysis_routes import router as rapid_analysis_router
    from scorer_routes import router as scorer_router
    from premium_ingest_routes import router as premium_ingest_router
    from premium_status_routes import router as premium_status_router
    from premium_product_routes import router as premium_product_router, premium_match_brief
    from premium_national_routes import router as premium_national_router
    from player_metrics_routes import router as player_metrics_router
    from video_session_routes import router as video_session_router

    app.include_router(premium_product_router)
    app.include_router(player_metrics_router)
    app.include_router(video_session_router)
    app.include_router(premium_ingest_router)
    app.include_router(premium_status_router)
    app.include_router(premium_national_router)
    app.include_router(rapid_analysis_router)
    app.include_router(scorer_router)

    # V12.2 invariant: the Executive Coach Brief is a first-class Ultimate
    # analysis endpoint. Keep a direct fallback because historical integration
    # passes can rebuild/copy APIRouters and previously dropped this one route.
    premium_brief_path = "/api/premium/matches/{match_id}/brief"
    premium_brief_present = any(
        getattr(route, "path", None) == premium_brief_path
        and "GET" in (getattr(route, "methods", set()) or set())
        for route in app.routes
    )
    if not premium_brief_present:
        app.add_api_route(
            premium_brief_path,
            premium_match_brief,
            methods=["GET"],
            name="premium_match_brief",
        )
