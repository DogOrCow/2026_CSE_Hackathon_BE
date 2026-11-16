# 익명실명 Backend

수업 중에 손들기 어려운 질문을 학생이 **익명**으로 올리고, 교수가 질문 받는 시간에 확인해 말로 답하는 웹앱의 백엔드입니다.

- 2026 경북대 컴퓨터학부 해커톤 출품작 (제출 마감: **11월 24일(화) 12:00**)
- 데모 범위: 과목 1~2개, 수강생 수십 명, 서버 한 대

> 전체 명세는 [docs/SPEC.md](docs/SPEC.md)가 기준입니다. 이 README는 요약이며, 내용이 다르면 SPEC.md를 따릅니다.
> AI에게 작업을 시킬 때는 SPEC.md 11장의 공통 규칙과 작업별 프롬프트를 사용합니다.

## 설계 원칙

1. 질문은 화면에 익명으로 보인다. 작성자 정보는 서버에만 남고 **어떤 응답에도 담기지 않는다.**
2. 질문은 등록 전에 판단 모델(Jev)이 수업 관련 질문인지 확인한다.
3. 질문은 수업 시간에만 올릴 수 있고, 올라온 순서대로 보인다.
4. 과목 코드는 학기 초에 한 번만 입력한다.

## 기술 스택

| 영역 | 선택 | 비고 |
| --- | --- | --- |
| 프레임워크 | FastAPI | |
| DB | PostgreSQL | 배포 서비스 제공 DB 사용 |
| ORM | SQLModel | 모델 하나로 테이블과 응답 형식을 함께 정의 |
| 인증 | JWT | 사용자 ID·역할 포함, 7일 유효, 리프레시 토큰 없음 |
| 메일 | Gmail SMTP | 앱 비밀번호 사용 |
| 실시간 | SSE | 웹소켓·Redis 미사용 |
| 판단 모델 | Jev (TypeSafe AI) | `judge(content, course_name)` 함수 하나 뒤에 둠 |
| 배포 | Railway 또는 Render + Docker | **인스턴스 1개 고정, 자동 확장 끔** |
| 프론트 배포 | Vercel | 별도 저장소 |

## 프로젝트 구조

```
app/
  main.py            # 라우터 등록(/api), CORS, GET /health      [공유]
  config.py          # 환경변수 설정                              [공유]
  db.py              # SQLModel 엔진, 세션 의존성                  [공유]
  models.py          # 테이블 8개                                 [공유]
  errors.py          # api_error(), 공통 예외 핸들러               [공유]
  deps.py            # get_current_user, require_* 권한 의존성     [A]
  routers/
    auth.py          # 인증                                       [A]
    courses.py       # 과목 목록·등록                              [A]
    history.py       # 지난 차시                                   [A]
    live.py          # 수업 중 질문 목록                            [B]
    questions.py     # 질문 등록, 나도 궁금, 답변 완료               [B]
    stream.py        # SSE                                        [B]
  services/
    schedule.py      # 수업 중 판별, get_live_session()            [A]
    mail.py          # 인증 메일                                   [A]
    security.py      # 비밀번호 해시, JWT                           [A]
    judge.py         # Jev 판단 모델                               [B]
    broadcast.py     # 과목별 SSE 구독자 관리, publish()            [B]
scripts/
  seed.py            # 초기 데이터 (python -m scripts.seed)          [A]
  judge_eval.py      # 판단 모델 기준값 평가                         [B]
tests/
  judge_cases.csv    # 평가용 문장                                  [B]
Dockerfile                                                         [A]
```

`[공유]` 파일은 0단계 이후 고정입니다. 바꿔야 하면 **코드를 고치기 전에 상대에게 먼저 알립니다.**

## 실행

```bash
cp .env.example .env        # 값 채우기
pip install -r requirements.txt
python -m scripts.seed      # 여러 번 실행해도 중복되지 않음
uvicorn app.main:app --reload
```

로컬 PostgreSQL이 없으면 Docker로 띄우거나, `DATABASE_URL`을 비워 sqlite(`./dev.db`)로 개발할 수 있습니다.

