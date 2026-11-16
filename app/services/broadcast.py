"""SSE 브로드캐스트 (SPEC 7장).

과목 ID별 구독자 큐를 메모리에 둔다. 그래서 서버는 반드시 한 대(워커 1개)로 띄운다.

- subscribe(course_id) -> queue      스트림을 연 쪽(이벤트 루프 안)에서 부른다
- unsubscribe(course_id, queue)
- publish(course_id, event, data)    라우터(동기 함수, threadpool)에서 부른다

publish()는 다른 스레드에서 불려도 되도록 loop.call_soon_threadsafe로 큐에 넣는다.
큐가 가득 찬 느린 구독자는 끊는다: 큐를 비우고 종료 신호(None)를 넣는다.
"""

import asyncio
import json
import logging
import threading

log = logging.getLogger(__name__)

QUEUE_SIZE = 100


class Subscriber(asyncio.Queue):
    """구독자 큐. 값은 SSE 메시지 문자열, None이면 연결을 닫으라는 신호."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__(maxsize=QUEUE_SIZE)
        self.loop = loop
        self.dropped = False


_subscribers: dict[int, set[Subscriber]] = {}
_lock = threading.Lock()


def format_event(event: str, data: dict | None) -> str:
    return f"event: {event}\ndata: {json.dumps(data or {}, ensure_ascii=False)}\n\n"


def subscribe(course_id: int) -> Subscriber:
    q = Subscriber(asyncio.get_running_loop())
    with _lock:
        _subscribers.setdefault(course_id, set()).add(q)
    return q


def unsubscribe(course_id: int, queue: Subscriber) -> None:
    with _lock:
        subs = _subscribers.get(course_id)
        if subs is not None:
            subs.discard(queue)
            if not subs:
                del _subscribers[course_id]


def subscriber_count(course_id: int) -> int:
    with _lock:
        return len(_subscribers.get(course_id, ()))


def _deliver(queue: Subscriber, message: str) -> None:
    # 이벤트 루프 스레드에서 실행된다
    if queue.dropped:
        return
    try:
        queue.put_nowait(message)
    except asyncio.QueueFull:
        queue.dropped = True
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(None)
        log.warning("느린 SSE 구독자를 끊었습니다")


def publish(course_id: int, event: str, data: dict) -> None:
    message = format_event(event, data)
    with _lock:
        targets = list(_subscribers.get(course_id, ()))
    for q in targets:
        try:
            q.loop.call_soon_threadsafe(_deliver, q, message)
        except RuntimeError:  # 루프가 이미 닫힘
            unsubscribe(course_id, q)
