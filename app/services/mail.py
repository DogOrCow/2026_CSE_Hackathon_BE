"""인증 메일 발송 (A).

보내는 방법은 설정에 따라 정해진다. 위에서부터 먼저 맞는 것을 쓴다.

1. BREVO_API_KEY가 있으면 Brevo HTTPS API로 보낸다 (배포용).
   Railway는 Pro 요금제가 아니면 SMTP 포트(465·587)로 나가는 연결을 막아서, 배포 서버에서는 이 방법을 쓴다.
   보내는 주소는 MAIL_FROM, 없으면 SMTP_USER. Brevo에서 발신자(sender)로 인증된 주소여야 한다.
2. SMTP_USER와 SMTP_PASSWORD가 있으면 Gmail SMTP로 보낸다 (로컬 개발용).
3. 둘 다 없으면 메일을 보내지 않고 코드를 서버 로그에 찍는다 (개발용).

BREVO_API_KEY, MAIL_FROM은 공유 파일(app/config.py)을 건드리지 않으려고 환경변수에서 직접 읽는다.
"""

import json
import logging
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("uvicorn.error")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
SENDER_NAME = "익명실명"
SUBJECT = "[익명실명] 인증 코드"
TIMEOUT = 10


def _body(code: str) -> str:
    return f"인증 코드: {code}\n\n3분 안에 입력해 주세요."


def _send_brevo(api_key: str, sender: str, to: str, code: str) -> None:
    payload = {
        "sender": {"name": SENDER_NAME, "email": sender},
        "to": [{"email": to}],
        "subject": SUBJECT,
        "textContent": _body(code),
    }
    req = urllib.request.Request(
        BREVO_URL,
        data=json.dumps(payload).encode(),
        headers={"api-key": api_key, "content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            if res.status >= 300:
                raise RuntimeError(f"Brevo 응답 {res.status}")
    except urllib.error.HTTPError as e:
        # 응답 본문에는 오류 코드와 사유만 있다 (키·코드 없음)
        logger.error("Brevo 메일 발송 실패: %s %s", e.code, e.read()[:300].decode(errors="replace"))
        raise RuntimeError("메일 발송 실패") from e


def _send_smtp(to: str, code: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = settings.SMTP_USER
    msg["To"] = to
    msg.set_content(_body(code))
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT) as smtp:
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


def send_verification_code(to: str, code: str) -> None:
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    sender = os.getenv("MAIL_FROM", "").strip() or settings.SMTP_USER

    if api_key and sender:
        _send_brevo(api_key, sender, to, code)
    elif settings.SMTP_USER and settings.SMTP_PASSWORD:
        _send_smtp(to, code)
    else:
        logger.warning("[dev] 메일 설정 없음: %s 인증 코드 %s", to, code)
