"""수업 중 판별과 차시 (A-2, SPEC 4장).

공개 함수
- is_live(course, now) -> bool
- next_class_at(course, now) -> datetime | None     지금 이후 가장 가까운 수업 시작 시각
- schedule_text(course) -> str                        예: "화·목 10:30"
- session_bounds(class_session) -> (starts_at, ends_at)  B의 /live 응답과 수업 종료 이벤트용
- get_live_session(session, course_id) -> ClassSession  수업 중이 아니면 409 NOT_IN_CLASS
- parse_schedules(entries) -> [(요일, 시작, 종료)]     강의 등록 입력 검사 (courses.py, admin.py)

course 인자를 받는 함수는 그 객체가 붙어 있는 DB 세션으로 시간표를 읽는다.
DEMO_ALWAYS_LIVE=true면 시간표와 무관하게 모든 과목을 수업 중으로 보고 오늘 차시를 쓴다.

같은 요일에 시간표가 여러 개일 수 있다 (예: 화 10:30~11:45, 화 15:00~16:15). 겹치지만 않으면 된다.
차시는 (과목, 날짜)로 하나라서, 같은 날의 두 시간은 같은 차시를 쓴다.
"""

from datetime import date, datetime, time, timedelta
from re import fullmatch

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import KST, now_kst, settings
from app.errors import api_error
from app.models import ClassSession, Course, CourseSchedule

DAY_NAMES = "월화수목금토일"


def normalize_semester(value: str) -> str | None:
    parts = fullmatch(r"([0-9]{4})\s*(?:-\s*([12])|년\s*([12])\s*학기)", value.strip())
    if parts is None:
        return None
    year, short_term, korean_term = parts.groups()
    if not 1 <= int(year) < date.max.year:
        return None
    return f"{year}-{short_term or korean_term}"


def _semester_start(year: int, term: int) -> date:
    configured = settings.SEMESTER_START
    if configured.year == year and (1 if configured.month <= 6 else 2) == term:
        return configured
    return date(year, 3 if term == 1 else 9, 1)


def _semester_bounds(semester: str) -> tuple[date, date] | None:
    normalized = normalize_semester(semester)
    if normalized is None:
        return None
    year, term = map(int, normalized.split("-"))
    next_year, next_term = (year, 2) if term == 1 else (year + 1, 1)
    return _semester_start(year, term), _semester_start(next_year, next_term)


def week_of(d: date, semester: str | None = None) -> int:
    bounds = _semester_bounds(semester) if semester is not None else None
    first_day = bounds[0] if bounds else settings.SEMESTER_START
    return (d - first_day).days // 7 + 1


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
    bounds = _semester_bounds(course.semester)
    today = now.astimezone(KST).date()
    return bool(bounds and bounds[0] <= today < bounds[1] and _current_slot(_schedules(course), now))


def next_class_at(course: Course, now: datetime) -> datetime | None:
    now = now.astimezone(KST)
    bounds = _semester_bounds(course.semester)
    if bounds is None or now.date() >= bounds[1]:
        return None
    first_day = max(now.date(), bounds[0])
    schedules = _schedules(course)
    for offset in range(8):
        d = first_day + timedelta(days=offset)
        if d >= bounds[1]:
            break
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


def session_bounds(class_session: ClassSession, now: datetime | None = None) -> tuple[datetime, datetime]:
    """차시의 시작·종료 시각 (KST).

    그 날짜 요일의 시간표를 쓴다.
    - 지금 진행 중인 시간이 있으면 그 시간 (같은 요일에 시간이 여러 개일 때 오후 수업 중이면 오후 시간)
    - 아니면 그날 첫 시작 ~ 마지막 종료
    - DEMO_ALWAYS_LIVE로 시간표가 없는 날에 만든 차시는 그날 00:00 ~ 다음 날 00:00
    """
    s = Session.object_session(class_session)
    if s is None:
        raise RuntimeError("class_session이 DB 세션에 붙어 있지 않습니다")
    d = class_session.date
    slots = s.exec(
        select(CourseSchedule)
        .where(CourseSchedule.course_id == class_session.course_id, CourseSchedule.day_of_week == d.weekday())
        .order_by(CourseSchedule.start_time)
    ).all()
    if not slots:
        start = _at(d, time(0, 0))
        return start, start + timedelta(days=1)
    now = (now or now_kst()).astimezone(KST)
    if now.date() == d:
        for slot in slots:
            if slot.start_time <= now.time() < slot.end_time:
                return _at(d, slot.start_time), _at(d, slot.end_time)
    return _at(d, slots[0].start_time), _at(d, max(slot.end_time for slot in slots))


MAX_SCHEDULES = 14  # 요일마다 두 시간씩


def parse_schedules(entries, prefix: str = "") -> list[tuple[int, time, time]]:
    """강의 등록 시간표 검사. entries는 day_of_week, start_time, end_time("HH:MM")을 가진 객체들.

    같은 요일에 여러 시간을 넣을 수 있지만 서로 겹치면 안 된다.
    """
    parsed = []
    for e in entries:
        start, end = time.fromisoformat(e.start_time), time.fromisoformat(e.end_time)
        if start >= end:
            api_error(400, "INVALID_SCHEDULE_TIME", prefix + "수업 종료 시간은 시작 시간보다 늦어야 합니다")
        parsed.append((e.day_of_week, start, end))
    parsed.sort()
    for (d1, _, e1), (d2, s2, _) in zip(parsed, parsed[1:]):
        if d1 == d2 and s2 < e1:
            api_error(400, "OVERLAPPING_SCHEDULE", prefix + f"{DAY_NAMES[d1]}요일 수업 시간이 서로 겹칩니다")
    return parsed


def _get_or_create_session(session: Session, course: Course, d: date) -> ClassSession:
    stmt = select(ClassSession).where(ClassSession.course_id == course.id, ClassSession.date == d)
    found = session.exec(stmt).first()
    if found:
        return found
    cs = ClassSession(course_id=course.id, date=d, week=week_of(d, course.semester))
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
    course = session.get(Course, course_id)
    if course is None:
        api_error(404, "NOT_FOUND", "과목을 찾을 수 없습니다")
    if not is_live(course, now):
        api_error(409, "NOT_IN_CLASS", "지금은 수업 시간이 아닙니다")
    return _get_or_create_session(session, course, now.astimezone(KST).date())
