"""초기 데이터: 교수 2명, 학생 3명, 과목 2개(각 시간표 2개), 수강 등록, 지난 차시 3개씩.

여러 번 실행해도 중복되지 않는다.
    python -m scripts.seed

비밀번호는 bcrypt 해시로 저장한다. A-1의 security.py도 bcrypt로 검증해야 seed 계정으로 로그인된다.
"""

from datetime import date, datetime, time, timedelta

import bcrypt
from sqlmodel import Session, select

from app.config import KST, now_kst
from app.db import create_db_and_tables, engine
from app.models import ClassSession, Course, CourseSchedule, Enrollment, Question, QuestionVote, Role, User
from app.services.schedule import week_of

SEED_PASSWORD = "password1234"
SEMESTER = "2026-2"

PROFESSOR = {"email": "prof@knu.ac.kr", "name": "서지환"}
SECOND_PROFESSOR = {"email": "prof2@knu.ac.kr", "name": "김민준"}
STUDENTS = ["student1@knu.ac.kr", "student2@knu.ac.kr", "student3@knu.ac.kr"]
COURSES = [
    {
        "code": "COMP0322",
        "name": "데이터베이스",
        # (요일 0=월, 시작, 종료) 화·목 10:30
        "schedules": [(1, time(10, 30), time(11, 45)), (3, time(10, 30), time(11, 45))],
        # 지난 차시별 질문, 최근 차시부터. (내용, 답변 여부, 나도 궁금 수 0~2)
        "past": [
            [
                ("B+ 트리에서 노드가 꽉 차면 분할은 어떤 순서로 일어나나요?", True, 2),
                ("클러스터드 인덱스는 테이블에 왜 하나만 만들 수 있나요?", True, 1),
                ("복합 인덱스에서 컬럼 순서는 어떻게 정하나요?", False, 2),
                ("인덱스를 타는지 확인하는 방법이 있나요?", False, 0),
            ],
            [
                ("3NF와 BCNF는 실제로 어떤 경우에 달라지나요?", True, 2),
                ("정규화를 많이 하면 조인이 늘어나는데 성능은 괜찮은가요?", True, 1),
                ("함수 종속을 찾는 요령이 있을까요?", False, 1),
            ],
            [
                ("LEFT JOIN과 INNER JOIN 결과가 달라지는 예시를 한 번 더 볼 수 있을까요?", True, 2),
                ("GROUP BY에 없는 컬럼을 SELECT에 쓰면 왜 오류가 나나요?", True, 0),
                ("서브쿼리와 조인 중 어느 쪽이 더 빠른가요?", False, 1),
            ],
        ],
    },
    {
        "code": "COMP0312",
        "name": "운영체제",
        # 월·수 13:00
        "schedules": [(0, time(13, 0), time(14, 15)), (2, time(13, 0), time(14, 15))],
        "past": [
            [
                ("교착 상태 예방과 회피는 무엇이 다른가요?", True, 2),
                ("은행원 알고리즘은 실제 운영체제에서도 쓰이나요?", False, 1),
                ("세마포어와 뮤텍스는 언제 구분해서 쓰나요?", True, 1),
            ],
            [
                ("라운드 로빈에서 타임 슬라이스는 어떤 기준으로 정하나요?", True, 2),
                ("기아 상태를 막는 에이징은 어떻게 구현하나요?", False, 0),
                ("문맥 교환 비용은 어느 정도인가요?", True, 1),
            ],
            [
                ("프로세스와 스레드의 메모리 구조 차이를 그림으로 다시 볼 수 있을까요?", True, 2),
                ("fork 직후에 부모와 자식 중 누가 먼저 실행되나요?", False, 1),
            ],
        ],
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


def _past_dates(schedules: list[tuple[int, time, time]], today: date, count: int) -> list[tuple[date, time]]:
    """오늘보다 앞선 수업 날짜를 최근 것부터 count개. (날짜, 시작 시각)"""
    starts = {dow: start for dow, start, _ in schedules}
    found: list[tuple[date, time]] = []
    d = today - timedelta(days=1)
    while len(found) < count:
        if d.weekday() in starts:
            found.append((d, starts[d.weekday()]))
        d -= timedelta(days=1)
    return found


def _seed_past_sessions(s: Session, course: Course, c: dict, students: list[User]) -> None:
    """지난 차시와 질문. 이 과목에 지난 차시가 하나라도 있으면 건드리지 않는다."""
    today = now_kst().date()
    has_past = s.exec(
        select(ClassSession).where(ClassSession.course_id == course.id, ClassSession.date < today)
    ).first()
    if has_past is not None:
        return

    for (d, start), questions in zip(_past_dates(c["schedules"], today, len(c["past"])), c["past"]):
        cs = ClassSession(course_id=course.id, date=d, week=week_of(d))
        s.add(cs)
        s.flush()
        for i, (content, answered, votes) in enumerate(questions):
            asked_at = datetime.combine(d, start, tzinfo=KST) + timedelta(minutes=12 + i * 14)
            author = students[i % len(students)]
            q = Question(
                session_id=cs.id,
                author_id=author.id,
                content=content,
                created_at=asked_at,
                answered_at=asked_at + timedelta(minutes=6) if answered else None,
            )
            s.add(q)
            s.flush()
            # 자기 질문에는 누를 수 없으므로 작성자를 뺀 학생만
            voters = [st for st in students if st.id != author.id][:votes]
            for st in voters:
                s.add(QuestionVote(question_id=q.id, user_id=st.id, created_at=asked_at + timedelta(minutes=1)))


def seed() -> None:
    create_db_and_tables()
    with Session(engine) as s:
        prof = _get_or_create_user(s, PROFESSOR["email"], Role.PROFESSOR, PROFESSOR["name"])
        students = [_get_or_create_user(s, e, Role.STUDENT) for e in STUDENTS]
        second_prof = _get_or_create_user(s, SECOND_PROFESSOR["email"], Role.PROFESSOR, SECOND_PROFESSOR["name"])

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

            _seed_past_sessions(s, course, c, students)

        s.commit()

        print("seed 완료")
        print(f"  교수 id={prof.id} {prof.email}")
        print(f"  교수 id={second_prof.id} {second_prof.email}")
        for st in students:
            print(f"  학생 id={st.id} {st.email}")
        print(f"  비밀번호(공통): {SEED_PASSWORD}")


if __name__ == "__main__":
    seed()
