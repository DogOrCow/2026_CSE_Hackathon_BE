"""수업 중 판별과 차시 (A-2, SPEC 4장).

공개 함수
- is_live(course, now) -> bool
- next_class_at(course, now) -> datetime | None     지금 이후 가장 가까운 수업 시작 시각
- schedule_text(course) -> str                        예: "화·목 10:30"
- session_bounds(class_session) -> (starts_at, ends_at)  B의 /live 응답과 수업 종료 이벤트용
- get_live_session(session, course_id) -> ClassSession  수업 중이 아니면 409 NOT_IN_CLASS

course 인자를 받는 함수는 그 객체가 붙어 있는 DB 세션으로 시간표를 읽는다.
DEMO_ALWAYS_LIVE=true면 시간표와 무관하게 모든 과목을 수업 중으로 보고 오늘 차시를 쓴다.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import KST, now_kst, settings
from app.errors import api_error
from app.models import ClassSession, Course, CourseSchedule

DAY_NAMES = "월화수목금토일"


def week_of(d: date) -> int:
    return (d - settings.SEMESTER_START).days // 7 + 1


def _schedules(course: Course) -> list[CourseSchedule]:
    s = Session.object_session(course)
    if s is None:
        raise RuntimeError("course가 DB 세션에 붙어 있지 않습니다")
    return list(
        s.exec(
            select(CourseSchedule)
            .where(CourseSchedule.course_id == course.id)
            .order_by(CourseSchedule.day_of_week, CourseSchedule.start_time)
        ).all()
    )


def _at(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=KST)


def _current_slot(schedules: list[CourseSchedule], now: datetime) -> CourseSchedule | None:
    now = now.astimezone(KST)
    for sc in schedules:
        if sc.day_of_week == now.weekday() and sc.start_time <= now.time() < sc.end_time:
            return sc
    return None


def is_live(course: Course, now: datetime) -> bool:
    if settings.DEMO_ALWAYS_LIVE:
        return True
    return _current_slot(_schedules(course), now) is not None


def next_class_at(course: Course, now: datetime) -> datetime | None:
    now = now.astimezone(KST)
    schedules = _schedules(course)
    for offset in range(8):
        d = now.date() + timedelta(days=offset)
        starts = sorted(_at(d, sc.start_time) for sc in schedules if sc.day_of_week == d.weekday())
        for st in starts:
            if st > now:
                return st
    return None


def schedule_text(course: Course) -> str:
    """같은 시작 시각끼리 요일을 묶는다. 예: "화·목 10:30", "월 09:00, 수 13:00"."""
    groups: dict[time, list[int]] = {}
    for sc in _schedules(course):
        groups.setdefault(sc.start_time, []).append(sc.day_of_week)
    parts = []
    for start, days in sorted(groups.items(), key=lambda kv: min(kv[1])):
        day_str = "·".join(DAY_NAMES[d] for d in sorted(set(days)))
        parts.append(f"{day_str} {start.strftime('%H:%M')}")
    return ", ".join(parts)


def session_bounds(class_session: ClassSession) -> tuple[datetime, datetime]:
    """차시의 시작·종료 시각 (KST).

    그 날짜 요일의 시간표를 쓴다. DEMO_ALWAYS_LIVE로 시간표가 없는 날에 만든 차시는
    그날 00:00 ~ 다음 날 00:00으로 돌려준다.
    """
    s = Session.object_session(class_session)
    if s is None:
        raise RuntimeError("class_session이 DB 세션에 붙어 있지 않습니다")
    d = class_session.date
    slot = s.exec(
        select(CourseSchedule)
        .where(CourseSchedule.course_id == class_session.course_id, CourseSchedule.day_of_week == d.weekday())
        .order_by(CourseSchedule.start_time)
    ).first()
    if slot is None:
        start = _at(d, time(0, 0))
        return start, start + timedelta(days=1)
    return _at(d, slot.start_time), _at(d, slot.end_time)


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


def find_today_session(session: Session, course_id: int, now: datetime) -> ClassSession | None:
    """오늘 차시를 찾기만 한다 (만들지 않음)."""
    return session.exec(
        select(ClassSession).where(ClassSession.course_id == course_id, ClassSession.date == now.astimezone(KST).date())
    ).first()


def get_live_session(session: Session, course_id: int) -> ClassSession:
    """수업 중이면 오늘 차시를 (없으면 만들어) 돌려준다. 아니면 409 NOT_IN_CLASS."""
    now = now_kst()
    if not settings.DEMO_ALWAYS_LIVE:
        course = session.get(Course, course_id)
        if course is None:
            api_error(404, "NOT_FOUND", "과목을 찾을 수 없습니다")
        if _current_slot(_schedules(course), now) is None:
            api_error(409, "NOT_IN_CLASS", "지금은 수업 시간이 아닙니다")
    return _get_or_create_session(session, course_id, now.date())
