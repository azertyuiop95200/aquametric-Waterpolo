"""Thin V8 binding over V7.

V7 patches HTML after Jinja rendering, so this layer resolves the numeric match
id into the injected async-status URLs before the page is sent to the browser.
It also gives the embedded YouTube players a slightly longer initial buffer so
capture does not start while the source is still in its lowest-quality ramp-up,
and caps automatic quality pauses so a permanently low-quality source cannot
prevent the analysis from ever finishing.
"""
from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from db import get_db
from capture_turbo_routes_v7 import (
    turbo_append_chunk,
    turbo_capture_status,
    turbo_create_session,
    turbo_finish_capture,
    turbo_progress_frame,
)
from capture_turbo_routes_v7 import turbo_browser_capture_page as _v7_page


def turbo_browser_capture_page(match_id: int, request: Request, db: Session = Depends(get_db)):
    response = _v7_page(match_id=match_id, request=request, db=db)
    html = bytes(response.body).decode("utf-8")
    html = html.replace("{{match.id}}", str(match_id))
    html = html.replace("setTimeout(r,1800)", "setTimeout(r,2800)", 1)
    html = html.replace(
        "let qualityPaused=false,qualityPauseStarted=0,qualityPausedMs=0,qualityRetryTimer=null,lastQualityPauseAt=0;",
        "let qualityPaused=false,qualityPauseStarted=0,qualityPausedMs=0,qualityRetryTimer=null,lastQualityPauseAt=0,qualityPauseCount=0;",
        1,
    )
    html = html.replace(
        "if(externalFallback||qualityPaused||stopping||!recorder||Date.now()-lastQualityPauseAt<1600)return;lastQualityPauseAt=Date.now();qualityPaused=true;",
        "if(externalFallback||qualityPaused||stopping||!recorder||qualityPauseCount>=6||Date.now()-lastQualityPauseAt<1600)return;lastQualityPauseAt=Date.now();qualityPauseCount++;qualityPaused=true;",
        1,
    )
    return HTMLResponse(html)
