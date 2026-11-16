"""과목 (A-2). SPEC 6장 과목, 3장 S-03·S-04·P-02."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.config import now_kst
from app.db import get_session
from app.deps import get_current_user, require_student
from app.errors import api_error
from app.models import Course, Enrollment, Question, Role, User
from app.services import schedule

router = APIRouter(tags=["courses"])


class EnrollRequest(BaseModel):
    code: str


def course_out(session: Session, course: Course, user: User, now: datetime) -> dict:
    """과목 객체. code는 교수에게만 담는다. live_question_count는 수업 중이 아니면 0."""
    live = schedule.is_live(course, now)
    live_count = 0
    if live:
        today = schedule.find_today_session(session, course.id, now)
        if today is not None:
            live_count = session.exec(
                select(func.count()).select_from(Question).where(Question.session_id == today.id)
            ).one()

    professor = session.get(User, course.professor_id)
    out = {
        "id": course.id,
        "name": course.name,
        "code": course.code,
        "professor_name": professor.name if professor else None,
        "schedule_text": schedule.schedule_text(course),
        "is_live": live,
        "next_class_at": schedule.next_class_at(course, now),
        "live_question_count": live_count,
    }
    if user.role != Role.PROFESSOR:
        del out["code"]
    return out


@router.get("/courses")
def list_courses(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role == Role.PROFESSOR:
        stmt = select(Course).where(Course.professor_id == user.id)
    else:
        stmt = select(Course).join(Enrollment, Enrollment.course_id == Course.id).where(Enrollment.user_id == user.id)
    now = now_kst()
    items = [course_out(session, c, user, now) for c in session.exec(stmt.order_by(Course.id)).all()]
    # 수업 중인 과목을 맨 위로, 나머지는 다음 수업이 가까운 순
    items.sort(key=lambda c: (not c["is_live"], c["next_class_at"] is None, c["next_class_at"] or now))
    return items


@router.post("/courses/enroll", status_code=201)
def enroll(body: EnrollRequest, user: User = Depends(require_student), session: Session = Depends(get_session)):
    code = body.code.strip().upper()
    course = session.exec(select(Course).where(Course.code == code)).first() if code else None
    if course is None:
        api_error(404, "COURSE_NOT_FOUND", "없는 과목 코드입니다")

    exists = session.exec(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course.id)
    ).first()
    if exists:
        api_error(409, "ALREADY_ENROLLED", "이미 등록한 과목입니다")

    session.add(Enrollment(user_id=user.id, course_id=course.id))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        api_error(409, "ALREADY_ENROLLED", "이미 등록한 과목입니다")
    return course_out(session, course, user, now_kst())
