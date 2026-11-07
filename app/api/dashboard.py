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
    trend, scoped_trend = {}, {}
    for s in reversed([s for s in sessions if s.status == 'done'][:10]):
        competencies = (await db.scalars(select(SessionCompetency).where(SessionCompetency.session_id == s.id))).all()
        for c in competencies:
            if c.score is not None:
                assessment = s.script.get('assessment', {})
                point = {'session_id':s.uuid, 'score':c.score}
                # Keep the legacy series generic; EM keys have different behavioral definitions.
                if not assessment.get('profile_id'):
                    trend.setdefault(c.competency, []).append(point)
                identity = assessment.get('sha256', 'legacy')
                series = scoped_trend.setdefault(identity, {'profile_id':assessment.get('profile_id','general'),
                    'version':assessment.get('version','legacy'), 'sha256':identity, 'competencies':{}})
                series['competencies'].setdefault(c.competency, {'name':assessment.get('competency_definitions', {}).get(c.competency, {}).get('name',c.competency), 'points':[]})['points'].append(point)
    return {'total_sessions': len(sessions), 'completed_sessions': len(scored), 'avg_score': round(sum(scored)/len(scored), 2) if scored else None,
            'best_score': max(scored) if scored else None, 'recent_sessions': [session_item(s) for s in sessions[:5]],
            'competency_trend': trend, 'competency_trend_by_rubric': scoped_trend}
