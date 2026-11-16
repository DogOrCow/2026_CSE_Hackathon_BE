"""질문 검열 판단 모델 (SPEC 4장 검열). 0단계 임시 버전.

B-4에서 Jev 연동으로 바꾸되, 이름·인자·반환 형태는 그대로 둔다.
반환: {"passed": bool, "reason": "OFF_TOPIC" | "PERSONAL" | "ABUSIVE" | None}
"""


def judge(content: str, course_name: str) -> dict:
    return {"passed": True, "reason": None}
