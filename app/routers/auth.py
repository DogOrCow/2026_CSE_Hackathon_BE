"""인증 (A). SPEC 6장 인증, 3장 S-01·S-02·P-01.

교수 가입: role=PROFESSOR로 가입하려면 이름과 교수 가입 코드가 필요하다.
교수 메일도 @knu.ac.kr이라 메일 인증만으로는 학생과 구분할 수 없어서, 팀이 교수님께 따로 전달하는 코드로 막는다.
코드는 환경변수 PROFESSOR_SIGNUP_CODE에만 둔다 (공유 파일 config.py를 건드리지 않으려고 직접 읽음).
비어 있으면 교수 가입 자체를 막는다.
"""

import hmac
import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, delete, select

from app.config import KST, now_kst
from app.db import get_session
from app.deps import get_current_user
from app.errors import api_error
from app.models import EmailVerification, Role, User
from app.services.mail import send_verification_code
from app.services.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])

ALLOWED_DOMAIN = "knu.ac.kr"
CODE_TTL = timedelta(minutes=3)
MIN_PASSWORD_LENGTH = 8
MAX_NAME_LENGTH = 50


class EmailCodeRequest(BaseModel):
    email: str


class SignupRequest(BaseModel):
    email: str
    code: str
    password: str
    agreed: bool
    # 아래는 교수 가입일 때만. 학생은 보내지 않아도 되고, 보내도 name은 저장하지 않는다.
    role: Role = Role.STUDENT
    name: str | None = None
    professor_code: str | None = None


def _check_professor_signup(body: SignupRequest) -> str:
    """교수 가입 조건을 확인하고 저장할 이름을 돌려준다."""
    expected = os.getenv("PROFESSOR_SIGNUP_CODE", "").strip()
    if not expected:
        api_error(403, "PROFESSOR_SIGNUP_DISABLED", "지금은 교수 회원가입을 받지 않습니다")
    if not hmac.compare_digest((body.professor_code or "").strip().encode(), expected.encode()):
        api_error(403, "INVALID_PROFESSOR_CODE", "교수 가입 코드가 올바르지 않습니다")
    name = (body.name or "").strip()
    if not 1 <= len(name) <= MAX_NAME_LENGTH:
        api_error(400, "INVALID_NAME", f"이름은 1자 이상 {MAX_NAME_LENGTH}자 이하로 입력해 주세요")
    return name


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    role: Role
    name: str


class MeResponse(BaseModel):
    email: str
    name: str
    role: Role


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _check_domain(email: str) -> None:
    local, sep, domain = email.partition("@")
    if not sep or not local or domain != ALLOWED_DOMAIN:
        api_error(400, "INVALID_EMAIL_DOMAIN", "knu.ac.kr 메일만 쓸 수 있습니다")


def _aware(dt: datetime) -> datetime:
    # sqlite는 시간대를 버리고 저장한다. 저장한 값은 KST 기준이므로 KST로 붙인다.
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def display_name(user: User) -> str:
    """교수는 users.name, 학생은 메일의 @ 앞부분."""
    if user.role == Role.PROFESSOR and user.name:
        return user.name
    return user.email.split("@", 1)[0]


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        role=user.role,
        name=display_name(user),
    )


@router.post("/auth/email-code", status_code=204)
def request_email_code(body: EmailCodeRequest, session: Session = Depends(get_session)):
    email = _normalize_email(body.email)
    _check_domain(email)
    if session.exec(select(User).where(User.email == email)).first():
        api_error(409, "EMAIL_TAKEN", "이미 가입한 메일입니다")

    # 다시 요청하면 이전 코드는 무효: 메일당 최신 1건만 남긴다
    session.exec(delete(EmailVerification).where(EmailVerification.email == email))
    code = f"{secrets.randbelow(10**6):06d}"
    session.add(EmailVerification(email=email, code=code, expires_at=now_kst() + CODE_TTL))
    session.commit()

    send_verification_code(email, code)
    return Response(status_code=204)


@router.post("/auth/signup", status_code=201, response_model=TokenResponse)
def signup(body: SignupRequest, session: Session = Depends(get_session)):
    email = _normalize_email(body.email)
    _check_domain(email)
    if not body.agreed:
        api_error(400, "AGREEMENT_REQUIRED", "익명 정책에 동의해야 가입할 수 있습니다")
    if len(body.password) < MIN_PASSWORD_LENGTH:
        api_error(400, "WEAK_PASSWORD", "비밀번호는 8자 이상이어야 합니다")
    if session.exec(select(User).where(User.email == email)).first():
        api_error(409, "EMAIL_TAKEN", "이미 가입한 메일입니다")
    # 교수 가입 조건은 인증 코드를 쓰기 전에 확인한다 (코드가 틀려도 인증 코드는 그대로 남음)
    professor_name = _check_professor_signup(body) if body.role == Role.PROFESSOR else None

    verification = session.exec(
        select(EmailVerification)
        .where(EmailVerification.email == email)
        .order_by(EmailVerification.id.desc())
    ).first()
    if verification is None or verification.verified_at is not None or verification.code != body.code.strip():
        api_error(400, "INVALID_CODE", "인증 코드가 올바르지 않습니다")
    now = now_kst()
    if _aware(verification.expires_at) <= now:
        api_error(400, "CODE_EXPIRED", "인증 코드가 만료되었습니다")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        role=Role.PROFESSOR if professor_name else Role.STUDENT,
        name=professor_name,  # 학생은 이름을 받지 않는다 (SPEC 5장)
    )
    verification.verified_at = now
    session.add(user)
    session.add(verification)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        api_error(409, "EMAIL_TAKEN", "이미 가입한 메일입니다")
    session.refresh(user)
    return _token_response(user)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)):
    email = _normalize_email(body.email)
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        api_error(401, "INVALID_CREDENTIALS", "메일 또는 비밀번호가 올바르지 않습니다")
    return _token_response(user)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(email=user.email, name=display_name(user), role=user.role)
