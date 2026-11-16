"""지난 차시 (A-3). SPEC 6장 지난 차시, 3장 S-10·P-05.

지난 차시 응답에는 answered, voted, mine을 넣지 않는다. 작성자 정보도 당연히 넣지 않는다.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from app.db import get_session
from app.deps import get_current_user, require_course_member
from app.errors import api_error
from app.models import ClassSession, Question, QuestionVote, User
from app.routers.live import iso_kst

router = APIRouter(tags=["history"])


@router.get("/courses/{id}/sessions")
def list_sessions(id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """차시 배열 (id, date, week, question_count), 최신순. 질문 수는 쿼리 한 번으로 센다."""
    require_course_member(session, user, id)
    rows = session.exec(
        select(ClassSession, func.count(Question.id))
        .join(Question, Question.session_id == ClassSession.id, isouter=True)
        .where(ClassSession.course_id == id)
        .group_by(ClassSession.id)
        .order_by(ClassSession.date.desc())
    ).all()
    return [
        {"id": cs.id, "date": cs.date.isoformat(), "week": cs.week, "question_count": count}
        for cs, count in rows
    ]


@router.get("/sessions/{id}/questions")
def list_session_questions(id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """질문 배열 (id, content, created_at, vote_count), 시간순. 궁금 수는 쿼리 한 번으로 센다."""
    cs = session.get(ClassSession, id)
    if cs is None:
        api_error(404, "NOT_FOUND", "차시를 찾을 수 없습니다")
    require_course_member(session, user, cs.course_id)

    rows = session.exec(
        select(Question.id, Question.content, Question.created_at, func.count(QuestionVote.id))
        .join(QuestionVote, QuestionVote.question_id == Question.id, isouter=True)
        .where(Question.session_id == id)
        .group_by(Question.id, Question.content, Question.created_at)
        .order_by(Question.created_at, Question.id)
    ).all()
    return [
        {"id": qid, "content": content, "created_at": iso_kst(created_at), "vote_count": votes}
        for qid, content, created_at, votes in rows
    ]
