"""운영자용 API: 강의 일괄 등록, 교수 계정 비밀번호 설정.

강의계획서의 과목들을 담당 교수 메일과 함께 미리 넣어 둔다.
교수 계정이 아직 없으면 "가입 대기" 교수 계정(비밀번호 없음, 로그인 불가)을 만들어 과목을 연결한다.
교수가 그 메일로 가입하면 계정이 활성화되고, 과목 코드를 입력하지 않아도 내 강의에 바로 보인다 (auth.py).

- 헤더 X-Admin-Key가 환경변수 ADMIN_API_KEY와 같아야 한다. 비어 있으면 이 API는 꺼져 있다.
- 같은 학기의 과목 코드만 갱신한다. 다른 학기에 이미 등록된 과목 코드는 재사용할 수 없다.
- 요청 전체를 먼저 검사하고 한 번에 저장한다. 하나라도 틀리면 아무것도 저장하지 않는다.
- 테이블 구조는 바꾸지 않는다 (가입 대기는 password_hash가 빈 문자열인 교수 계정).
"""

import hmac
import os
from re import fullmatch

from fastapi import APIRouter, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete, select

from app.db import get_session
from app.errors import api_error
from app.models import Course, CourseSchedule, Role, User
from app.routers.auth import (
    ALLOWED_DOMAIN,
    MAX_NAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    PENDING_PASSWORD_HASH,
    is_pending_professor,
)
from app.routers.courses import CourseScheduleRequest
from app.services import schedule
from app.services.security import hash_password

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
    schedules: list[CourseScheduleRequest] = Field(min_length=1, max_length=schedule.MAX_SCHEDULES)


class AdminCoursesRequest(BaseModel):
    courses: list[AdminCourse] = Field(min_length=1, max_length=200)


def _validated(c: AdminCourse) -> dict:
    """POST /api/courses(courses.py)와 같은 규칙 + 교수 메일·이름."""
    code = c.code.strip().upper()
    name = c.name.strip()
    semester = schedule.normalize_semester(c.semester)
    email = c.professor_email.strip().lower()
    prof_name = c.professor_name.strip()
    where = f"[{code or c.code}] "
    if len(code) > 20 or not fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", code):
        api_error(400, "INVALID_COURSE_CODE", where + "과목 코드는 영문, 숫자, 하이픈을 사용해 20자 이하로 입력해 주세요")
    if not name or len(name) > 100:
        api_error(400, "INVALID_COURSE_NAME", where + "과목명은 1자 이상 100자 이하로 입력해 주세요")
    if semester is None:
        api_error(400, "INVALID_SEMESTER", where + "학기를 2026-2 또는 2026년 2학기 형식으로 입력해 주세요")
    local, sep, domain = email.partition("@")
    if not sep or not local or domain != ALLOWED_DOMAIN:
        api_error(400, "INVALID_EMAIL_DOMAIN", where + "교수 메일은 knu.ac.kr이어야 합니다")
    if not 1 <= len(prof_name) <= MAX_NAME_LENGTH:
        api_error(400, "INVALID_NAME", where + f"교수 이름은 1자 이상 {MAX_NAME_LENGTH}자 이하로 입력해 주세요")

    slots = schedule.parse_schedules(c.schedules, prefix=where)
    return {"code": code, "name": name, "semester": semester, "email": email, "prof_name": prof_name, "slots": slots}


def _status(user: User) -> str:
    return "PENDING" if is_pending_professor(user) else "ACTIVE"


