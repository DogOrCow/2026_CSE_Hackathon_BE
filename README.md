# 익명실명 Backend

수업 중에 손들기 어려운 질문을 학생이 **익명**으로 올리고, 교수가 질문 받는 시간에 확인해 말로 답하는 웹앱의 백엔드입니다.
2026 경북대 컴퓨터학부 해커톤 출품작이며, 제출 마감은 **11월 24일(화) 12:00**입니다.

| | 주소 |
| --- | --- |
| 배포 API | https://api-production-f55f4175.up.railway.app |
| Swagger 문서 | https://api-production-f55f4175.up.railway.app/docs |
| 프론트엔드 저장소 | https://github.com/DogOrCow/2026_CSE_Hackathon_FE |
| 전체 명세 | [docs/SPEC.md](docs/SPEC.md) |

> 이 README는 요약입니다. 내용이 다르면 [docs/SPEC.md](docs/SPEC.md)를 따릅니다.

## 현재 상태

명세의 API 15개에 교수 강의 추가, 운영자 강의 일괄 등록·조회를 더해 모두 18개가 구현되어 Railway에 배포되어 있습니다.

| 영역 | 내용 | 상태 |
| --- | --- | --- |
| 인증 | 메일 인증 코드, 학생·교수 가입, 로그인, JWT | 완료 (메일 발송은 [제약](#알려진-제약) 참고) |
| 과목 | 목록, 수강 등록, 교수 강의 추가, 운영자 강의 미리 등록 | 완료 |
| 수업 중 | 질문 목록·등록, 나도 궁금, 답변 완료 | 완료 |
| 실시간 | SSE 이벤트 4종, 수업 종료 | 완료 |
| 검열 | Jev 판단 모델 | 완료 (평가 문장 41개 전부 정답) |
| 지난 차시 | 차시 목록, 차시별 질문 | 완료 |
| 남은 일 | 프론트 연동, 통합 테스트 | [#9](https://github.com/DogOrCow/2026_CSE_Hackathon_BE/issues/9) |

## 전체 구성

```
브라우저 ──▶ Cloudflare Pages (프론트, /api 프록시) ──▶ Railway (FastAPI, 인스턴스 1개) ──▶ PostgreSQL
                                                              └──HTTPS──▶ TypeSafe Jev (질문 검열)
```

- 프론트는 같은 주소의 `/api`로 요청하고, Pages Function이 Railway로 전달합니다. 그래서 배포 환경에서는 CORS 설정이 없어도 됩니다.
- 실시간 연결(SSE)을 서버 메모리에 두기 때문에 **서버는 반드시 한 대**로 운영합니다.

## 기술 스택

| 영역 | 선택 |
| --- | --- |
| 프레임워크 | FastAPI (Python 3.12) |
| DB / ORM | PostgreSQL / SQLModel |
| 인증 | 자체 JWT (HS256, 7일), 비밀번호 bcrypt |
| 실시간 | SSE (웹소켓·Redis 미사용) |
| 검열 | [TypeSafe Jev](https://docs.typesafe.ai) `jev-1.14.0` (고정 버전) |
| 배포 | Railway, Dockerfile 빌드, `main` 브랜치 |

## 로컬 실행

Python 3.12와 Docker가 필요합니다. PostgreSQL이 없으면 `DATABASE_URL`을 비워 sqlite로 실행할 수 있습니다.

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

```bash
cp .env.example .env
```

```bash
.venv/bin/python -m scripts.seed
```

```bash
.venv/bin/uvicorn app.main:app --reload
```

http://localhost:8000/docs 에서 Swagger가 열립니다. seed는 여러 번 실행해도 중복되지 않습니다.

로컬 PostgreSQL을 쓰려면 아래처럼 띄우고 `.env`의 `DATABASE_URL`을 맞춥니다.

```bash
docker run -d --name anon-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=anon -p 5432:5432 postgres:16-alpine
```

개발 중에는 `.env`에 `DEMO_ALWAYS_LIVE=true`를 두면 시간표와 무관하게 모든 과목이 수업 중이 됩니다.

### 테스트 계정 (seed)

비밀번호는 모두 `password1234`입니다.

| 역할 | 메일 | id |
| --- | --- | --- |
| 교수 | `prof@knu.ac.kr` | 1 |
| 학생 | `student1@knu.ac.kr` ~ `student3@knu.ac.kr` | 2 ~ 4 |

과목은 데이터베이스 `COMP0322`(화·목 10:30~11:45)와 운영체제 `COMP0312`(월·수 13:00~14:15)입니다.

### Swagger로 테스트하기

1. `POST /api/auth/login`에 위 계정으로 로그인해 `access_token`을 받습니다.
2. 오른쪽 위 **Authorize**에 토큰을 넣습니다. `Bearer `는 빼고 토큰만 넣습니다.
3. 원하는 API에서 **Try it out → Execute**를 누릅니다.

`ENV=dev`일 때는 토큰 대신 `x-debug-user` 칸에 사용자 id를 넣어도 됩니다. 배포 환경(`prod`)에서는 이 칸이 보이지 않고 동작하지도 않습니다.

## 환경변수

실제 값은 `.env`(git 제외)와 Railway Variables에만 넣습니다. `.env.example`에는 예시만 둡니다.

| 이름 | 로컬 | 배포 | 설명 |
| --- | --- | --- | --- |
| `DATABASE_URL` | 비우면 sqlite | Railway Postgres 참조 | `postgres://`도 자동 변환 |
| `JWT_SECRET` | 아무 값 | 길고 무작위인 값 | 토큰 서명 키 |
| `ENV` | `dev` | **`prod`** | `dev`에서만 `X-Debug-User` 허용 |
| `CORS_ORIGINS` | `http://localhost:5173` | 직접 호출할 때만 | 쉼표로 구분. Pages 프록시를 쓰면 불필요 |
| `SEMESTER_START` | `2026-09-01` | 실제 학기 시작일 | 주차 계산 |
| `TZ` | `Asia/Seoul` | `Asia/Seoul` | 로그 시각용. 코드는 항상 KST로 계산 |
| `DEMO_ALWAYS_LIVE` | `true` 권장 | 발표 방식에 따라 | 모든 과목을 수업 중으로 봄 |
| `JUDGE_API_KEY` | 선택 | **필수** | Jev 키. 비면 검열 없이 모두 통과 |
| `JUDGE_MODEL` | 선택 | 선택 | 기본 `jev-1.14.0` |
| `JUDGE_THRESHOLD` | 선택 | 선택 | 기본 `0.6` |
| `SMTP_USER`, `SMTP_PASSWORD` | 선택 | **비워 둠** | 비면 인증 코드를 서버 로그에 출력 ([제약](#알려진-제약)) |
| `PROFESSOR_SIGNUP_CODE` | 선택 | 교수에게 따로 전달할 값 | 교수 가입 코드. 비면 교수 가입을 받지 않음 (미리 등록된 교수 메일은 코드 불필요) |
| `ADMIN_API_KEY` | 선택 | 팀만 아는 긴 값 | 운영자 강의 일괄 등록 API 키. 비면 운영자 API가 꺼짐 |

## API

모든 경로는 `/api`로 시작하고, 인증이 필요한 요청은 `Authorization: Bearer <토큰>`을 보냅니다. 요청·응답 필드와 예시는 Swagger와 [SPEC 6장](docs/SPEC.md#6-api-명세)에 있습니다.

| 영역 | 메서드와 경로 | 권한 |
| --- | --- | --- |
| 인증 | `POST /auth/email-code`, `POST /auth/signup`, `POST /auth/login`, `GET /me` | 누구나 / 로그인 |
| 과목 | `GET /courses` | 학생: 수강 과목, 교수: 담당 과목 |
| | `POST /courses/enroll` | 학생 |
| | `POST /courses` (강의 추가) | 교수 |
| 수업 중 | `GET /courses/{id}/live`, `GET /courses/{id}/stream` | 등록 학생, 담당 교수 |
| | `POST /courses/{id}/questions` | 등록 학생 |
| | `PUT`·`DELETE /questions/{id}/vote` | 등록 학생 |
| | `PUT`·`DELETE /questions/{id}/answered` | 담당 교수 |
| 지난 차시 | `GET /courses/{id}/sessions`, `GET /sessions/{id}/questions` | 등록 학생, 담당 교수 |

### 교수 회원가입

학생과 같은 `POST /api/auth/signup`에 아래 필드를 더 보냅니다. 교수 메일도 `@knu.ac.kr`이라 메일 인증만으로는 학생과 구분할 수 없어서, 팀이 교수님께 따로 전달하는 **교수 가입 코드**가 필요합니다.

```json
{ "email": "prof@knu.ac.kr", "code": "482913", "password": "...", "agreed": true,
  "role": "PROFESSOR", "name": "홍길동", "professor_code": "<PROFESSOR_SIGNUP_CODE 값>" }
```

- `role`을 빼면 학생으로 가입합니다.
- 코드가 틀리면 `403 INVALID_PROFESSOR_CODE`, 서버에 코드가 없으면 `403 PROFESSOR_SIGNUP_DISABLED`, 이름이 없으면 `400 INVALID_NAME`입니다.
- 가입한 교수는 `POST /api/courses`로 강의와 시간표를 추가합니다.
- 운영자가 [미리 등록한](#운영자-강의-미리-등록) 메일로 가입하면 가입 코드 없이 교수가 되고, 등록된 강의가 바로 보입니다.

### 운영자: 강의 미리 등록

강의계획서의 과목을 담당 교수 메일과 함께 미리 넣어 둡니다. 교수는 그 메일로 가입하면 과목 코드를 입력하지 않아도 자기 강의가 바로 보입니다.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/admin/courses` | 강의 일괄 등록. 과목 코드 기준으로 없으면 만들고 있으면 덮어씀 |
| GET | `/api/admin/courses` | 등록된 과목과 담당 교수 가입 여부(`PENDING` 가입 전 / `ACTIVE` 가입함) |
| PUT | `/api/admin/professors` | 교수 계정 비밀번호 설정 (목업·데모용). 계정이 없으면 만듦 |

- 헤더 `X-Admin-Key`에 환경변수 `ADMIN_API_KEY` 값을 넣습니다. Swagger에서는 **Authorize**의 `APIKeyHeader` 칸에 넣습니다. 값이 없으면 이 API는 꺼져 있습니다(`403 ADMIN_DISABLED`).
- 담당 교수가 아직 가입하지 않았으면, 그 메일로 **비밀번호 없는 교수 계정**을 만들어 강의를 붙여 둡니다. 비밀번호가 없어 로그인할 수 없습니다.
- 교수가 그 메일로 가입하면 비밀번호가 채워지면서 강의가 붙은 계정이 됩니다. 이 경우 교수 가입 코드는 필요 없습니다.
- 요청 전체를 먼저 검사하고 한 번에 저장합니다. 하나라도 틀리면 아무것도 저장하지 않습니다. 같은 요청을 다시 보내도 중복되지 않습니다.
- 같은 요일에 시간을 여러 개 넣을 수 있습니다(예: 화 10:30~11:45와 화 15:00~16:15). 서로 겹치면 `400 OVERLAPPING_SCHEDULE`입니다. 교수의 `POST /api/courses`도 같습니다.

목업 교수 계정에 바로 로그인하려면 비밀번호를 정해 줍니다. **실제 교수님 계정에는 쓰지 않습니다.** 비밀번호는 응답에 나오지 않습니다.

```json
PUT /api/admin/professors
{ "professors": [ { "email": "mock.prof@knu.ac.kr", "name": "목업 교수", "password": "8자 이상" } ] }
```
응답의 `status`는 `CREATED`(새로 만듦), `ACTIVATED`(가입 전 계정에 비밀번호를 넣음), `UPDATED`(이미 쓰던 계정의 비밀번호를 바꿈)입니다.

```json
{
  "courses": [
    {
      "code": "COMP0322-001", "name": "데이터베이스", "semester": "2026-2",
      "professor_email": "kim@knu.ac.kr", "professor_name": "김교수",
      "schedules": [
        { "day_of_week": 1, "start_time": "10:30", "end_time": "11:45" },
        { "day_of_week": 3, "start_time": "10:30", "end_time": "11:45" }
      ]
    }
  ]
}
```

### 오류 형식

오류는 항상 `{"code": "...", "message": "..."}`입니다. 프론트는 `code`로 분기합니다. API별 오류 코드는 Swagger의 각 API 응답 목록에 있습니다.

| 상태 | 대표 코드 |
| --- | --- |
| 400 | `VALIDATION_ERROR`(요청 형식), `INVALID_LENGTH`, `INVALID_CODE` 등 |
| 401 | `UNAUTHORIZED`, `INVALID_CREDENTIALS` |
| 403 | `FORBIDDEN`, `OWN_QUESTION` |
| 404 | `NOT_FOUND`, `COURSE_NOT_FOUND` |
| 409 | `NOT_IN_CLASS`, `ALREADY_ENROLLED`, `ALREADY_ANSWERED`, `EMAIL_TAKEN`, `COURSE_CODE_TAKEN` |
| 422 | `QUESTION_HELD` + `reason` (`OFF_TOPIC` / `PERSONAL` / `ABUSIVE`). 이 용도로만 씀 |

## 실시간 (SSE)

`GET /api/courses/{id}/stream` 하나로 변경을 받습니다. 브라우저 `EventSource`는 헤더를 못 보내므로 `fetch`로 열어 `Authorization` 헤더를 보냅니다.

| 이벤트 | 데이터 |
| --- | --- |
| `question.created` | id, content, created_at, vote_count, answered |
| `question.voted` | id, vote_count |
| `question.answered` | id, answered |
| `session.ended` | 없음 (`DEMO_ALWAYS_LIVE`면 안 보냄) |

- 20초마다 `: ping`을 보냅니다. 이벤트에는 `mine`, `voted`를 넣지 않습니다.
- 끊기면 `/live`를 다시 불러 목록을 맞춘 뒤 스트림을 다시 엽니다. Railway는 요청 하나를 오래 유지하지 않으므로 재연결은 꼭 필요합니다.
- 확인: `curl -N -H "Authorization: Bearer <토큰>" <주소>/api/courses/1/stream`

## 질문 검열 (Jev)

질문 등록 요청 안에서 순서대로 검사합니다.

1. **길이:** 앞뒤 공백을 자르고 1~200자인지 봅니다. 어기면 `400 INVALID_LENGTH`입니다.
2. **Jev 판정:** 질문과 과목명을 보내 `ON_TOPIC` / `OFF_TOPIC` / `PERSONAL` / `ABUSIVE` 중 하나로 판정받습니다.

| 결과 | 처리 |
| --- | --- |
| 가장 높은 선택지가 `ON_TOPIC` | 저장 + `question.created` 이벤트 |
| 가장 높은 선택지가 `ABUSIVE` (확신도 무관) | 저장하지 않고 `422 QUESTION_HELD` + `ABUSIVE` |
| `OFF_TOPIC`·`PERSONAL`, 확신도 ≥ 0.6 | 저장하지 않고 `422 QUESTION_HELD` + 사유 |
| 확신도 < 0.6, 3초 초과, 호출 오류, 키 없음 | 통과 (데모가 멈추지 않게) |

- **욕설과 선정적인 글은 강하게 막습니다.** "존나", "ㅅㅂ" 같은 가벼운 비속어, 성적인 내용은 수업 얘기여도 `ABUSIVE`이고 확신도와 상관없이 막습니다. "시발점", "개념"처럼 글자만 겹치는 단어는 막지 않습니다.
- **Jev 앞에 욕설 단어 필터**가 있습니다. 띄어쓰기·숫자·기호를 걷어낸 뒤 핵심 욕설이 있으면 Jev 없이 바로 막습니다. "시발시발", "씨1발", "시 발", "ㅅ.ㅂ", 영문 자판 "tlqkf" 같은 우회도 막히고, Jev가 실패해도 뚫리지 않습니다.
- 잡담(`OFF_TOPIC`)은 확신도가 낮으면 통과될 수 있습니다 (팀 결정).
- 로그에는 질문 본문을 남기지 않습니다.
- 평가: `tests/judge_cases.csv`(56문장, 실제 Jev로 56/56)로 확인합니다. 키가 있으면 `--sweep`으로 기준값별 정확도를 봅니다.

```bash
.venv/bin/python -m scripts.judge_eval --sweep
```

## 데이터 모델

테이블은 8개이며, 모두 `id`와 `created_at`을 가집니다.

| 테이블 | 핵심 컬럼 | 제약 |
| --- | --- | --- |
| users | email, password_hash, name, role | email 유일. name은 교수만 |
| email_verifications | email, code, expires_at, verified_at | 메일당 최신 1건만 유효 |
| courses | code, name, professor_id, semester | code 유일 |
| course_schedules | course_id, day_of_week(0=월), start_time, end_time | |
| enrollments | user_id, course_id | 쌍 유일 |
| class_sessions | course_id, date, week | (과목, 날짜) 유일 |
| questions | session_id, author_id, content, answered_at | author_id는 어떤 응답에도 안 나감 |
| question_votes | question_id, user_id | 쌍 유일 |

## 프로젝트 구조

```
app/
  main.py              앱, 라우터 등록, CORS, /health
  config.py            환경변수, now_kst()
  db.py                DB 엔진, 세션
  models.py            테이블 8개
  errors.py            api_error(), 공통 오류 핸들러
  deps.py              로그인 사용자, 권한 검사
  openapi_docs.py      Swagger 오류 코드 표 (ERRORS)
  routers/
    auth.py            인증
    courses.py         과목 목록·등록·강의 추가
    history.py         지난 차시
    live.py            수업 중 질문 목록, 질문 직렬화
    questions.py       질문 등록, 나도 궁금, 답변 완료
    stream.py          SSE
  services/
    schedule.py        수업 중 판별, 차시, session_bounds()
    judge.py           Jev 검열
    broadcast.py       과목별 SSE 구독자
    mail.py            인증 메일
    security.py        bcrypt, JWT
scripts/
  seed.py              초기 데이터
  judge_eval.py        검열 평가
tests/judge_cases.csv  검열 평가 문장
docs/SPEC.md           전체 명세
```

## 작업 규칙

- `main`에 직접 올리지 않고 **브랜치 → PR → 머지** 순서로 합니다. 머지하면 Railway가 자동으로 다시 배포합니다.
- 공유 파일(`main.py`, `models.py`, `db.py`, `config.py`, `errors.py`)을 바꿀 때는 먼저 팀에 알립니다.
- API나 오류 코드를 추가하면 `app/openapi_docs.py`의 `ERRORS` 표도 같이 고칩니다. 안 고치면 Swagger가 실제와 달라집니다.
- 오류는 `api_error(status, code, message)`로만 냅니다. 응답에는 작성자 정보(`author_id`, 메일, 이름)를 절대 넣지 않습니다.
- 시각은 모두 KST이고, 응답은 `+09:00`이 붙은 ISO 8601입니다.

## 알려진 제약

- **실제 인증 메일이 나가지 않습니다.** Railway 무료(Hobby) 요금제는 SMTP 포트를 막습니다. 배포 환경에서는 `SMTP_*`를 비워 두어, 인증 코드가 Railway 로그에 찍히게 합니다. 데모는 seed 계정을 씁니다.
- **seed 계정 비밀번호가 공개되어 있습니다.** 저장소가 공개이므로 발표 전에 배포 서버의 교수 계정 비밀번호를 바꾸는 것을 권합니다.
- **`DEMO_ALWAYS_LIVE`:** 배포 서버에서 켜져 있습니다. 발표 때 켤지, 데모 과목 시간표를 발표 시간에 맞출지 정해야 합니다.

## 범위 밖

신고·관리 화면, 비밀번호 찾기·탈퇴, 보강·휴강, LMS 연동, 질문 수정·삭제, 댓글·글 답변, 푸시·메일 알림.

## 일정

| 언제 | 무엇을 |
| --- | --- |
| 11/22 (일) | 프론트와 연결해 모든 화면이 실제 데이터로 동작 |
| 11/23 (월) | 통합 테스트, 버그 수정, 발표 자료. 전원이 휴대폰으로 한 차시 끝까지 돌려보기 |
| 11/24 (화) 12:00 | 제출 |
