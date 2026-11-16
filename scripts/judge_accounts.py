"""심사용 계정: 교수 1명, 학생 2명, 그 교수의 과목 1개, 수강 등록.

seed 계정(비밀번호가 README에 공개됨)과 분리해, 심사위원에게만 알려 줄 계정을 만든다.
비밀번호는 코드나 저장소에 두지 않고 실행할 때 환경변수로 넘긴다.

    JUDGE_PASSWORD='...' python -m scripts.judge_accounts

배포 DB에 만들 때는 Railway Postgres의 외부 접속 주소를 DATABASE_URL로 같이 넘긴다.

    DATABASE_URL='postgresql://...' JUDGE_PASSWORD='...' python -m scripts.judge_accounts

여러 번 실행해도 중복되지 않는다. 계정이 이미 있으면 비밀번호만 새 값으로 바꾼다.
"""

import os
import sys
from datetime import time

from sqlmodel import Session, select

from app.db import engine
from app.models import Course, CourseSchedule, Enrollment, Role, User
from app.routers.auth import MIN_PASSWORD_LENGTH
from app.services.security import hash_password

SEMESTER = "2026-2"
PROFESSOR = {"email": "judge.prof@knu.ac.kr", "name": "심사 교수"}
STUDENTS = ["judge.student1@knu.ac.kr", "judge.student2@knu.ac.kr"]
COURSE = {
    "code": "JUDGE0322",
    "name": "데이터베이스",
    # (요일 0=월, 시작, 종료) 화·목 10:30. DEMO_ALWAYS_LIVE면 시간과 무관하게 수업 중
    "schedules": [(1, time(10, 30), time(11, 45)), (3, time(10, 30), time(11, 45))],
}


def _upsert_user(s: Session, email: str, role: Role, password_hash: str, name: str | None = None) -> User:
    user = s.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email, password_hash=password_hash, name=name, role=role)
    else:
        user.password_hash = password_hash
    s.add(user)
    s.flush()
    return user


def main() -> None:
    password = os.environ.get("JUDGE_PASSWORD", "")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"JUDGE_PASSWORD 환경변수에 {MIN_PASSWORD_LENGTH}자 이상의 비밀번호를 넣어 주세요")
    password_hash = hash_password(password)

    with Session(engine) as s:
        prof = _upsert_user(s, PROFESSOR["email"], Role.PROFESSOR, password_hash, PROFESSOR["name"])
        students = [_upsert_user(s, e, Role.STUDENT, password_hash) for e in STUDENTS]

        course = s.exec(select(Course).where(Course.code == COURSE["code"])).first()
        if course is None:
            course = Course(code=COURSE["code"], name=COURSE["name"], professor_id=prof.id, semester=SEMESTER)
            s.add(course)
            s.flush()

        for dow, start, end in COURSE["schedules"]:
            exists = s.exec(
                select(CourseSchedule).where(
                    CourseSchedule.course_id == course.id,
                    CourseSchedule.day_of_week == dow,
                    CourseSchedule.start_time == start,
                )
            ).first()
            if exists is None:
                s.add(CourseSchedule(course_id=course.id, day_of_week=dow, start_time=start, end_time=end))

        for st in students:
            enrolled = s.exec(
                select(Enrollment).where(Enrollment.user_id == st.id, Enrollment.course_id == course.id)
            ).first()
            if enrolled is None:
                s.add(Enrollment(user_id=st.id, course_id=course.id))

        s.commit()

        # 비밀번호는 출력하지 않는다
        print("심사용 계정 준비 완료")
        print(f"  교수 {prof.email}")
        for st in students:
            print(f"  학생 {st.email}")
        print(f"  과목 {course.name} ({course.code})")


if __name__ == "__main__":
    main()
