"""수업 중 질문 목록 (B). SPEC 6장 수업 중, 3장 S-05·P-03.

질문 직렬화 헬퍼도 여기에 둔다. questions.py(등록·투표·답변)와 stream 이벤트가 같이 쓴다.
응답은 항상 명시적인 dict로 만든다. Question 테이블 객체를 그대로 내보내면 author_id가 샌다.
"""

from collections.abc import Iterable
from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from app.config import KST
from app.db import get_session
from app.deps import get_current_user, require_course_member
from app.models import ClassSession, CourseSchedule, Question, QuestionVote, Role, User
from app.services.schedule import get_live_session

router = APIRouter(tags=["live"])


# ---------- 공통 헬퍼 ----------

def iso_kst(dt: datetime | None) -> str | None:
    """+09:00이 붙은 ISO 8601 (초 단위). naive 값(sqlite)은 KST로 본다."""
    if dt is None:
        return None
    dt = dt.replace(tzinfo=KST) if dt.tzinfo is None else dt.astimezone(KST)
    return dt.isoformat(timespec="seconds")


def vote_counts(session: Session, question_ids: Iterable[int]) -> dict[int, int]:
    ids = list(question_ids)
    if not ids:
        return {}
    rows = session.exec(
        select(QuestionVote.question_id, func.count())
        .where(QuestionVote.question_id.in_(ids))
        .group_by(QuestionVote.question_id)
    ).all()
    return {qid: cnt for qid, cnt in rows}


def my_votes(session: Session, user: User, question_ids: Iterable[int]) -> set[int]:
    ids = list(question_ids)
    if not ids or user.role != Role.STUDENT:
        return set()
    rows = session.exec(
        select(QuestionVote.question_id).where(
            QuestionVote.user_id == user.id, QuestionVote.question_id.in_(ids)
        )
    ).all()
    return set(rows)


def question_event_data(q: Question, vote_count: int) -> dict:
    """SSE question.created 데이터 (SPEC 7장). 개인별 값(mine, voted)은 넣지 않는다."""
    return {
        "id": q.id,
        "content": q.content,
        "created_at": iso_kst(q.created_at),
        "vote_count": vote_count,
        "answered": q.answered_at is not None,
    }


def question_out(q: Question, user: User, vote_count: int, voted: bool) -> dict:
    """수업 중 질문 객체. 교수에게는 voted와 mine이 항상 false."""
    is_student = user.role == Role.STUDENT
    return {
        **question_event_data(q, vote_count),
        "voted": voted if is_student else False,
        "mine": (q.author_id == user.id) if is_student else False,
    }


def session_window(session: Session, cs: ClassSession) -> tuple[str | None, str | None]:
    """차시의 시작·종료 시각. 그 요일 시간표가 없으면 (None, None).

    DEMO_ALWAYS_LIVE로 시간표 없는 날에 수업 중이 된 경우 None이 나간다.
    TODO: A-2(#3)에서 schedule.py에 같은 함수가 생기면 그쪽을 쓴다.
    """
    sched = session.exec(
        select(CourseSchedule)
        .where(CourseSchedule.course_id == cs.course_id, CourseSchedule.day_of_week == cs.date.weekday())
        .order_by(CourseSchedule.start_time)
    ).first()
    if sched is None:
        return None, None
    d: date = cs.date
    starts = datetime.combine(d, sched.start_time, tzinfo=KST)
    ends = datetime.combine(d, sched.end_time, tzinfo=KST)
    return iso_kst(starts), iso_kst(ends)


# ---------- 엔드포인트 ----------

@router.get("/courses/{id}/live")
def get_live(
    id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    require_course_member(session, user, id)
    cs = get_live_session(session, id)

    questions = session.exec(
        select(Question).where(Question.session_id == cs.id).order_by(Question.created_at, Question.id)
    ).all()
    ids = [q.id for q in questions]
    counts = vote_counts(session, ids)
    voted = my_votes(session, user, ids)

    starts_at, ends_at = session_window(session, cs)
    return {
        "session": {
            "id": cs.id,
            "date": cs.date.isoformat(),
            "week": cs.week,
            "starts_at": starts_at,
            "ends_at": ends_at,
        },
        "questions": [question_out(q, user, counts.get(q.id, 0), q.id in voted) for q in questions],
    }
