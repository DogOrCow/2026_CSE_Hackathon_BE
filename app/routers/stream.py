"""실시간 SSE (B). SPEC 7장.

GET /api/courses/{id}/stream
- 등록 학생, 담당 교수만. 수업 중이 아니면 409 NOT_IN_CLASS
- 20초마다 ": ping" 주석 줄
- 차시 종료 시각에 session.ended를 보내고 닫는다 (DEMO_ALWAYS_LIVE면 보내지 않음)
- 이벤트에 mine, voted, author_id를 넣지 않는다 (publish 하는 쪽에서 이미 빼고 보낸다)

DB 연결은 권한·차시 확인에만 쓰고 스트림을 열기 전에 반납한다.
연결마다 DB 커넥션을 붙잡고 있으면 수강생 수십 명이 접속할 때 커넥션 풀이 바닥난다.
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.config import now_kst, settings
from app.db import get_session
from app.deps import get_current_user, require_course_member
from app.models import User
from app.services import broadcast
from app.services.schedule import get_live_session, session_bounds

router = APIRouter(tags=["stream"])

PING_INTERVAL = 20.0  # 초

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


async def event_stream(course_id: int, ends_at: datetime | None):
    """ends_at이 None이면 수업 종료를 보내지 않는다 (DEMO_ALWAYS_LIVE)."""
    queue = broadcast.subscribe(course_id)
    try:
        yield ": connected\n\n"
        while True:
            timeout = PING_INTERVAL
            if ends_at is not None:
                remaining = (ends_at - now_kst()).total_seconds()
                if remaining <= 0:
                    yield broadcast.format_event("session.ended", None)
                    return
                timeout = min(timeout, remaining)

            try:
                message = await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue

            if message is None:  # 느린 구독자라 끊김
                return
            yield message
    finally:
        # 클라이언트가 끊으면 여기서 CancelledError와 함께 정리된다
        broadcast.unsubscribe(course_id, queue)


@router.get("/courses/{id}/stream")
def open_stream(
    id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    require_course_member(session, user, id)
    cs = get_live_session(session, id)
    _, ends_at = session_bounds(cs)
    session.close()  # 스트림 동안 DB 커넥션을 잡지 않는다

    return StreamingResponse(
        event_stream(id, None if settings.DEMO_ALWAYS_LIVE else ends_at),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
