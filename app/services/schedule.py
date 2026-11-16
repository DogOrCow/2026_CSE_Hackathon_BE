"""수업 중 판별과 차시 (SPEC 4장). 0단계 임시 버전.

get_live_session()은 지금은 항상 오늘 차시를 돌려준다.
A-2에서 시간표 판별로 바꾸되, 이름·인자·반환 타입은 그대로 둔다.
수업 중이 아니면 api_error(409, "NOT_IN_CLASS", ...)를 던지게 된다.
"""

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import now_kst, settings
from app.models import ClassSession


def week_of(d: date) -> int:
    return (d - settings.SEMESTER_START).days // 7 + 1


def _get_or_create_session(session: Session, course_id: int, d: date) -> ClassSession:
    stmt = select(ClassSession).where(ClassSession.course_id == course_id, ClassSession.date == d)
    found = session.exec(stmt).first()
    if found:
        return found
    cs = ClassSession(course_id=course_id, date=d, week=week_of(d))
    session.add(cs)
    try:
        session.commit()
    except IntegrityError:
        # 동시에 두 요청이 만들려고 하면 (course_id, date) 유일 제약으로 하나만 남는다
        session.rollback()
        return session.exec(stmt).one()
    session.refresh(cs)
    return cs


def get_live_session(session: Session, course_id: int) -> ClassSession:
    # 임시: 시간표와 무관하게 오늘 차시 (DEMO_ALWAYS_LIVE 동작)
    return _get_or_create_session(session, course_id, now_kst().date())
