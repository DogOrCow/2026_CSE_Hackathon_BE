"""질문 등록·나도 궁금·답변 완료 (B). SPEC 6장 수업 중, 4장 검열·나도 궁금과 답변 완료."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import now_kst
from app.db import get_session
from app.deps import get_current_user, require_course_member, require_course_professor, require_student
from app.errors import api_error
from app.models import ClassSession, Course, Question, QuestionVote, User
from app.routers.live import question_event_data, question_out, vote_counts
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


# ---------- 나도 궁금, 답변 완료 (B-2) ----------

def _load_question(session: Session, question_id: int) -> tuple[Question, ClassSession]:
    q = session.get(Question, question_id)
    if q is None:
        api_error(404, "NOT_FOUND", "질문을 찾을 수 없습니다")
    return q, session.get(ClassSession, q.session_id)


def _require_live(session: Session, q: Question, cs: ClassSession) -> None:
    """질문이 속한 차시가 지금 수업 중인 차시가 아니면 409 NOT_IN_CLASS."""
    live = get_live_session(session, cs.course_id)  # 수업 중이 아니면 여기서 409
    if live.id != q.session_id:
        api_error(409, "NOT_IN_CLASS", "지금은 수업 시간이 아닙니다")


def _vote_count(session: Session, question_id: int) -> int:
    return vote_counts(session, [question_id]).get(question_id, 0)


def _find_vote(session: Session, question_id: int, user_id: int) -> QuestionVote | None:
    return session.exec(
        select(QuestionVote).where(QuestionVote.question_id == question_id, QuestionVote.user_id == user_id)
    ).first()


@router.put("/questions/{id}/vote")
def vote(id: int, user: User = Depends(require_student), session: Session = Depends(get_session)):
    q, cs = _load_question(session, id)
    require_course_member(session, user, cs.course_id)
    _require_live(session, q, cs)
    if q.author_id == user.id:
        api_error(403, "OWN_QUESTION", "내가 쓴 질문에는 누를 수 없습니다")
    if q.answered_at is not None:
        api_error(409, "ALREADY_ANSWERED", "이미 답변된 질문입니다")

    changed = False
    if _find_vote(session, id, user.id) is None:
        session.add(QuestionVote(question_id=id, user_id=user.id))
        try:
            session.commit()
            changed = True
        except IntegrityError:  # 같은 요청이 동시에 들어온 경우. 결과는 같다
            session.rollback()

    count = _vote_count(session, id)
    if changed:
        broadcast.publish(cs.course_id, "question.voted", {"id": id, "vote_count": count})
    return {"vote_count": count, "voted": True}


@router.delete("/questions/{id}/vote")
def unvote(id: int, user: User = Depends(require_student), session: Session = Depends(get_session)):
    q, cs = _load_question(session, id)
    require_course_member(session, user, cs.course_id)
    _require_live(session, q, cs)
    if q.answered_at is not None:
        api_error(409, "ALREADY_ANSWERED", "이미 답변된 질문입니다")

    existing = _find_vote(session, id, user.id)
    if existing is not None:
        session.delete(existing)
        session.commit()

    count = _vote_count(session, id)
    if existing is not None:
        broadcast.publish(cs.course_id, "question.voted", {"id": id, "vote_count": count})
    return {"vote_count": count, "voted": False}


def _set_answered(session: Session, user: User, question_id: int, answered: bool) -> dict:
    q, cs = _load_question(session, question_id)
    require_course_professor(session, user, cs.course_id)
    _require_live(session, q, cs)

    if (q.answered_at is not None) != answered:
        q.answered_at = now_kst() if answered else None
        session.add(q)
        session.commit()
        broadcast.publish(cs.course_id, "question.answered", {"id": q.id, "answered": answered})
    return {"answered": answered}


@router.put("/questions/{id}/answered")
def mark_answered(id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return _set_answered(session, user, id, True)


@router.delete("/questions/{id}/answered")
def unmark_answered(id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return _set_answered(session, user, id, False)
