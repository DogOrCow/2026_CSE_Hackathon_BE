"""인증 메일 발송 (A). Gmail SMTP + 앱 비밀번호.

SMTP_USER나 SMTP_PASSWORD가 비어 있으면 메일을 보내지 않고 코드를 서버 로그에 찍는다 (개발용).
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("uvicorn.error")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def send_verification_code(to: str, code: str) -> None:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("[dev] SMTP 미설정: %s 인증 코드 %s", to, code)
        return

    msg = EmailMessage()
    msg["Subject"] = "[익명실명] 인증 코드"
    msg["From"] = settings.SMTP_USER
    msg["To"] = to
    msg.set_content(f"인증 코드: {code}\n\n3분 안에 입력해 주세요.")

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)
