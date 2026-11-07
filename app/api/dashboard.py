from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.db import get_db
from app.deps import current_user
from app.models import InterviewSession, SessionCompetency
from app.services.interview import session_item

router = APIRouter()


@router.get('/api/dashboard')
async def dashboard(user=Depends(current_user), db=Depends(get_db)):
    sessions = list((await db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id).order_by(InterviewSession.created_at.desc()))).all())
    scored = [s.total_score for s in sessions if s.status == 'done' and s.total_score is not None]
    trend = {}
    for s in reversed([s for s in sessions if s.status == 'done'][:10]):
        competencies = (await db.scalars(select(SessionCompetency).where(SessionCompetency.session_id == s.id))).all()
        for c in competencies:
            if c.score is not None:
                trend.setdefault(c.competency, []).append({'session_id': s.uuid, 'score': c.score})
    return {'total_sessions': len(sessions), 'completed_sessions': len(scored), 'avg_score': round(sum(scored)/len(scored), 2) if scored else None,
            'best_score': max(scored) if scored else None, 'recent_sessions': [session_item(s) for s in sessions[:5]], 'competency_trend': trend}
