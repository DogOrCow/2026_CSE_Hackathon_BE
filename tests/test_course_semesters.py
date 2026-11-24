import unittest
from datetime import date, datetime, time
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine, select

from app.config import KST
from app.errors import ApiError
from app.models import ClassSession, Course, CourseSchedule, Enrollment, Question, Role, User
from app.routers.admin import AdminCoursesRequest, upsert_courses
from app.services import schedule


class CourseSemesterTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)
        start_setting = patch.object(schedule.settings, "SEMESTER_START", date(2026, 9, 3))
        demo_setting = patch.object(schedule.settings, "DEMO_ALWAYS_LIVE", False)
        start_setting.start()
        demo_setting.start()
        self.addCleanup(start_setting.stop)
        self.addCleanup(demo_setting.stop)
        professor = User(email="prof@knu.ac.kr", name="담당 교수", password_hash="", role=Role.PROFESSOR)
        student = User(email="student@knu.ac.kr", password_hash="", role=Role.STUDENT)
        self.session.add_all([professor, student])
        self.session.flush()
        self.professor_id = professor.id
        self.course = Course(code="COMP100", name="기존 강의", semester="2026년 2학기", professor_id=professor.id)
        self.session.add(self.course)
        self.session.flush()
        self.session.add(CourseSchedule(course_id=self.course.id, day_of_week=0, start_time=time(13), end_time=time(14)))
        self.session.add(Enrollment(user_id=student.id, course_id=self.course.id))
        past = ClassSession(course_id=self.course.id, date=date(2026, 11, 9), week=10)
        self.session.add(past)
        self.session.flush()
        self.session.add(Question(session_id=past.id, author_id=student.id, content="지난 학기 질문"))
        self.session.commit()

    def registration(self, code, semester, professor_email="prof@knu.ac.kr"):
        return {
            "code": code, "name": "신규 강의", "semester": semester,
            "professor_email": professor_email, "professor_name": "교수",
            "schedules": [{"day_of_week": 1, "start_time": "09:00", "end_time": "10:00"}],
        }

    def test_cross_semester_collision_preserves_old_records_and_rejects_whole_batch(self):
        request = AdminCoursesRequest(courses=[
            self.registration("COMP200", "2027-1", "new@knu.ac.kr"),
            self.registration("COMP100", "2027-1", "other@knu.ac.kr"),
        ])
        with self.assertRaises(ApiError) as caught:
            upsert_courses(request, self.session)
        self.assertEqual((caught.exception.status, caught.exception.code), (409, "COURSE_CODE_TAKEN"))
        self.session.refresh(self.course)
        self.assertEqual((self.course.name, self.course.semester, self.course.professor_id),
                         ("기존 강의", "2026년 2학기", self.professor_id))
        self.assertEqual([row.code for row in self.session.exec(select(Course))], ["COMP100"])
        self.assertEqual(len(self.session.exec(select(User)).all()), 2)
        self.assertEqual(self.session.exec(select(CourseSchedule)).one().day_of_week, 0)
        self.assertEqual(self.session.exec(select(Enrollment)).one().course_id, self.course.id)
        self.assertEqual(self.session.exec(select(Question)).one().content, "지난 학기 질문")

    def test_same_semester_legacy_label_can_be_updated(self):
        result = upsert_courses(
            AdminCoursesRequest(courses=[self.registration("COMP100", "2026-2")]), self.session
        )
        self.assertEqual(result["updated"], 1)
        self.assertEqual(self.session.exec(select(Enrollment)).one().course_id, self.course.id)

    def test_live_session_is_limited_to_the_course_semester(self):
        for day, expected in [(date(2026, 8, 31), False), (date(2026, 11, 23), True), (date(2027, 3, 1), False)]:
            with self.subTest(day=day):
                now = datetime.combine(day, time(13, 30), tzinfo=KST)
                self.assertEqual(schedule.is_live(self.course, now), expected)
                with patch.object(schedule, "now_kst", return_value=now):
                    if expected:
                        self.assertEqual(schedule.get_live_session(self.session, self.course.id).date, day)
                    else:
                        with self.assertRaises(ApiError) as caught:
                            schedule.get_live_session(self.session, self.course.id)
                        self.assertEqual(caught.exception.code, "NOT_IN_CLASS")
                        self.assertIsNone(schedule.find_today_session(self.session, self.course.id, now))

    def test_next_class_starts_inside_the_course_semester(self):
        before = datetime(2026, 8, 24, 10, tzinfo=KST)
        self.assertEqual(schedule.next_class_at(self.course, before), datetime(2026, 9, 7, 13, tzinfo=KST))
        after_last = datetime(2027, 2, 22, 14, tzinfo=KST)
        self.assertIsNone(schedule.next_class_at(self.course, after_last))

    def test_future_course_first_class_has_its_own_week_one(self):
        self.course.semester = "2027-1"
        now = datetime(2027, 3, 1, 13, 30, tzinfo=KST)
        with patch.object(schedule, "now_kst", return_value=now):
            self.assertEqual(schedule.get_live_session(self.session, self.course.id).week, 1)