```bash
docker run -d --name anon-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=anon -p 5432:5432 postgres:16-alpine
```

seed 계정 (비밀번호 공통 `password1234`): 교수 `prof@knu.ac.kr`(id 1), 학생 `student1~3@knu.ac.kr`(id 2~4).
과목은 데이터베이스 `COMP0322`(화·목 10:30), 운영체제 `COMP0312`(월·수 13:00).
로그인 구현 전에는 `ENV=dev`에서 `X-Debug-User: 2` 헤더로 사용자를 지정합니다.

### 0단계 뼈대 사용 규칙

- 오류: `api_error(409, "NOT_IN_CLASS", "지금은 수업 시간이 아닙니다")`는 호출하면 바로 예외를 던집니다. 추가 필드는 키워드로 (`reason="OFF_TOPIC"`).
- 요청 형식 오류(FastAPI 기본 422)는 `400 VALIDATION_ERROR`로 나갑니다. 422는 `QUESTION_HELD` 전용입니다.
- 권한: `require_student`, `require_professor`는 `Depends()`로, `require_course_member(session, user, course_id)`, `require_course_professor(...)`는 핸들러 안에서 직접 부릅니다 (과목 객체 반환).
- 시각: `app.config.now_kst()`를 씁니다. DB 시각 컬럼은 timezone 포함.
- 비밀번호 해시는 bcrypt (seed와 A-1 `security.py`가 같아야 함).
- 라우터는 동기 함수, `broadcast.publish()`와 `judge()`도 동기 함수입니다.

또는 Docker:

```bash
docker build -t anon-realname-be .
docker run --env-file .env -p 8000:8000 anon-realname-be
```

서버가 뜨면 `/docs`(Swagger)와 `/health`에서 확인할 수 있습니다.

### 환경변수

저장소에는 올리지 않습니다 (`.env.example`만 커밋).

| 이름 | 용도 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 접속 주소 |
| `JWT_SECRET` | 토큰 서명 키 |
| `SMTP_USER`, `SMTP_PASSWORD` | 인증 메일 발송 계정. 비어 있으면 코드를 서버 로그에 출력 (개발용) |
| `JUDGE_API_KEY` | Jev 호출 키. 비어 있으면 호출 없이 통과 (개발용) |
| `CORS_ORIGINS` | 허용할 프론트 주소 |
| `TZ` | `Asia/Seoul`. **없으면 수업 중 판별이 9시간 어긋남** |
| `SEMESTER_START` | 학기 시작일. 주차 계산에 사용 |
| `ENV` | `dev` 또는 `prod`. `dev`일 때만 `X-Debug-User` 헤더로 사용자 지정 가능. **배포는 반드시 `prod`** |
| `DEMO_ALWAYS_LIVE` | `true`면 시간표와 무관하게 모든 과목을 수업 중으로 보고 오늘 차시 사용 (발표·개발용) |
| `JUDGE_THRESHOLD` | 선택. 확신도 기준값, 기본 `0.6` |
| `JUDGE_MODEL` | 선택. Jev 모델 ID (고정 버전 사용) |

## API

모든 경로는 `/api`로 시작합니다. 인증이 필요한 요청은 `Authorization: Bearer <토큰>` 헤더를 보내고, 본문은 JSON입니다.

### 인증

| 메서드 | 경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- | --- |
| POST | `/auth/email-code` | email | 204 | 400 `INVALID_EMAIL_DOMAIN`, 409 `EMAIL_TAKEN` |
| POST | `/auth/signup` | email, code, password, agreed | 201 access_token, role, name | 400 `INVALID_CODE`, `CODE_EXPIRED`, `WEAK_PASSWORD`, `AGREEMENT_REQUIRED` |
| POST | `/auth/login` | email, password | 200 access_token, role, name | 401 `INVALID_CREDENTIALS` |
| GET | `/me` | – | 200 email, name, role | 401 `UNAUTHORIZED` |

- 메일은 `knu.ac.kr` 도메인만. 인증 코드는 6자리, 3분 유효, 재요청 시 이전 코드 무효.
- 비밀번호 8자 이상, 익명 정책 동의 필수. 가입 계정은 항상 `STUDENT` (교수 계정은 seed로 등록).
- `name`은 교수면 이름, 학생이면 메일의 `@` 앞부분.

