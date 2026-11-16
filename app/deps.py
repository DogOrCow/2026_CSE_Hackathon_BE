"""인증·권한 의존성.

get_current_user()는 0단계 임시 버전이다. A-1에서 JWT 검증으로 바꾸되,
이름과 반환 타입(User)은 그대로 둔다.

require_course_member / require_course_professor 는 일반 함수다.
경로 변수 이름이 라우터마다 달라서({id}, 질문의 course 등) 핸들러 안에서 직접 부른다.

    @router.get("/courses/{id}/live")
    def live(id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
        course = require_course_member(session, user, id)
"""

from fastapi import Depends, Header
from sqlmodel import Session, select

from app.config import settings
from app.db import get_session
from app.errors import api_error
from app.models import Course, Enrollment, Role, User


def get_current_user(
    x_debug_user: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    # 임시: X-Debug-User 헤더의 사용자 ID. ENV=dev에서만 허용
    if not settings.is_dev or not x_debug_user or not x_debug_user.isdigit():
        api_error(401, "UNAUTHORIZED", "로그인이 필요합니다")
    user = session.get(User, int(x_debug_user))
    if user is None:
        api_error(401, "UNAUTHORIZED", "로그인이 필요합니다")
    return user


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.STUDENT:
        api_error(403, "FORBIDDEN", "학생만 할 수 있습니다")
    return user


def require_professor(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.PROFESSOR:
        api_error(403, "FORBIDDEN", "교수만 할 수 있습니다")
    return user


def _get_course(session: Session, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        api_error(404, "NOT_FOUND", "과목을 찾을 수 없습니다")
    return course


def require_course_member(session: Session, user: User, course_id: int) -> Course:
    """등록 학생이거나 담당 교수면 과목을 돌려준다. 과목이 없으면 404, 아니면 403."""
    course = _get_course(session, course_id)
    if user.role == Role.PROFESSOR:
        if course.professor_id != user.id:
            api_error(403, "FORBIDDEN", "담당 과목이 아닙니다")
        return course
    enrolled = session.exec(
        select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course_id)
    ).first()
    if enrolled is None:
        api_error(403, "FORBIDDEN", "등록하지 않은 과목입니다")
    return course


def require_course_professor(session: Session, user: User, course_id: int) -> Course:
    """담당 교수면 과목을 돌려준다. 과목이 없으면 404, 아니면 403."""
    course = _get_course(session, course_id)
    if user.role != Role.PROFESSOR or course.professor_id != user.id:
        api_error(403, "FORBIDDEN", "담당 교수만 할 수 있습니다")
    return course
