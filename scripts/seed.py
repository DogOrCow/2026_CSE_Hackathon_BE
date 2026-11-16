"""초기 데이터: 교수 1명, 학생 3명, 과목 2개(각 시간표 2개), 수강 등록.

여러 번 실행해도 중복되지 않는다.
    python -m scripts.seed

비밀번호는 bcrypt 해시로 저장한다. A-1의 security.py도 bcrypt로 검증해야 seed 계정으로 로그인된다.
"""

from datetime import time

import bcrypt
from sqlmodel import Session, select

from app.db import create_db_and_tables, engine
from app.models import Course, CourseSchedule, Enrollment, Role, User

SEED_PASSWORD = "password1234"
SEMESTER = "2026-2"

PROFESSOR = {"email": "prof@knu.ac.kr", "name": "서지환"}
STUDENTS = ["student1@knu.ac.kr", "student2@knu.ac.kr", "student3@knu.ac.kr"]
COURSES = [
    {
        "code": "COMP0322",
        "name": "데이터베이스",
        # (요일 0=월, 시작, 종료) 화·목 10:30
        "schedules": [(1, time(10, 30), time(11, 45)), (3, time(10, 30), time(11, 45))],
    },
    {
        "code": "COMP0312",
        "name": "운영체제",
        # 월·수 13:00
        "schedules": [(0, time(13, 0), time(14, 15)), (2, time(13, 0), time(14, 15))],
    },
]


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _get_or_create_user(s: Session, email: str, role: Role, name: str | None = None) -> User:
    user = s.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email, password_hash=_hash(SEED_PASSWORD), name=name, role=role)
        s.add(user)
        s.flush()
    return user


def seed() -> None:
    create_db_and_tables()
    with Session(engine) as s:
        prof = _get_or_create_user(s, PROFESSOR["email"], Role.PROFESSOR, PROFESSOR["name"])
        students = [_get_or_create_user(s, e, Role.STUDENT) for e in STUDENTS]

        for c in COURSES:
            course = s.exec(select(Course).where(Course.code == c["code"])).first()
            if course is None:
                course = Course(code=c["code"], name=c["name"], professor_id=prof.id, semester=SEMESTER)
                s.add(course)
                s.flush()

            for dow, start, end in c["schedules"]:
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

        print("seed 완료")
        print(f"  교수 id={prof.id} {prof.email}")
        for st in students:
            print(f"  학생 id={st.id} {st.email}")
        print(f"  비밀번호(공통): {SEED_PASSWORD}")


if __name__ == "__main__":
    seed()
