"""질문 검열 판단 모델 Jev (SPEC 4장 검열, B-4).

judge(content, course_name) -> {"passed": bool, "reason": "OFF_TOPIC" | "PERSONAL" | "ABUSIVE" | None}
이름·인자·반환 형태는 0단계와 같다. questions.py가 그대로 쓴다.

구조
- _call_jev(): Jev API를 실제로 호출하는 유일한 부분 (TypeSafe 공식 문서 https://docs.typesafe.ai).
- decide():    Jev 결과에 4장 판정 규칙을 적용한다. 순수 함수라 평가 스크립트도 쓴다.
- judge():     키 확인, 3초 타임아웃, 실패 시 통과, 로그를 맡는다.

로그에는 질문 본문을 남기지 않는다. 선택지와 확신도만 남긴다.
"""

import json
import logging
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass

from app.config import settings

log = logging.getLogger("uvicorn.error")

# TypeSafe API (https://docs.typesafe.ai/api/system-one.md)
JEV_URL = "https://api.typesafe.ai/v1/systemone"
# 고정 버전. jev-latest 같은 별칭은 새 릴리스 때 바뀌어 발표 중 동작이 달라질 수 있다.
# JUDGE_MODEL로 바꿀 수 있다. (https://docs.typesafe.ai/models.md)
DEFAULT_MODEL = "jev-1.14.0"
QUESTION_ID = "category"

ON_TOPIC = "ON_TOPIC"
HOLD_CHOICES = ("OFF_TOPIC", "PERSONAL", "ABUSIVE")
CHOICES = (ON_TOPIC, *HOLD_CHOICES)

# Jev Choice 질문. 선택지 이름과 설명이 모두 모델에 전달된다.
INSTRUCTIONS = (
    "A university student typed `question` anonymously during a live lecture of the course "
    "`course_name`, to be shown to the professor and classmates. Which category does it fall into?"
)
CRITERIA = {
    "ON_TOPIC": "A question or comment about the course: lecture content, concepts, examples, "
                "assignments, exams, or how the class is run",
    "OFF_TOPIC": "Unrelated to the course or the class: small talk, jokes, chatting, other subjects",
    "PERSONAL": "Singles out a specific person (a classmate, the professor, a TA) "
                "to mock, criticize, expose, or gossip about them",
    "ABUSIVE": "Contains profanity, insults, slurs, or hateful language",
}

TIMEOUT_SECONDS = 3.0

PASS = {"passed": True, "reason": None}

# 호출이 3초를 넘기면 기다리지 않고 통과시킨다. 늦은 호출은 백그라운드에서 끝난다.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="jev")


@dataclass
class JevResult:
    probabilities: dict[str, float]  # 선택지별 확률
    confidence: float                # 확신도

    @property
    def top(self) -> str:
        return max(self.probabilities, key=self.probabilities.get)


def model_id() -> str:
    return settings.JUDGE_MODEL or DEFAULT_MODEL


def _call_jev(content: str, course_name: str) -> JevResult:
    """Jev에 질문과 과목명을 넘기고 선택지별 확률과 확신도를 받는다.

    요청: POST /v1/systemone, Authorization: Bearer <키>
          {"model", "state": {...}, "questions": {id: {"type": "choice", "instructions", "criteria"}}}
    응답: {"model", "answers": {id: {"type": "choice", "choice", "confidence", "probabilities"}}, "usage"}
    """
    body = {
        "model": model_id(),
        "state": {"course_name": course_name, "question": content},
        "questions": {
            QUESTION_ID: {"type": "choice", "instructions": INSTRUCTIONS, "criteria": CRITERIA},
        },
    }
    req = urllib.request.Request(
        JEV_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.JUDGE_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())

    answer = data["answers"][QUESTION_ID]
    return JevResult(
        probabilities={k: float(v) for k, v in answer["probabilities"].items()},
        confidence=float(answer["confidence"]),
    )


def decide(result: JevResult, threshold: float) -> dict:
    """SPEC 4장 판정 규칙.

    - 가장 높은 선택지가 ON_TOPIC → 통과
    - 나머지 셋 중 하나이고 확신도 ≥ 기준값 → 보류 (그 선택지가 사유)
    - 확신도 < 기준값 → 통과 (애매한 질문을 막는 쪽이 손해가 더 크다)
    """
    top = result.top
    if top == ON_TOPIC:
        return PASS
    if top not in HOLD_CHOICES:
        log.warning("Jev가 알 수 없는 선택지를 돌려줌: %s → 통과", top)
        return PASS
    if result.confidence >= threshold:
        return {"passed": False, "reason": top}
    return PASS


def judge(content: str, course_name: str) -> dict:
    if not settings.JUDGE_API_KEY:
        return PASS  # 개발용: 키가 없으면 호출하지 않는다

    future = _executor.submit(_call_jev, content, course_name)
    try:
        result = future.result(timeout=TIMEOUT_SECONDS)
    except FutureTimeout:
        log.warning("Jev 응답 %.0f초 초과 → 통과", TIMEOUT_SECONDS)
        return PASS
    except urllib.error.HTTPError as e:  # 401 키 오류, 429 한도 초과 등. 응답 본문은 남기지 않는다
        log.warning("Jev HTTP %s → 통과", e.code)
        return PASS
    except Exception as e:  # 네트워크, 응답 형식 오류 모두 통과
        log.warning("Jev 호출 실패(%s) → 통과", type(e).__name__)
        return PASS

    verdict = decide(result, settings.JUDGE_THRESHOLD)
    log.info(
        "Jev 판정 top=%s confidence=%.2f → %s",
        result.top, result.confidence, "통과" if verdict["passed"] else "보류",
    )
    return verdict
