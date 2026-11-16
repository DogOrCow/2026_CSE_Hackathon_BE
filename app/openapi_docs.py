"""Swagger(/docs) 문서 보정.

1. FastAPI 기본 문서의 422 HTTPValidationError를 지운다.
   실제로는 요청 형식 오류가 400 VALIDATION_ERROR로 나가고, 422는 QUESTION_HELD 전용이다 (errors.py).
2. 엔드포인트마다 실제로 나가는 오류 코드를 {code, message} 형태로 적는다 (SPEC 6장 + 구현).

API를 추가하거나 오류 코드를 바꾸면 ERRORS 표도 같이 고친다.
문서만 바꾸고 동작은 바꾸지 않는다.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# 거의 모든 인증 API에 붙는 공통 오류
AUTH = {401: ["UNAUTHORIZED"]}
MEMBER = {**AUTH, 403: ["FORBIDDEN"], 404: ["NOT_FOUND"]}
BODY = {400: ["VALIDATION_ERROR"]}

ERRORS: dict[tuple[str, str], dict[int, list[str]]] = {
    ("post", "/api/auth/email-code"): {400: ["INVALID_EMAIL_DOMAIN", "VALIDATION_ERROR"], 409: ["EMAIL_TAKEN"]},
    ("post", "/api/auth/signup"): {
        400: ["INVALID_CODE", "CODE_EXPIRED", "WEAK_PASSWORD", "AGREEMENT_REQUIRED", "INVALID_EMAIL_DOMAIN", "VALIDATION_ERROR"],
        409: ["EMAIL_TAKEN"],
    },
    ("post", "/api/auth/login"): {**BODY, 401: ["INVALID_CREDENTIALS"]},
    ("get", "/api/me"): AUTH,
    ("get", "/api/courses"): AUTH,
    ("post", "/api/courses/enroll"): {
        **BODY, **AUTH, 403: ["FORBIDDEN"], 404: ["COURSE_NOT_FOUND"], 409: ["ALREADY_ENROLLED"],
    },
    ("get", "/api/courses/{id}/sessions"): MEMBER,
    ("get", "/api/sessions/{id}/questions"): MEMBER,
    ("get", "/api/courses/{id}/live"): {**MEMBER, 409: ["NOT_IN_CLASS"]},
    ("post", "/api/courses/{id}/questions"): {
        400: ["INVALID_LENGTH", "VALIDATION_ERROR"], **MEMBER, 409: ["NOT_IN_CLASS"], 422: ["QUESTION_HELD"],
    },
    ("put", "/api/questions/{id}/vote"): {
        **AUTH, 403: ["OWN_QUESTION", "FORBIDDEN"], 404: ["NOT_FOUND"], 409: ["ALREADY_ANSWERED", "NOT_IN_CLASS"],
    },
    ("delete", "/api/questions/{id}/vote"): {**MEMBER, 409: ["ALREADY_ANSWERED", "NOT_IN_CLASS"]},
    ("put", "/api/questions/{id}/answered"): {**MEMBER, 409: ["NOT_IN_CLASS"]},
    ("delete", "/api/questions/{id}/answered"): {**MEMBER, 409: ["NOT_IN_CLASS"]},
    ("get", "/api/courses/{id}/stream"): {**MEMBER, 409: ["NOT_IN_CLASS"]},
}

# 코드별 설명 (Swagger에 보이는 문구)
CODE_TEXT = {
    "VALIDATION_ERROR": "요청 본문이나 파라미터 형식이 틀림",
    "UNAUTHORIZED": "토큰이 없거나 만료됨",
    "FORBIDDEN": "등록하지 않은 과목, 담당이 아닌 과목, 역할이 맞지 않는 요청",
    "NOT_FOUND": "없는 과목·차시·질문",
    "INVALID_EMAIL_DOMAIN": "knu.ac.kr 메일이 아님",
    "EMAIL_TAKEN": "이미 가입한 메일",
    "INVALID_CODE": "인증 코드가 틀림",
    "CODE_EXPIRED": "인증 코드 3분 지남",
    "WEAK_PASSWORD": "비밀번호 8자 미만",
    "AGREEMENT_REQUIRED": "익명 정책 미동의",
    "INVALID_CREDENTIALS": "메일 또는 비밀번호가 틀림",
    "COURSE_NOT_FOUND": "없는 과목 코드",
    "ALREADY_ENROLLED": "이미 등록한 과목",
    "NOT_IN_CLASS": "지금은 수업 시간이 아님",
    "INVALID_LENGTH": "공백 제거 후 1~200자가 아님",
    "QUESTION_HELD": "판단 모델이 등록을 보류함. reason: OFF_TOPIC | PERSONAL | ABUSIVE",
    "OWN_QUESTION": "내가 쓴 질문에는 나도 궁금을 누를 수 없음",
    "ALREADY_ANSWERED": "이미 답변 완료된 질문",
}

ERROR_SCHEMA = {
    "title": "ErrorResponse",
    "type": "object",
    "required": ["code", "message"],
    "properties": {
        "code": {"type": "string", "description": "프론트는 이 값으로 분기한다"},
        "message": {"type": "string"},
        "reason": {
            "type": "string",
            "enum": ["OFF_TOPIC", "PERSONAL", "ABUSIVE"],
            "description": "QUESTION_HELD일 때만",
        },
    },
}


def _response(codes: list[str]) -> dict:
    lines = "\n".join(f"- `{c}`: {CODE_TEXT.get(c, '')}" for c in codes)
    examples = {}
    for c in codes:
        value = {"code": c, "message": CODE_TEXT.get(c, "")}
        if c == "QUESTION_HELD":
            value["reason"] = "OFF_TOPIC"
        examples[c] = {"summary": c, "value": value}
    return {
        "description": lines,
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}, "examples": examples}},
    }


def install_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        comps = schema.setdefault("components", {}).setdefault("schemas", {})
        comps["ErrorResponse"] = ERROR_SCHEMA
        comps.pop("HTTPValidationError", None)
        comps.pop("ValidationError", None)

        for path, ops in schema.get("paths", {}).items():
            for method, op in ops.items():
                responses = op.setdefault("responses", {})
                responses.pop("422", None)
                for status, codes in sorted(ERRORS.get((method, path), {}).items()):
                    responses[str(status)] = _response(codes)

        stream = schema["paths"].get("/api/courses/{id}/stream", {}).get("get")
        if stream:
            stream["responses"]["200"] = {
                "description": "SSE 스트림 (text/event-stream). 이벤트: question.created, question.voted, "
                "question.answered, session.ended. 20초마다 `: ping`. Swagger에서는 응답이 끝나지 않으니 curl -N으로 확인",
                "content": {"text/event-stream": {"schema": {"type": "string"}}},
            }

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
