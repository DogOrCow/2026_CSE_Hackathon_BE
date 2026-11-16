"""모든 오류는 {"code": ..., "message": ...} 형태로 나간다 (SPEC 6장 공통 오류).

사용법:
    from app.errors import api_error
    api_error(409, "NOT_IN_CLASS", "지금은 수업 시간이 아닙니다")   # 바로 예외를 던진다
"""

from typing import NoReturn

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra):
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra  # 예: QUESTION_HELD의 reason


def api_error(status: int, code: str, message: str, **extra) -> NoReturn:
    raise ApiError(status, code, message, **extra)


_DEFAULT_CODES = {
    400: ("BAD_REQUEST", "잘못된 요청입니다"),
    401: ("UNAUTHORIZED", "로그인이 필요합니다"),
    403: ("FORBIDDEN", "권한이 없습니다"),
    404: ("NOT_FOUND", "찾을 수 없습니다"),
    405: ("METHOD_NOT_ALLOWED", "허용되지 않은 메서드입니다"),
}


def _body(code: str, message: str, **extra) -> dict:
    return {"code": code, "message": message, **extra}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message, **exc.extra))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code, message = _DEFAULT_CODES.get(exc.status_code, ("ERROR", "오류가 발생했습니다"))
        return JSONResponse(status_code=exc.status_code, content=_body(code, message))

    # FastAPI 기본은 422지만 422는 QUESTION_HELD 전용이라 요청 형식 오류는 400으로 낸다.
    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=400, content=_body("VALIDATION_ERROR", "요청 형식이 올바르지 않습니다"))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return JSONResponse(status_code=500, content=_body("INTERNAL_ERROR", "서버 오류가 발생했습니다"))
