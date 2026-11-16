"""SPEC 5장: 테이블 8개. 모든 테이블은 id(자동 증가)와 created_at을 갖는다."""

from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.config import now_kst


def _created_at() -> datetime:
    return Field(default_factory=now_kst, sa_type=DateTime(timezone=True), nullable=False)


class Role(str, Enum):
    STUDENT = "STUDENT"
    PROFESSOR = "PROFESSOR"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    password_hash: str
    name: str | None = Field(default=None, max_length=50)  # 교수만 값이 있다
    role: Role = Field(sa_column=Column(SAEnum(Role, name="user_role"), nullable=False))
    created_at: datetime = _created_at()


class EmailVerification(SQLModel, table=True):
    __tablename__ = "email_verifications"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, max_length=255)  # 메일당 최신 1건만 유효
    code: str = Field(min_length=6, max_length=6)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))
    verified_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = _created_at()


class Course(SQLModel, table=True):
    __tablename__ = "courses"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=20)
    name: str = Field(max_length=100)
    professor_id: int = Field(foreign_key="users.id", index=True)
    semester: str = Field(max_length=20)
    created_at: datetime = _created_at()


class CourseSchedule(SQLModel, table=True):
    __tablename__ = "course_schedules"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    day_of_week: int = Field(ge=0, le=6)  # 0=월 ~ 6=일
    start_time: time
    end_time: time
    created_at: datetime = _created_at()


class Enrollment(SQLModel, table=True):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    created_at: datetime = _created_at()


class ClassSession(SQLModel, table=True):
    __tablename__ = "class_sessions"
    __table_args__ = (UniqueConstraint("course_id", "date"),)

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    date: date
    week: int
    created_at: datetime = _created_at()


class Question(SQLModel, table=True):
    __tablename__ = "questions"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="class_sessions.id", index=True)
    author_id: int = Field(foreign_key="users.id")  # 절대 응답에 담지 않는다
    content: str = Field(max_length=200)
    answered_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = _created_at()


class QuestionVote(SQLModel, table=True):
    __tablename__ = "question_votes"
    __table_args__ = (UniqueConstraint("question_id", "user_id"),)

    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="questions.id", index=True)
    user_id: int = Field(foreign_key="users.id")
    created_at: datetime = _created_at()
