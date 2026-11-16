"""인증 메일 발송 (A).

보내는 방법은 설정에 따라 정해진다. 위에서부터 먼저 맞는 것을 쓴다.

1. MAIL_WEBHOOK_URL과 MAIL_WEBHOOK_SECRET이 있으면 Google Apps Script 중계로 보낸다 (배포용).
   Railway는 Pro 요금제가 아니면 SMTP 포트(465·587)로 나가는 연결을 막는다. HTTPS는 열려 있어서
   Apps Script 웹 앱(scripts/mail_relay.gs)에 HTTPS로 요청하면 Apps Script가 Gmail로 대신 보낸다.
2. SMTP_USER와 SMTP_PASSWORD가 있으면 Gmail SMTP로 보낸다 (로컬 개발용).
3. 둘 다 없으면 메일을 보내지 않고 코드를 서버 로그에 찍는다 (개발용).

MAIL_WEBHOOK_*는 공유 파일(app/config.py)을 건드리지 않으려고 환경변수에서 직접 읽는다.
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
SUBJECT = "[익명실명] 인증 코드"
TIMEOUT = 15  # Apps Script는 첫 호출이 몇 초 걸릴 수 있다


def _send_webhook(url: str, secret: str, to: str, code: str) -> None:
    """Apps Script 웹 앱에 POST한다.

    Apps Script는 실행 후 결과를 googleusercontent.com 주소로 302 리다이렉트해서 돌려준다.
    urllib은 POST의 302를 GET으로 따라가므로 그대로 결과 JSON을 받는다.
    """
    req = urllib.request.Request(
        url,
        data=json.dumps({"secret": secret, "to": to, "code": code}).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            raw = res.read()
    except urllib.error.HTTPError as e:
        logger.error("메일 중계 실패: HTTP %s", e.code)
        raise RuntimeError("메일 발송 실패") from e

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # 웹 앱 접근 권한이 "모든 사용자"가 아니면 로그인 HTML이 온다
        logger.error("메일 중계 응답이 JSON이 아님 (웹 앱 접근 권한 확인): %s", raw[:120])
        raise RuntimeError("메일 발송 실패")
    if not result.get("ok"):
        logger.error("메일 중계 실패: %s", result.get("error"))
        raise RuntimeError("메일 발송 실패")


def _send_smtp(to: str, code: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = settings.SMTP_USER
    msg["To"] = to
    msg.set_content(f"인증 코드: {code}\n\n3분 안에 입력해 주세요.")
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT) as smtp:
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


def send_verification_code(to: str, code: str) -> None:
    url = os.getenv("MAIL_WEBHOOK_URL", "").strip()
    secret = os.getenv("MAIL_WEBHOOK_SECRET", "").strip()

    if url and secret:
        _send_webhook(url, secret, to, code)
    elif settings.SMTP_USER and settings.SMTP_PASSWORD:
        _send_smtp(to, code)
    else:
        logger.warning("[dev] 메일 설정 없음: %s 인증 코드 %s", to, code)
