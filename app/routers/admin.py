"""운영자용 강의 일괄 등록.

강의계획서의 과목들을 담당 교수 메일과 함께 미리 넣어 둔다.
교수 계정이 아직 없으면 "가입 대기" 교수 계정(비밀번호 없음, 로그인 불가)을 만들어 과목을 연결한다.
교수가 그 메일로 가입하면 계정이 활성화되고, 과목 코드를 입력하지 않아도 내 강의에 바로 보인다 (auth.py).

- 헤더 X-Admin-Key가 환경변수 ADMIN_API_KEY와 같아야 한다. 비어 있으면 이 API는 꺼져 있다.
- 과목 코드 기준으로 덮어쓴다 (없으면 생성, 있으면 이름·학기·담당 교수·시간표 갱신). 여러 번 보내도 된다.
- 요청 전체를 먼저 검사하고 한 번에 저장한다. 하나라도 틀리면 아무것도 저장하지 않는다.
- 테이블 구조는 바꾸지 않는다 (가입 대기는 password_hash가 빈 문자열인 교수 계정).
"""

import hmac
import os
from datetime import time
from re import fullmatch

from fastapi import APIRouter, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlmodel import Session, delete, select

from app.db import get_session
from app.errors import api_error
from app.models import Course, CourseSchedule, Role, User
from app.routers.auth import ALLOWED_DOMAIN, MAX_NAME_LENGTH, PENDING_PASSWORD_HASH, is_pending_professor
from app.routers.courses import CourseScheduleRequest

router = APIRouter(tags=["admin"])

admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False, description="환경변수 ADMIN_API_KEY 값")


def require_admin(key: str | None = Depends(admin_key_header)) -> None:
    expected = os.getenv("ADMIN_API_KEY", "").strip()
    if not expected:
        api_error(403, "ADMIN_DISABLED", "운영자 API가 꺼져 있습니다 (ADMIN_API_KEY 미설정)")
    if not hmac.compare_digest((key or "").strip().encode(), expected.encode()):
        api_error(403, "FORBIDDEN", "운영자 키가 올바르지 않습니다")


class AdminCourse(BaseModel):
    code: str
    name: str
    semester: str
    professor_email: str
    professor_name: str
    schedules: list[CourseScheduleRequest] = Field(min_length=1, max_length=7)


class AdminCoursesRequest(BaseModel):
    courses: list[AdminCourse] = Field(min_length=1, max_length=200)


def _validated(c: AdminCourse) -> dict:
    """POST /api/courses(courses.py)와 같은 규칙 + 교수 메일·이름."""
    code = c.code.strip().upper()
    name = c.name.strip()
    semester = c.semester.strip()
    email = c.professor_email.strip().lower()
    prof_name = c.professor_name.strip()
    where = f"[{code or c.code}] "
    if len(code) > 20 or not fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", code):
        api_error(400, "INVALID_COURSE_CODE", where + "과목 코드는 영문, 숫자, 하이픈을 사용해 20자 이하로 입력해 주세요")
    if not name or len(name) > 100:
        api_error(400, "INVALID_COURSE_NAME", where + "과목명은 1자 이상 100자 이하로 입력해 주세요")
    if not semester or len(semester) > 20:
        api_error(400, "INVALID_SEMESTER", where + "학기를 1자 이상 20자 이하로 입력해 주세요")
    local, sep, domain = email.partition("@")
    if not sep or not local or domain != ALLOWED_DOMAIN:
        api_error(400, "INVALID_EMAIL_DOMAIN", where + "교수 메일은 knu.ac.kr이어야 합니다")
    if not 1 <= len(prof_name) <= MAX_NAME_LENGTH:
        api_error(400, "INVALID_NAME", where + f"교수 이름은 1자 이상 {MAX_NAME_LENGTH}자 이하로 입력해 주세요")

    slots: dict[int, tuple[time, time]] = {}
    for entry in c.schedules:
        start, end = time.fromisoformat(entry.start_time), time.fromisoformat(entry.end_time)
        if entry.day_of_week in slots:
            api_error(400, "DUPLICATE_SCHEDULE_DAY", where + "같은 요일의 수업 시간을 한 번만 입력해 주세요")
        if start >= end:
            api_error(400, "INVALID_SCHEDULE_TIME", where + "수업 종료 시간은 시작 시간보다 늦어야 합니다")
        slots[entry.day_of_week] = (start, end)
    return {"code": code, "name": name, "semester": semester, "email": email, "prof_name": prof_name, "slots": slots}


def _status(user: User) -> str:
    return "PENDING" if is_pending_professor(user) else "ACTIVE"


@router.post("/admin/courses", dependencies=[Depends(require_admin)])
def upsert_courses(body: AdminCoursesRequest, session: Session = Depends(get_session)):
    """강의 일괄 등록. 과목 코드 기준으로 생성하거나 갱신한다."""
    items = [_validated(c) for c in body.courses]
    codes = [i["code"] for i in items]
    if len(set(codes)) != len(codes):
        api_error(400, "DUPLICATE_COURSE_CODE", "요청 안에 같은 과목 코드가 두 번 있습니다")

    # 저장 전에 학생 메일이 교수로 들어가 있지 않은지 전부 확인
    professors: dict[str, User] = {}
    for i in items:
        if i["email"] in professors:
            continue
        user = session.exec(select(User).where(User.email == i["email"])).first()
        if user is not None and user.role != Role.PROFESSOR:
            api_error(409, "PROFESSOR_EMAIL_IS_STUDENT", f"[{i['code']}] {i['email']}은 학생 계정입니다")
        professors[i["email"]] = user

    created = updated = professors_created = 0
    for i in items:
        prof = professors[i["email"]]
        if prof is None:
            prof = User(email=i["email"], password_hash=PENDING_PASSWORD_HASH, name=i["prof_name"], role=Role.PROFESSOR)
            session.add(prof)
            session.flush()
            professors[i["email"]] = prof
            professors_created += 1
        elif is_pending_professor(prof):
            prof.name = i["prof_name"]  # 가입 전이면 이름을 최신 값으로. 가입한 교수의 이름은 건드리지 않음
            session.add(prof)

        course = session.exec(select(Course).where(Course.code == i["code"])).first()
        if course is None:
            course = Course(code=i["code"], name=i["name"], semester=i["semester"], professor_id=prof.id)
            session.add(course)
            session.flush()
            created += 1
        else:
            course.name, course.semester, course.professor_id = i["name"], i["semester"], prof.id
            session.add(course)
            session.exec(delete(CourseSchedule).where(CourseSchedule.course_id == course.id))
            updated += 1
        session.add_all([
            CourseSchedule(course_id=course.id, day_of_week=d, start_time=s, end_time=e)
            for d, (s, e) in i["slots"].items()
        ])

    session.commit()
    return {
        "created": created,
        "updated": updated,
        "professors_created": professors_created,
        "courses": [
            {"code": i["code"], "name": i["name"], "professor_email": i["email"],
             "professor_status": _status(professors[i["email"]])}
            for i in items
        ],
    }


@router.get("/admin/courses", dependencies=[Depends(require_admin)])
def list_admin_courses(session: Session = Depends(get_session)):
    """등록된 과목과 담당 교수 가입 여부. 수강생 수는 세지 않는다."""
    out = []
    for course in session.exec(select(Course).order_by(Course.code)).all():
        prof = session.get(User, course.professor_id)
        out.append({
            "code": course.code,
            "name": course.name,
            "semester": course.semester,
            "professor_email": prof.email if prof else None,
            "professor_name": prof.name if prof else None,
            "professor_status": _status(prof) if prof else None,
        })
    return out
