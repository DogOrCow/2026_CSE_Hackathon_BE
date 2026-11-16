"""비밀번호 해시와 JWT (A).

- 비밀번호: bcrypt. scripts/seed.py와 같은 방식이라 seed 계정으로 로그인된다.
- JWT: HS256, 7일 유효. payload는 sub(사용자 ID 문자열), role, iat, exp.
  공유 파일(requirements.txt)을 건드리지 않으려고 표준 라이브러리로 HS256만 직접 구현했다.
"""

import base64
import hashlib
import hmac
import json
from datetime import timedelta

import bcrypt

from app.config import now_kst, settings

TOKEN_TTL = timedelta(days=7)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(signing_input: bytes) -> str:
    return _b64encode(hmac.new(settings.JWT_SECRET.encode(), signing_input, hashlib.sha256).digest())


def create_access_token(user_id: int, role: str) -> str:
    now = int(now_kst().timestamp())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": now + int(TOKEN_TTL.total_seconds())}
    head = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{head}.{body}".encode()
    return f"{head}.{body}.{_sign(signing_input)}"


def decode_access_token(token: str) -> dict | None:
    """서명과 만료를 확인하고 payload를 돌려준다. 잘못된 토큰이면 None."""
    try:
        head, body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(f"{head}.{body}".encode())):
            return None
        if json.loads(_b64decode(head)).get("alg") != "HS256":
            return None
        payload = json.loads(_b64decode(body))
        if int(payload["exp"]) <= int(now_kst().timestamp()):
            return None
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
