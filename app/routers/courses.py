"""과목 (A-2). SPEC 6장 과목, 3장 S-03·S-04·P-02."""

from datetime import datetime, time
from re import fullmatch

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.config import now_kst
from app.db import get_session
from app.deps import get_current_user, require_professor, require_student
from app.errors import api_error
from app.models import Course, CourseSchedule, Enrollment, Question, Role, User
from app.services import schedule

router = APIRouter(tags=["courses"])
CLASS_TIME_PATTERN = r"^(?:[01][0-9]|2[0-3]):[0-5][0-9](?::00)?$"


class EnrollRequest(BaseModel):
    code: str


class CourseScheduleRequest(BaseModel):
    day_of_week: int = Field(ge=0, le=6, strict=True)
    start_time: str = Field(pattern=CLASS_TIME_PATTERN)
    end_time: str = Field(pattern=CLASS_TIME_PATTERN)


class CreateCourseRequest(BaseModel):
    name: str
    code: str
    semester: str
    schedules: list[CourseScheduleRequest] = Field(min_length=1, max_length=7)


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
        "semester": course.semester,
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


@router.post("/courses", status_code=201)
def create_course(
    body: CreateCourseRequest,
    user: User = Depends(require_professor),
    session: Session = Depends(get_session),
):
    name = body.name.strip()
    code = body.code.strip().upper()
    semester = body.semester.strip()
    if not name or len(name) > 100:
        api_error(400, "INVALID_COURSE_NAME", "과목명은 1자 이상 100자 이하로 입력해 주세요")
    if len(code) > 20 or not fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", code):
        api_error(400, "INVALID_COURSE_CODE", "과목 코드는 영문, 숫자, 하이픈을 사용해 20자 이하로 입력해 주세요")
    if not semester or len(semester) > 20:
        api_error(400, "INVALID_SEMESTER", "학기를 1자 이상 20자 이하로 입력해 주세요")

    slots: dict[int, tuple[time, time]] = {}
    for entry in body.schedules:
        start = time.fromisoformat(entry.start_time)
        end = time.fromisoformat(entry.end_time)
        if entry.day_of_week in slots:
            api_error(400, "DUPLICATE_SCHEDULE_DAY", "같은 요일의 수업 시간을 한 번만 입력해 주세요")
        if start >= end:
            api_error(400, "INVALID_SCHEDULE_TIME", "수업 종료 시간은 시작 시간보다 늦어야 합니다")
        slots[entry.day_of_week] = (start, end)

    course = Course(name=name, code=code, semester=semester, professor_id=user.id)
    try:
        session.add(course)
        session.flush()
        session.add_all([
            CourseSchedule(course_id=course.id, day_of_week=day, start_time=start, end_time=end)
            for day, (start, end) in slots.items()
        ])
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.exec(select(Course.id).where(Course.code == code)).first() is not None:
            api_error(409, "COURSE_CODE_TAKEN", "이미 사용 중인 과목 코드입니다")
        raise

    return course_out(session, course, user, now_kst())


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
