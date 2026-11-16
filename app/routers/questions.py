"""질문 등록·나도 궁금·답변 완료 (B). SPEC 6장 수업 중, 4장 검열."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.deps import require_course_member, require_student
from app.errors import api_error
from app.models import Course, Question, User
from app.routers.live import question_event_data, question_out
from app.services import broadcast
from app.services.judge import judge
from app.services.schedule import get_live_session

router = APIRouter(tags=["questions"])

MAX_LENGTH = 200

# 화면 문구는 프론트가 reason 코드에 맞춰 보여준다. message는 기본값.
HELD_MESSAGES = {
    "OFF_TOPIC": "수업과 관련 없는 질문으로 보여 등록이 보류되었습니다",
    "PERSONAL": "특정 사람을 언급하거나 비방하는 내용으로 보여 등록이 보류되었습니다",
    "ABUSIVE": "욕설이나 혐오 표현으로 보여 등록이 보류되었습니다",
}


class QuestionCreate(BaseModel):
    # 길이 제한은 모델에 두지 않는다. 그래야 초과 시 VALIDATION_ERROR가 아니라 INVALID_LENGTH가 나간다.
    content: str


@router.post("/courses/{id}/questions", status_code=201)
def create_question(
    id: int,
    body: QuestionCreate,
    user: User = Depends(require_student),
    session: Session = Depends(get_session),
):
    course: Course = require_course_member(session, user, id)
    # get_live_session()은 충돌 시 rollback 하므로 질문을 add 하기 전에 부른다.
    cs = get_live_session(session, id)

    content = body.content.strip()
    if not 1 <= len(content) <= MAX_LENGTH:
        api_error(400, "INVALID_LENGTH", f"질문은 1자 이상 {MAX_LENGTH}자 이하로 써주세요")

    verdict = judge(content, course.name)
    if not verdict["passed"]:
        reason = verdict["reason"]
        api_error(
            422,
            "QUESTION_HELD",
            HELD_MESSAGES.get(reason, "등록이 보류되었습니다"),
            reason=reason,
        )

    q = Question(session_id=cs.id, author_id=user.id, content=content)
    session.add(q)
    session.commit()
    session.refresh(q)

    broadcast.publish(course.id, "question.created", question_event_data(q, 0))
    return question_out(q, user, vote_count=0, voted=False)
