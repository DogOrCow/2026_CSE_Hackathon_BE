"""SSE 브로드캐스트 (SPEC 7장). 0단계 임시 버전: 아무 일도 하지 않는다.

B-3에서 과목별 구독자 큐로 구현하되, publish()의 이름과 인자는 그대로 둔다.
주의: 라우터는 동기 함수(threadpool)에서 publish()를 부른다.
"""


def publish(course_id: int, event: str, data: dict) -> None:
    return None