### 과목

| 메서드 | 경로 | 권한 | 성공 | 오류 |
| --- | --- | --- | --- | --- |
| GET | `/courses` | 학생: 등록 과목 / 교수: 담당 과목 | 200 과목 배열 | – |
| POST | `/courses/enroll` | 학생, 요청 `code` | 201 과목 | 404 `COURSE_NOT_FOUND`, 409 `ALREADY_ENROLLED` |

```json
{
  "id": 1,
  "name": "데이터베이스",
  "code": "COMP0322",
  "professor_name": "서지환",
  "schedule_text": "화·목 10:30",
  "is_live": true,
  "next_class_at": "2026-11-19T10:30:00+09:00",
  "live_question_count": 7
}
```

`code`는 교수에게만, `live_question_count`는 수업 중이 아니면 0.

### 수업 중

| 메서드 | 경로 | 권한 | 성공 | 오류 |
| --- | --- | --- | --- | --- |
| GET | `/courses/{id}/live` | 등록 학생, 담당 교수 | 200 session, questions | 409 `NOT_IN_CLASS` |
| POST | `/courses/{id}/questions` | 등록 학생, 요청 `content` | 201 질문 | 400 `INVALID_LENGTH`, 409 `NOT_IN_CLASS`, 422 `QUESTION_HELD` (+ reason) |
| PUT | `/questions/{id}/vote` | 등록 학생 | 200 vote_count, voted: true | 403 `OWN_QUESTION`, 409 `ALREADY_ANSWERED`, `NOT_IN_CLASS` |
| DELETE | `/questions/{id}/vote` | 등록 학생 | 200 vote_count, voted: false | 409 `ALREADY_ANSWERED`, `NOT_IN_CLASS` |
| PUT | `/questions/{id}/answered` | 담당 교수 | 200 answered: true | 409 `NOT_IN_CLASS` |
| DELETE | `/questions/{id}/answered` | 담당 교수 | 200 answered: false | 409 `NOT_IN_CLASS` |
| GET | `/courses/{id}/stream` | 등록 학생, 담당 교수 | SSE 스트림 | 409 `NOT_IN_CLASS` |

```json
{
  "session": {
    "id": 42, "date": "2026-11-17", "week": 11,
    "starts_at": "2026-11-17T10:30:00+09:00",
    "ends_at": "2026-11-17T11:45:00+09:00"
  },
  "questions": [
    {
      "id": 318,
      "content": "3정규형이랑 BCNF 차이가 아직 헷갈려요.",
      "created_at": "2026-11-17T10:52:10+09:00",
      "vote_count": 12, "voted": true, "mine": false, "answered": false
    }
  ]
}
```

- 질문은 `created_at` 오름차순. 궁금 수나 답변 여부로 순서를 바꾸지 않음.
- 교수에게는 `voted`, `mine`이 항상 `false`.
- vote / answered는 같은 요청을 두 번 보내도 같은 결과 (멱등).

### 지난 차시

| 메서드 | 경로 | 권한 | 성공 |
| --- | --- | --- | --- |
| GET | `/courses/{id}/sessions` | 등록 학생, 담당 교수 | 200 차시 배열 (id, date, week, question_count), 최신순 |
| GET | `/sessions/{id}/questions` | 등록 학생, 담당 교수 | 200 질문 배열 (id, content, created_at, vote_count), 시간순 |

지난 차시 응답에는 `answered`, `voted`, `mine`을 넣지 않습니다.

### 오류 형식

```json
{ "code": "NOT_IN_CLASS", "message": "지금은 수업 시간이 아닙니다" }
```

| 상태 | 코드 | 언제 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 토큰 없음·만료 |
| 403 | `FORBIDDEN` | 등록하지 않은 과목, 담당이 아닌 과목, 역할 불일치 |
| 404 | `NOT_FOUND` | 없는 과목·차시·질문 |

오류는 반드시 `app/errors.py`의 `api_error(status, code, message)`로만 냅니다.

