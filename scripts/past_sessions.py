"""이미 있는 과목에 지난 수업 차시와 질문 예시를 넣는다 (시연용).

seed 과목이 아닌 과목(심사용 과목, 교수가 화면에서 추가한 과목 등)에도 "지난 질문" 화면을 채우기 위한 스크립트.
질문 내용은 scripts/seed.py의 COURSES에 있는 예시를 쓴다. 작성자와 나도 궁금은 그 과목의 수강 학생으로 정한다.

    python -m scripts.past_sessions JUDGE0322                 # 같은 이름의 seed 과목 질문을 사용
    python -m scripts.past_sessions JUDGE0322 --from COMP0312  # 운영체제 질문을 사용
    python -m scripts.past_sessions JUDGE0322 --dry-run        # 넣지 않고 계획만 출력

배포 DB에 넣을 때는 Railway Postgres의 외부 접속 주소를 DATABASE_URL로 넘긴다.

    DATABASE_URL='postgresql://...' python -m scripts.past_sessions JUDGE0322

- 비밀번호나 계정은 건드리지 않는다.
- 날짜별로 확인한다. 이미 질문이 있는 차시는 건너뛰고, 빈 차시에는 질문만 채운다. 여러 번 실행해도 중복되지 않는다.
- 오늘 이후 차시는 건드리지 않는다.
"""

import argparse
import sys
from datetime import datetime, timedelta

from sqlmodel import Session, func, select

from app.config import KST, now_kst
from app.db import create_db_and_tables, engine
from app.models import ClassSession, Course, CourseSchedule, Enrollment, Question, QuestionVote, Role, User
from app.services.schedule import week_of
from scripts.seed import COURSES, _past_dates


def _template(course: Course, from_code: str | None) -> dict:
    if from_code:
        for c in COURSES:
            if c["code"] == from_code.upper():
                return c
        sys.exit(f"--from {from_code}: seed.py COURSES에 없는 코드입니다 ({', '.join(c['code'] for c in COURSES)})")
    for c in COURSES:
        if c["name"] == course.name:
            return c
    return COURSES[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="과목에 지난 차시와 질문 예시 넣기")
    ap.add_argument("course_code", help="질문을 넣을 과목 코드 (예: JUDGE0322)")
    ap.add_argument("--from", dest="from_code", help="질문 예시를 가져올 seed 과목 코드 (기본: 같은 이름)")
    ap.add_argument("--dry-run", action="store_true", help="넣지 않고 계획만 출력")
    args = ap.parse_args()

    create_db_and_tables()
    with Session(engine) as s:
        course = s.exec(select(Course).where(Course.code == args.course_code.upper())).first()
        if course is None:
            print(f"과목 코드 {args.course_code}가 DB에 없습니다")
            return 1

        schedules = [
            (sc.day_of_week, sc.start_time, sc.end_time)
            for sc in s.exec(select(CourseSchedule).where(CourseSchedule.course_id == course.id)).all()
        ]
        if not schedules:
            print(f"{course.code}에 시간표가 없어 지난 수업 날짜를 정할 수 없습니다")
            return 1

        students = list(
            s.exec(
                select(User)
                .join(Enrollment, Enrollment.user_id == User.id)
                .where(Enrollment.course_id == course.id, User.role == Role.STUDENT)
                .order_by(User.id)
            ).all()
        )
        if not students:
            print(f"{course.code}에 수강 학생이 없습니다. 질문 작성자를 정할 수 없습니다")
            return 1

        template = _template(course, args.from_code)
        past = template["past"]
        dates = _past_dates(schedules, now_kst().date(), len(past))
        print(f"{course.name} ({course.code}) ← {template['name']} 질문 예시, 수강 학생 {len(students)}명")

        added_sessions = added_questions = 0
        for (d, start), questions in zip(dates, past):
            cs = s.exec(select(ClassSession).where(ClassSession.course_id == course.id, ClassSession.date == d)).first()
            if cs is not None:
                count = s.exec(select(func.count()).select_from(Question).where(Question.session_id == cs.id)).one()
                if count:
                    print(f"  {d} 건너뜀: 이미 질문 {count}개")
                    continue

            print(f"  {d} {'빈 차시에 ' if cs else ''}질문 {len(questions)}개{' (dry-run)' if args.dry_run else ''}")
            if args.dry_run:
                continue

            if cs is None:
                cs = ClassSession(course_id=course.id, date=d, week=week_of(d))
                s.add(cs)
                s.flush()
                added_sessions += 1

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
                for st in [st for st in students if st.id != author.id][:votes]:
                    s.add(QuestionVote(question_id=q.id, user_id=st.id, created_at=asked_at + timedelta(minutes=1)))
                added_questions += 1

        if not args.dry_run:
            s.commit()
            print(f"완료: 차시 {added_sessions}개 생성, 질문 {added_questions}개 추가")
    return 0


if __name__ == "__main__":
    sys.exit(main())