@router.post("/admin/courses", dependencies=[Depends(require_admin)])
def upsert_courses(body: AdminCoursesRequest, session: Session = Depends(get_session)):
    """강의 일괄 등록. 과목 코드 기준으로 생성하거나 같은 학기의 강의를 갱신한다."""
    items = [_validated(c) for c in body.courses]
    codes = [i["code"] for i in items]
    if len(set(codes)) != len(codes):
        api_error(400, "DUPLICATE_COURSE_CODE", "요청 안에 같은 과목 코드가 두 번 있습니다")

    existing_courses = {
        course.code: course for course in session.exec(select(Course).where(Course.code.in_(codes)))
    }
    for i in items:
        course = existing_courses.get(i["code"])
        if course is not None and schedule.normalize_semester(course.semester) != i["semester"]:
            api_error(409, "COURSE_CODE_TAKEN", f"[{course.code}] 다른 학기에 이미 사용된 과목 코드입니다")

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

        course = existing_courses.get(i["code"])
        if course is None:
            course = Course(code=i["code"], name=i["name"], semester=i["semester"], professor_id=prof.id)
            session.add(course)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                if session.exec(select(Course.id).where(Course.code == i["code"])).first() is not None:
                    api_error(409, "COURSE_CODE_TAKEN", f"[{i['code']}] 이미 사용 중인 과목 코드입니다")
                raise
            created += 1
        else:
            course.name, course.semester, course.professor_id = i["name"], i["semester"], prof.id
            session.add(course)
            session.exec(delete(CourseSchedule).where(CourseSchedule.course_id == course.id))
            updated += 1
        session.add_all([
            CourseSchedule(course_id=course.id, day_of_week=d, start_time=s, end_time=e)
            for d, s, e in i["slots"]
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


# ---------- 교수 계정 비밀번호 설정 (목업·데모용) ----------

class AdminProfessor(BaseModel):
    email: str
    password: str
    name: str | None = None  # 새로 만들 때는 필수, 이미 있으면 바꿀 때만


class AdminProfessorsRequest(BaseModel):
    professors: list[AdminProfessor] = Field(min_length=1, max_length=100)


@router.put("/admin/professors", dependencies=[Depends(require_admin)])
def set_professor_passwords(body: AdminProfessorsRequest, session: Session = Depends(get_session)):
    """교수 계정 비밀번호를 운영자가 정한다. 계정이 없으면 만든다.

    - 미리 등록된(비밀번호 없는) 교수 계정에 쓰면 바로 로그인할 수 있게 된다.
    - 이미 쓰고 있는 교수 계정에 쓰면 비밀번호가 바뀐다. 실제 교수 계정에는 쓰지 않는다.
    - 비밀번호는 응답이나 로그에 남기지 않는다. 요청 전체를 검사한 뒤 한 번에 저장한다.
    """
    items = []
    seen: set[str] = set()
    for p in body.professors:
        email = p.email.strip().lower()
        name = (p.name or "").strip()
        local, sep, domain = email.partition("@")
        if not sep or not local or domain != ALLOWED_DOMAIN:
            api_error(400, "INVALID_EMAIL_DOMAIN", f"[{email}] 교수 메일은 knu.ac.kr이어야 합니다")
        if email in seen:
            api_error(400, "DUPLICATE_EMAIL", f"[{email}] 요청 안에 같은 메일이 두 번 있습니다")
        seen.add(email)
        if len(p.password) < MIN_PASSWORD_LENGTH:
            api_error(400, "WEAK_PASSWORD", f"[{email}] 비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다")
        if len(name) > MAX_NAME_LENGTH:
            api_error(400, "INVALID_NAME", f"[{email}] 이름은 {MAX_NAME_LENGTH}자 이하로 입력해 주세요")
        user = session.exec(select(User).where(User.email == email)).first()
        if user is not None and user.role != Role.PROFESSOR:
            api_error(409, "PROFESSOR_EMAIL_IS_STUDENT", f"[{email}] 학생 계정입니다")
        if user is None and not name:
            api_error(400, "INVALID_NAME", f"[{email}] 새 교수 계정에는 이름이 필요합니다")
        items.append((email, name, p.password, user))

    result = []
    for email, name, password, user in items:
        if user is None:
            user = User(email=email, password_hash=hash_password(password), name=name, role=Role.PROFESSOR)
            status = "CREATED"
        else:
            status = "ACTIVATED" if is_pending_professor(user) else "UPDATED"
            user.password_hash = hash_password(password)
            if name:
                user.name = name
        session.add(user)
        result.append({"email": email, "name": user.name, "status": status})
    session.commit()
    return {"professors": result}