## 실시간 (SSE)

`GET /api/courses/{id}/stream` 하나로 변경을 받습니다 (서버 → 클라이언트 단방향).

| 이벤트 | 데이터 | 시점 |
| --- | --- | --- |
| `question.created` | id, content, created_at, vote_count, answered | 검열 통과 후 저장 직후 |
| `question.voted` | id, vote_count | 나도 궁금 / 취소 직후 |
| `question.answered` | id, answered | 답변 완료 / 되돌리기 직후 |
| `session.ended` | – | 수업 종료 시각 (`DEMO_ALWAYS_LIVE`면 안 보냄) |

- 이벤트는 모두에게 같으므로 `mine`, `voted`, `author_id`를 넣지 않음.
- 브라우저 `EventSource`는 헤더를 못 보내므로 프론트는 `fetch`로 스트림을 열어 `Authorization` 헤더를 보냄.
- 20초마다 `: ping` 주석 줄 전송. 응답 헤더 `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- 재연결 시 클라이언트가 `/live`로 목록을 통째로 다시 맞춤 (놓친 이벤트 재전송 없음).
- 과목 ID별 연결 목록을 **메모리**에 두므로 서버는 반드시 한 대.

## 정책

### 익명
- 질문에 작성자 ID를 저장하되, **어떤 API 응답에도 작성자 ID·메일·이름을 담지 않는다** (교수용 포함).
- "내가 쓴 질문"은 서버가 비교해 `mine` 불리언으로만 내려준다.
- 가입 시 "운영 정책을 어긴 글은 운영진이 작성자를 확인할 수 있다"에 동의를 받는다. 신고 기능은 없다.

### 검열 (질문 등록 요청 안에서 순서대로)
1. **규칙 검사**: 앞뒤 공백 제거 후 1~200자. 어기면 400 `INVALID_LENGTH`.
2. **판단 모델(Jev)**: 질문 본문과 과목명으로 `ON_TOPIC` / `OFF_TOPIC` / `PERSONAL` / `ABUSIVE` 중 판정.

| 상황 | 처리 |
| --- | --- |
| 최고 선택지가 `ON_TOPIC` | 저장 + 실시간 이벤트 |
| 최고 선택지가 나머지 셋 중 하나, 확신도 ≥ 기준값 | 저장하지 않고 422 `QUESTION_HELD` + 사유 코드 |
| 확신도 < 기준값 | 통과 |
| 3초 타임아웃·호출 실패 | 통과 (경고 로그) |

- 기준값은 0.6에서 시작, 테스트 문장 약 30개로 조정 (`scripts/judge_eval.py`).
- 로그에 질문 본문은 남기지 않고 선택지와 확신도만 남긴다.
- `judge()` 반환: `{"passed": bool, "reason": str | None}`.

### 수업 중 판별과 차시
- 과목마다 요일·시작·종료 시각을 저장하고 서버 시각(Asia/Seoul)과 비교.
- 차시는 (과목, 날짜)로 유일. 수업 시간에 첫 요청이 올 때 없으면 생성 (동시 요청에도 하나만).
- 수업 종료 후에는 질문 등록·나도 궁금·답변 완료 모두 막힘. 보강·휴강은 범위 밖.

### 나도 궁금과 답변 완료
- 나도 궁금은 (질문, 사용자)로 유일, 개수는 조회 시 집계.
- 내가 쓴 질문, 답변 완료된 질문에는 누를 수 없음.
- 답변 완료·되돌리기는 그 과목의 담당 교수만.

## 데이터 모델

모든 테이블은 `id`(자동 증가)와 `created_at`을 가집니다.

| 테이블 | 컬럼 | 제약 |
| --- | --- | --- |
| users | email, password_hash, name, role (`STUDENT`/`PROFESSOR`) | email 유일. name은 교수만 값 있음 |
| email_verifications | email, code(6자리), expires_at, verified_at | 메일당 최신 1건만 유효 |
| courses | code, name, professor_id, semester | code 유일 |
| course_schedules | course_id, day_of_week (0=월~6=일), start_time, end_time | |
| enrollments | user_id, course_id | (user_id, course_id) 유일 |
| class_sessions | course_id, date, week | (course_id, date) 유일 |
| questions | session_id, author_id, content(≤200), answered_at (nullable) | session_id 인덱스 |
| question_votes | question_id, user_id | (question_id, user_id) 유일 |

- 답변 여부는 `answered_at`이 널인지로 판단 (되돌리기는 널로).
- 보류된 질문은 저장하지 않으므로 상태 컬럼 없음.
- `week`는 `SEMESTER_START`로부터 계산.

## 작업 분담과 일정

백엔드 2명. 0단계(뼈대, 약 30분)만 같이 하고 이후 따로 진행합니다.

### 0단계 임시 함수
| 함수 | 임시 동작 | 교체 |
| --- | --- | --- |
| `get_current_user()` | `X-Debug-User` 헤더의 ID로 사용자 조회 | A: JWT 검증 (`ENV=dev`에서는 헤더도 유지) |
| `get_live_session(session, course_id)` | 오늘 차시를 없으면 만들어 반환 | A: 시간표 판별 (임시 동작은 `DEMO_ALWAYS_LIVE`로 유지) |
| `judge(content, course_name)` | 항상 통과 | B: Jev 연동 |

함수 이름과 반환값은 교체 후에도 같습니다.

### 1단계
| 순서 | A: 기반·인증·과목 | B: 질문·판단·실시간 |
| --- | --- | --- |
| 1 | 빈 서버 배포 | 질문 목록 `/live`, 질문 등록 |
| 2 | 메일 인증, 가입, 로그인, `/me` | 나도 궁금, 답변 완료 |
| 3 | `get_current_user()` JWT 교체 | SSE와 브로드캐스트 |
| 4 | 과목 목록, 과목 등록 | Jev 연동, 기준값 조정 |
| 5 | 수업 중 판별, `get_live_session()` 교체 | 수업 종료 이벤트 |
| 6 | 지난 차시 API 2개, 권한 점검 | 프론트 연동 지원 |

### 마감
| 언제 | 무엇을 |
| --- | --- |
| 11/22 (일) | 1단계 전부, 프론트와 연결해 13개 화면이 실제 데이터로 동작 |
| 11/23 (월) | 통합 테스트, 버그 수정, 발표 자료. 전원이 휴대폰으로 한 차시 끝까지 돌려보기 |
| 11/24 (화) 12:00 | 제출 |

### 작업 규칙
- 기능 하나가 끝나면 바로 `main`에 올린다. 브랜치를 오래 끌지 않는다.
- API가 하나 끝날 때마다 배포 주소의 `/docs`를 프론트 담당에게 공유한다.
- 시각은 모두 Asia/Seoul, 응답은 `+09:00`이 붙은 ISO 8601.
- 경로·필드 이름·상태 코드·오류 코드는 명세와 글자 그대로 맞춘다.

## 배포 체크리스트

- [ ] 인스턴스 1개 고정, 자동 확장 끔
- [ ] 빈 프로젝트를 첫날 배포해 경로 확보
- [ ] 무료 요금제가 서버를 재우면 발표 전에 미리 한 번 열어두기
- [ ] 어떤 응답에도 작성자 ID·메일·이름이 없다
- [ ] 학생 토큰으로 답변 완료 API를 호출하면 403
- [ ] 서버 시각이 한국 시간이고, `ENV=prod`라서 `X-Debug-User`가 먹히지 않는다

## 범위 밖

신고·관리 화면, 비밀번호 찾기·탈퇴, 교수의 과목·시간표 등록 화면, 보강·휴강, LMS 연동, 질문 수정·삭제, 댓글·글 답변, 푸시·메일 알림.

## 미정 사항

- [ ] Jev 확신도 기준값 (테스트 문장 30개로 결정)
- [ ] 판단 모델 무응답 시 통과/차단 (현재 통과)
- [ ] 프론트 스택과 담당자
- [ ] 데모 과목·시간표·학기 시작일
- [ ] 발표 때 `DEMO_ALWAYS_LIVE`를 켤지, 데모 과목 시간표를 발표 시간에 맞출지
