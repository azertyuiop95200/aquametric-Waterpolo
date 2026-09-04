from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db
from models import Match, User

router = APIRouter()


@router.get('/api/premium/matches/{match_id}/status')
def premium_match_status(match_id: int, request: Request, db: Session = Depends(get_db)):
    uid = request.session.get('user_id')
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(status_code=401, detail='Login required')
    match = db.get(Match, match_id)
    if not match or match.owner_id != user.id:
        raise HTTPException(status_code=404, detail='Match not found')
    status = match.status or 'created'
    has_video = bool(match.video_path or match.video_url)
    analysis_flow = status in {
        'analysis_queued', 'analysis_running', 'analysis_ready',
        'url_analysis_queued', 'url_analysis_running', 'url_reference_ready',
        'analysis_failed',
    }
    return {
        'match_id': match.id,
        'status': status,
        'has_video': has_video,
        'analysis_flow': analysis_flow,
        'result_url': f'/matches/{match.id}/analysis/result',
    }
