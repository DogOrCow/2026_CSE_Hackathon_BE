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
ABUSIVE = "ABUSIVE"
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
    # 비속어는 가벼운 것도, 수업 얘기여도 막는다 (팀 결정). 글자만 겹치는 일반 단어는 예외로 명시.
    # 예시에 "시발"을 넣으면 "시발점"이 막혀서 뺐다.
    # 선정적인 글도 여기에 넣는다. 선택지가 없을 때는 OFF_TOPIC으로 분류되어 확신도가 낮으면 뚫렸다.
    "ABUSIVE": "Contains any profanity, swear word, or vulgar slang, including mild or casual ones and their "
               "abbreviations (e.g. 존나, 졸라, ㅈㄴ, 씨발, ㅅㅂ, 병신, 개빡치다, 미친), even when it is about "
               "the course or just expresses frustration; also insults, slurs, or hateful language; "
               "also sexual, obscene, or sexually suggestive content (e.g. 섹스, 야동, 야한 얘기, 19금, "
               "comments on someone's body). "
               "Ordinary words that only share syllables with a swear word are not profanity "
               "(e.g. 시발점 meaning starting point, 개념, 병렬, 미분)",
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
    # 욕설은 세게 막는다 (팀 결정): 가장 높은 판정이 ABUSIVE면 확신도와 상관없이 보류.
    # "시바시바"처럼 글자를 비틀면 확신도가 0.4~0.6으로 떨어져 기준값 규칙만으로는 뚫렸다.
    if top == ABUSIVE or result.confidence >= threshold:
        return {"passed": False, "reason": top}
    return PASS


# ---------- Jev 앞 욕설 단어 필터 ----------
# Jev 호출 없이 바로 막는다. Jev가 실패해 "통과"로 처리되는 경우(3초 초과, 429 등)에도 뻔한 욕설은 막힌다.
# 애매한 단어(미친, 시바 등)는 Jev에 맡긴다.
# 일반 욕설은 띄어쓰기를 살린 채로 찾는다. 띄어쓰기까지 지우면 "다시 발표", "기존 나머지"처럼
# 단어 경계를 넘어 글자가 이어진 정상 질문이 막힌다. "씨 발"처럼 띄어 쓴 욕설은 Jev가 판정한다.
PROFANITY = (
    "씨발", "씨빨", "씨팔", "시발", "시빨", "씌발", "쒸발",
    "병신", "븅신", "존나", "졸라", "좆", "개새끼", "개새",
    "지랄", "염병", "느금마", "애미뒤", "엿먹", "닥쳐",
    "tlqkf", "qudtls", "whssk",  # 한글 자판으로 친 씨발·병신·존나
    "fuck", "shit", "bitch",
    # 선정적인 단어. Jev는 잘 막지만, Jev 호출이 실패해 통과 처리되면 "섹스섹스"가 그대로 올라갔다.
    # "sex"(DB 컬럼 이름), "보지"·"자지"(보지 못하는, 자지 않는), "자위"(자위권)는 정상 질문과 겹쳐 Jev에 맡긴다.
    "섹스", "쎅스", "섹쓰", "쎅쓰", "야동", "야스", "포르노", "porn",
    "tprtm", "diehd",  # 한글 자판으로 친 섹스·야동
)
# 자모 줄임말은 띄어쓰기까지 지우고 찾는다 ("ㅅ ㅂ"). 정상 문장에 자모가 이어질 일이 드물다.
PROFANITY_JAMO = ("ㅅㅂ", "ㅆㅂ", "ㅅㅃ", "ㅂㅅ", "ㅄ", "ㅈㄴ", "ㄱㅅㄲ", "ㅈㄹ")
# 욕설과 글자만 겹치는 일반 단어. 지운 뒤에 검사한다.
NOT_PROFANITY = ("시발점", "시발역", "시발택시", "시발자동차", "졸라매", "졸라맨")


def _normalize(text: str) -> str:
    """소문자로 바꾸고 예외 단어·숫자·기호를 지운다. 띄어쓰기는 한 칸으로 남긴다."""
    t = text.lower()
    for word in NOT_PROFANITY:
        t = t.replace(word, "")
    t = "".join(ch for ch in t if ch.isalpha() or ch.isspace())  # "씨1발", "씨.발"은 붙는다
    return " ".join(t.split())


def has_profanity(text: str) -> bool:
    spaced = _normalize(text)
    if any(word in spaced for word in PROFANITY):
        return True
    packed = spaced.replace(" ", "")
    return any(word in packed for word in PROFANITY_JAMO)


def judge(content: str, course_name: str) -> dict:
    if has_profanity(content):
        log.info("욕설 단어 필터 → 보류")
        return {"passed": False, "reason": ABUSIVE}
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
