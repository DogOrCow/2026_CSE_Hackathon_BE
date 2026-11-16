"""인증 메일 발송 (A).

보내는 방법은 설정에 따라 정해진다. 위에서부터 먼저 맞는 것을 쓴다.

1. GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN이 있으면 Gmail API(HTTPS)로 보낸다 (배포용).
   Railway는 Pro 요금제가 아니면 SMTP 포트(465·587)로 나가는 연결을 막아서, 배포 서버에서는 이 방법을 쓴다.
   보내는 주소는 MAIL_FROM, 없으면 SMTP_USER. 갱신 토큰을 발급받은 Gmail 계정과 같아야 한다.
   갱신 토큰은 scripts/gmail_token.py로 한 번 발급받는다.
2. SMTP_USER와 SMTP_PASSWORD가 있으면 Gmail SMTP로 보낸다 (로컬 개발용).
3. 둘 다 없으면 메일을 보내지 않고 코드를 서버 로그에 찍는다 (개발용).

GMAIL_*, MAIL_FROM은 공유 파일(app/config.py)을 건드리지 않으려고 환경변수에서 직접 읽는다.
"""

import base64
import json
import logging
import os
import smtplib
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("uvicorn.error")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SENDER_NAME = "익명실명"
SUBJECT = "[익명실명] 인증 코드"
TIMEOUT = 10

_token_lock = threading.Lock()
_token: dict = {"value": None, "expires_at": 0.0}


def _message(sender: str, to: str, code: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = f"{SENDER_NAME} <{sender}>"
    msg["To"] = to
    msg.set_content(f"인증 코드: {code}\n\n3분 안에 입력해 주세요.")
    return msg


def _post(url: str, data: bytes, headers: dict) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        # Google 오류 응답에는 오류 종류와 설명만 있다 (토큰·인증 코드 없음)
        logger.error("Gmail API 실패: %s %s %s", url.split("/")[2], e.code, e.read()[:300].decode(errors="replace"))
        raise RuntimeError("메일 발송 실패") from e


def _access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """갱신 토큰으로 액세스 토큰을 받는다. 만료 1분 전까지 재사용한다."""
    with _token_lock:
        if _token["value"] and time.time() < _token["expires_at"] - 60:
            return _token["value"]
        body = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode()
        data = _post(TOKEN_URL, body, {"content-type": "application/x-www-form-urlencoded"})
        _token["value"] = data["access_token"]
        _token["expires_at"] = time.time() + int(data.get("expires_in", 3600))
        return _token["value"]


def _send_gmail_api(client_id: str, client_secret: str, refresh_token: str, sender: str, to: str, code: str) -> None:
    token = _access_token(client_id, client_secret, refresh_token)
    raw = base64.urlsafe_b64encode(_message(sender, to, code).as_bytes()).decode()
    _post(
        SEND_URL,
        json.dumps({"raw": raw}).encode(),
        {"authorization": f"Bearer {token}", "content-type": "application/json"},
    )


def _send_smtp(to: str, code: str) -> None:
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT) as smtp:
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(_message(settings.SMTP_USER, to, code))


def send_verification_code(to: str, code: str) -> None:
    client_id = os.getenv("GMAIL_CLIENT_ID", "").strip()
    client_secret = os.getenv("GMAIL_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN", "").strip()
    sender = os.getenv("MAIL_FROM", "").strip() or settings.SMTP_USER

    if client_id and client_secret and refresh_token and sender:
        _send_gmail_api(client_id, client_secret, refresh_token, sender, to, code)
    elif settings.SMTP_USER and settings.SMTP_PASSWORD:
        _send_smtp(to, code)
    else:
        logger.warning("[dev] 메일 설정 없음: %s 인증 코드 %s", to, code)
