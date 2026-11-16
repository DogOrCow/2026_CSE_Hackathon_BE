# 익명실명 스펙 명세서

Nov 17, 2026 · @예성

## 1. 개요

익명실명은 수업 중에 손들기 어려운 질문을 학생이 익명으로 올리고, 교수가 질문 받는 시간에 확인해 말로 답하는 웹앱이다.

- 사용자: 학생, 교수 두 역할. 같은 로그인 화면을 쓰고 계정의 역할로 구분한다.
- 제출 대상: 2026 경북대 컴퓨터학부 해커톤. 제출 마감은 11월 24일 12:00이다.
- 데모 범위: 과목 1~2개, 수강생 수십 명 규모. 서버 한 대로 운영한다.

설계 원칙은 네 가지다.

- 질문은 화면에 익명으로 보인다. 작성자 정보는 서버에만 남고 어떤 응답에도 담기지 않는다.
- 질문은 등록 전에 판단 모델이 수업 관련 질문인지 확인한다.
- 질문은 수업 시간에만 올릴 수 있고, 올라온 순서대로 보인다.
- 과목 코드는 학기 초에 한 번만 입력한다.

## 2. 화면과 플로우

화면은 학생 9개, 교수 4개다. 시안은 익명실명 와이어프레임에 있다.

| 화면 | 언제 나오나 | 다음 화면 |
| --- | --- | --- |
| 학생 1. 로그인 | 처음 접속, 로그아웃 후 | 학생은 학생 2, 교수는 교수 1 |
| 학생 1-1. 가입 | 로그인의 가입 링크 | 학생 2-1 |
| 학생 2. 과목 선택 | 로그인 후, 등록한 과목이 있을 때 | 수업 중인 과목은 학생 3, 아니면 학생 5 |
| 학생 2-1. 과목 없음 | 등록한 과목이 없거나 코드가 틀렸을 때 | 코드 등록 후 학생 2 |
| 학생 3. 질문창 | 수업 중인 과목에 들어갔을 때 | 등록 성공 시 그대로, 보류 시 학생 4 |
| 학생 3-1. 질문 없음 | 질문창에 질문이 0개일 때 | 첫 질문 등록 후 학생 3 |
| 학생 4. 검열 보류 | 판단 모델이 등록을 보류했을 때 | 고쳐서 다시 등록하면 학생 3 |
| 학생 4-1. 수업 종료 | 질문창에 있는 동안 수업이 끝났을 때 | 학생 5 |
| 학생 5. 지난 질문 | 수업 중이 아닌 과목에 들어갔을 때 | 날짜를 바꿔가며 조회 |
| 교수 1. 과목 선택 | 교수 계정으로 로그인 후 | 수업 중인 과목은 교수 2, 아니면 교수 3 |
| 교수 2. 질문 받는 창 | 수업 중인 과목에 들어갔을 때 | 뒤로가기로 교수 3 |
| 교수 2-1. 질문 없음 | 질문 받는 창에 질문이 0개일 때 | 질문이 오면 교수 2 |
| 교수 3. 차시별 질문 | 수업 중이 아닌 과목, 또는 교수 2에서 뒤로가기 | 차시를 바꿔가며 조회, 수업 중이면 교수 2로 복귀 |

모바일 폭에서는 같은 화면이 한 줄로 쌓인다. 질문창은 데스크톱에서 카드, 모바일에서 구분선 목록으로 보인다.

## 3. 기능 명세

기능은 학생 10개, 교수 5개다.

### 학생

| ID | 기능 | 동작 |
| --- | --- | --- |
| S-01 | 가입 | knu.ac.kr 메일로 6자리 인증 코드를 받는다. 코드는 3분간 유효하고 다시 보내기가 가능하다. 비밀번호는 8자 이상이며, 익명 정책 동의가 필수다. |
| S-02 | 로그인 | 메일과 비밀번호로 로그인한다. 로그인 상태 유지를 선택할 수 있다. |
| S-03 | 과목 등록 | 과목 코드를 입력하면 내 과목에 추가된다. 없는 코드는 입력 칸 아래에 오류를 보여준다. 이미 등록한 과목은 다시 등록하지 않는다. |
| S-04 | 과목 목록 | 수업 중인 과목을 맨 위에 강조한다. 나머지는 교수 이름, 시간표, 다음 수업 시각을 보여준다. |
| S-05 | 질문 목록 | 수업 중인 차시의 질문을 올라온 순서로 보여준다. 각 질문에 등록 시각(시:분)을 표시한다. 새 질문은 새로고침 없이 추가된다. |
| S-06 | 질문 등록 | 화면 아래 입력창에서 200자까지 쓴다. 판단 모델을 통과하면 목록 맨 아래에 추가된다. 보류되면 사유를 입력창 위에 보여주고 쓴 글은 입력창에 남긴다. |
| S-07 | 나도 궁금 | 다른 사람 질문에 누르면 숫자가 1 오르고, 다시 누르면 취소된다. 내가 쓴 질문과 답변 완료된 질문에는 버튼이 없고 숫자만 보인다. |
| S-08 | 상태 표시 | 내가 쓴 질문에는 "내가 쓴 질문", 교수가 답변 완료한 질문에는 "교수님이 답변함"을 붙인다. 작성자 이름이나 익명 번호는 표시하지 않는다. |
| S-09 | 수업 종료 | 수업이 끝나면 입력창을 안내 문구와 "지난 질문 보기" 버튼으로 바꾼다. 목록은 그대로 볼 수 있다. |
| S-10 | 지난 질문 | 날짜 칩과 좌우 화살표로 차시를 고른다. 질문을 시간순으로 보여주며 읽기 전용이다. 답변 여부는 표시하지 않는다. |

### 교수

| ID | 기능 | 동작 |
| --- | --- | --- |
| P-01 | 로그인 | 학생과 같은 화면에서 로그인한다. 교수 계정과 담당 과목은 운영자가 미리 등록한다. 교수는 방을 만들지 않는다. |
| P-02 | 내 강의 | 담당 과목 목록과 과목 코드를 보여준다. 수업 중인 과목을 맨 위에 강조한다. |
| P-03 | 질문 받는 창 | 수업 중인 차시의 질문을 올라온 순서로 보여준다. 각 질문에 등록 시각과 궁금해한 사람 수를 표시한다. 새 질문은 새로고침 없이 추가된다. |
| P-04 | 답변 완료 | 질문마다 "답변 완료"를 누른다. 완료된 질문은 제자리에서 흐려지고 "되돌리기"로 취소할 수 있다. |
| P-05 | 차시별 질문 | 지난 차시를 날짜로 고르면 그날 질문을 시간순으로 보여준다. 읽기 전용이며 답변 여부는 표시하지 않는다. 수업 중이면 맨 위에 질문 받는 창으로 가는 줄을 둔다. |

## 4. 정책

### 익명

- 질문에는 작성자 ID를 저장하되, 어떤 API 응답에도 작성자 ID, 메일, 이름을 담지 않는다. 교수용 응답도 마찬가지다.
- "내가 쓴 질문"은 서버가 비교해서 mine 불리언으로만 내려준다.
- 가입할 때 "운영 정책을 어긴 글은 운영진이 작성자를 확인할 수 있다"는 데 동의를 받는다.
- 신고 기능은 두지 않는다.

### 검열

등록 요청 하나 안에서 두 단계를 순서대로 거친다.

- 규칙 검사: 앞뒤 공백을 잘라낸 뒤 1자 이상 200자 이하인지 본다. 어기면 400을 돌려준다.
- 판단 모델 (Jev): 질문 본문과 과목명을 넘기고, 네 개 선택지 중 어느 쪽인지 판정받는다. 선택지는 ON_TOPIC(수업 내용 질문), OFF_TOPIC(수업과 관련 없음), PERSONAL(특정 사람 언급이나 비방), ABUSIVE(욕설이나 혐오)다. Jev는 선택지별 확률과 확신도를 돌려준다.

| 상황 | 처리 |
| --- | --- |
| 가장 높은 선택지가 ON_TOPIC | 질문을 저장하고 실시간 이벤트를 보낸다 |
| 가장 높은 선택지가 나머지 셋 중 하나이고 확신도가 기준값 이상 | 저장하지 않고 422와 그 선택지를 사유 코드로 돌려준다. 다른 사용자에게는 보이지 않는다 |
| 확신도가 기준값 미만 | 통과로 처리한다. 애매한 질문을 막는 쪽이 손해가 더 크다고 본다 |
| 3초 안에 응답 없음, 호출 실패 | 통과로 처리한다 (데모 중 등록이 멈추지 않게 하기 위함) |

확신도 기준값은 0.6에서 시작한다. 실제 수업 질문과 걸러야 할 문장을 합쳐 30개쯤 만들어 돌려보고 조정한다.

사유 코드는 OFF_TOPIC(수업과 관련 없음), PERSONAL(특정 사람 언급이나 비방), ABUSIVE(욕설이나 혐오) 세 가지다. 화면 문구는 프론트가 코드에 맞춰 보여준다.

ABUSIVE는 강하게 막는다. "존나", "ㅈㄴ", "ㅅㅂ", "개빡치다", "미친" 같은 가벼운 비속어와 줄임말도 포함하고, 수업 내용에 대한 말이어도 막는다. "시발점", "개념"처럼 글자만 겹치는 일반 단어는 막지 않는다. (B-4 평가 후 팀 결정)

Jev를 쓰는 이유는 세 가지다. 문장을 생성하지 않고 미리 정한 선택지 안에서만 답하므로 응답을 파싱하거나 형식 오류를 처리할 일이 없다. 사용자 글에 지시문을 섞어도 모델이 내놓을 수 있는 것이 선택지 확률뿐이다. 응답이 빨라서 등록 버튼을 누른 뒤 기다리는 시간이 짧다. 다만 Jev는 판정 이유를 설명하지 않으므로, 사용자에게 보여주는 사유는 선택지 이름에 맞춰 미리 써둔 문구를 쓴다. 모델 소개는 Jev: 텍스트 대신 확률을 돌려주는 결정 모델과 Jev 결정 모델 정리를 참고했다.

Jev 호출은 judge(content, course_name) 함수 하나 뒤에 둔다. 모델이나 기준값을 바꿔도 이 함수만 고치면 된다. 모델 ID는 최신 별칭 대신 고정 버전을 써서 발표 중에 동작이 바뀌지 않게 한다. 요청 형식과 SDK 사용법은 TypeSafe 공식 문서에서 확인해 구현한다.

### 수업 중 판별과 차시

- 과목마다 요일, 시작 시각, 종료 시각을 저장한다. 요청이 올 때 서버 시각(Asia/Seoul)과 비교해 수업 중인지 계산한다.
- 차시는 과목과 날짜로 유일하다. 수업 시간에 첫 요청이 들어올 때 없으면 만든다.
- 수업 종료 시각이 지나면 질문 등록, 나도 궁금, 답변 완료 모두 막힌다.
- 보강과 휴강은 이번 범위에서 다루지 않는다.
- 데모와 개발을 위해 DEMO_ALWAYS_LIVE 환경변수를 둔다. 켜면 시간표와 무관하게 모든 과목을 수업 중으로 보고, 오늘 날짜의 차시를 쓴다.

### 나도 궁금과 답변 완료

- 나도 궁금은 질문과 사용자 쌍으로 유일하다. 개수는 조회할 때 센다.
- 내가 쓴 질문과 답변 완료된 질문에는 누를 수 없다.
- 답변 완료와 되돌리기는 그 과목의 담당 교수만 할 수 있다.
- 질문 순서는 학생과 교수 화면 모두 등록 시각 오름차순이다. 궁금 수나 답변 여부로 순서를 바꾸지 않는다.

## 5. 데이터 모델

테이블은 8개다. 모든 테이블은 id(정수, 자동 증가)와 created_at을 갖는다.

| 테이블 | 컬럼 | 제약 |
| --- | --- | --- |
| users | email, password_hash, name, role (STUDENT 또는 PROFESSOR) | email 유일 |
| email_verifications | email, code (6자리), expires_at, verified_at | 메일당 최신 1건만 유효 |
| courses | code, name, professor_id, semester | code 유일, professor_id는 users 참조 |
| course_schedules | course_id, day_of_week (0=월 ~ 6=일), start_time, end_time | course_id는 courses 참조 |
| enrollments | user_id, course_id | (user_id, course_id) 유일 |
| class_sessions | course_id, date, week | (course_id, date) 유일 |
| questions | session_id, author_id, content (최대 200자), answered_at (널 가능) | session_id에 인덱스 |
| question_votes | question_id, user_id | (question_id, user_id) 유일 |

- 답변 여부는 answered_at이 널인지로 판단한다. 되돌리기는 널로 되돌린다.
- 보류된 질문은 저장하지 않으므로 상태 컬럼이 없다.
- week(주차)는 학기 시작일로부터 계산해 차시를 만들 때 넣는다. 학기 시작일은 설정값으로 둔다.
- 교수 계정, 과목, 시간표는 초기 데이터 스크립트로 넣는다. 등록 화면은 만들지 않는다.
- users.name은 교수만 값이 있다. 학생은 가입할 때 이름을 받지 않으므로 널이다.

## 6. API 명세

엔드포인트는 15개다. 모든 경로는 /api로 시작하고, 인증이 필요한 요청은 `Authorization: Bearer <토큰>` 헤더를 보낸다. 요청과 응답 본문은 JSON이다.

아래 표의 경로는 /api를 뺀 나머지다. 예를 들어 /auth/login의 실제 경로는 /api/auth/login이다.

### 인증

| 메서드 | 경로 | 요청 | 성공 응답 | 오류 |
| --- | --- | --- | --- | --- |
| POST | /auth/email-code | email | 204 | 400 INVALID_EMAIL_DOMAIN, 409 EMAIL_TAKEN |
| POST | /auth/signup | email, code, password, agreed | 201 access_token, role, name | 400 INVALID_CODE, 400 CODE_EXPIRED, 400 WEAK_PASSWORD, 400 AGREEMENT_REQUIRED |
| POST | /auth/login | email, password | 200 access_token, role, name | 401 INVALID_CREDENTIALS |
| GET | /me | 없음 | 200 email, name, role | 401 UNAUTHORIZED |

응답의 name은 교수면 이름, 학생이면 메일의 @ 앞부분이다. 토큰은 7일간 유효하고 리프레시 토큰은 두지 않는다. 로그인 상태 유지를 끄면 프론트가 토큰을 브라우저 탭이 열려 있는 동안만 보관한다.

### 과목

| 메서드 | 경로 | 권한 | 성공 응답 | 오류 |
| --- | --- | --- | --- | --- |
| GET | /courses | 학생은 등록한 과목, 교수는 담당 과목 | 200 과목 배열 | 없음 |
| POST | /courses/enroll | 학생. 요청 code | 201 과목 | 404 COURSE_NOT_FOUND, 409 ALREADY_ENROLLED |

과목 객체는 아래 형태다. code는 교수에게만 내려준다.

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

### 수업 중

| 메서드 | 경로 | 권한 | 성공 응답 | 오류 |
| --- | --- | --- | --- | --- |
| GET | /courses/{id}/live | 등록 학생, 담당 교수 | 200 session, questions | 409 NOT_IN_CLASS |
| POST | /courses/{id}/questions | 등록 학생. 요청 content | 201 질문 | 400 INVALID_LENGTH, 409 NOT_IN_CLASS, 422 QUESTION_HELD (+ reason) |
| PUT | /questions/{id}/vote | 등록 학생 | 200 vote_count, voted: true | 403 OWN_QUESTION, 409 ALREADY_ANSWERED, 409 NOT_IN_CLASS |
| DELETE | /questions/{id}/vote | 등록 학생 | 200 vote_count, voted: false | 409 ALREADY_ANSWERED, 409 NOT_IN_CLASS |
| PUT | /questions/{id}/answered | 담당 교수 | 200 answered: true | 409 NOT_IN_CLASS |
| DELETE | /questions/{id}/answered | 담당 교수 | 200 answered: false | 409 NOT_IN_CLASS |
| GET | /courses/{id}/stream | 등록 학생, 담당 교수 | SSE 스트림 (7장) | 409 NOT_IN_CLASS |

/courses/{id}/live의 응답은 아래 형태다. questions는 created_at 오름차순이다. 교수에게는 voted와 mine이 항상 false다.

```json
{
  "session": {
    "id": 42,
    "date": "2026-11-17",
    "week": 11,
    "starts_at": "2026-11-17T10:30:00+09:00",
    "ends_at": "2026-11-17T11:45:00+09:00"
  },
  "questions": [
    {
      "id": 318,
      "content": "3정규형이랑 BCNF 차이가 아직 헷갈려요.",
      "created_at": "2026-11-17T10:52:10+09:00",
      "vote_count": 12,
      "voted": true,
      "mine": false,
      "answered": false
    }
  ]
}
```

### 지난 차시

| 메서드 | 경로 | 권한 | 성공 응답 |
| --- | --- | --- | --- |
| GET | /courses/{id}/sessions | 등록 학생, 담당 교수 | 200 차시 배열 (id, date, week, question_count), 최신순 |
| GET | /sessions/{id}/questions | 등록 학생, 담당 교수 | 200 질문 배열 (id, content, created_at, vote_count), 시간순 |

지난 차시 응답에는 answered, voted, mine을 넣지 않는다.

### 공통 오류

오류 응답은 항상 `{"code": "NOT_IN_CLASS", "message": "지금은 수업 시간이 아닙니다"}` 형태다. 프론트는 code로 분기한다.

| 상태 | 코드 | 언제 |
| --- | --- | --- |
| 401 | UNAUTHORIZED | 토큰이 없거나 만료됨 |
| 403 | FORBIDDEN | 등록하지 않은 과목, 담당이 아닌 과목, 역할이 맞지 않는 요청 |
| 404 | NOT_FOUND | 없는 과목, 차시, 질문 |

## 7. 실시간 (SSE)

질문창과 질문 받는 창은 GET /api/courses/{id}/stream 하나로 변경을 받는다. 서버에서 클라이언트로만 보내는 단방향 연결이다.

| 이벤트 | 데이터 | 보내는 시점 |
| --- | --- | --- |
| question.created | id, content, created_at, vote_count, answered | 질문이 검열을 통과해 저장된 직후 |
| question.voted | id, vote_count | 나도 궁금을 누르거나 취소한 직후 |
| question.answered | id, answered | 답변 완료 또는 되돌리기 직후 |
| session.ended | 없음 | 수업 종료 시각이 됐을 때 |

- 개인별 값은 이벤트에 넣지 않는다. 같은 이벤트가 모두에게 가므로 mine과 voted는 빠진다. 클라이언트는 자기가 등록하거나 누른 요청의 응답으로 이 값을 채운다.
- 인증: 브라우저 기본 EventSource는 헤더를 못 보낸다. 프론트는 fetch로 스트림을 열어 Authorization 헤더를 보낸다.
- 연결 유지: 서버는 20초마다 주석 줄(`: ping`)을 보낸다. 배포 서비스의 프록시가 조용한 연결을 끊지 않게 하기 위함이다.
- 재연결: 끊기면 클라이언트가 /courses/{id}/live를 다시 불러 목록을 통째로 맞춘 뒤 스트림을 다시 연다. 놓친 이벤트를 따로 재전송하지 않는다.
- 서버 구조: 과목 ID별 연결 목록을 메모리에 둔다. 그래서 서버는 반드시 한 대로 띄운다.
- 수업 종료: 스트림을 열 때 차시의 종료 시각을 기억해 두고, 그 시각이 되면 session.ended를 보낸 뒤 연결을 닫는다. DEMO_ALWAYS_LIVE가 켜져 있으면 보내지 않는다.

## 8. 기술 스택과 배포

백엔드는 FastAPI, DB는 PostgreSQL이고 서버 한 대에 Docker로 올린다.

| 영역 | 선택 | 비고 |
| --- | --- | --- |
| 프레임워크 | FastAPI | AI로 코드를 생성하기 때문에 파일 수와 코드 양이 적은 쪽을 골랐다 |
| DB | PostgreSQL | 배포 서비스가 제공하는 것을 쓴다 |
| ORM | SQLModel | 모델 하나로 테이블과 응답 형식을 같이 정의한다 |
| 인증 | JWT | 토큰에 사용자 ID와 역할을 담는다. 비밀번호는 해시로 저장한다 |
| 메일 | Gmail SMTP | 앱 비밀번호를 발급받아 쓴다 |
| 실시간 | SSE | 웹소켓, Redis는 쓰지 않는다 |
| 판단 모델 | Jev (TypeSafe AI) | 선택지별 확률을 돌려주는 결정 모델이다. 함수 하나 뒤에 둔다 (4장 검열) |
| 백엔드 배포 | Railway 또는 Render | 깃허브 저장소를 연결하고 Dockerfile로 빌드한다 |
| 프론트 배포 | Vercel | 프론트 스택은 담당자가 정한다 |

환경변수는 아래 열 개다. 저장소에는 올리지 않는다.

| 이름 | 용도 |
| --- | --- |
| DATABASE_URL | PostgreSQL 접속 주소 |
| JWT_SECRET | 토큰 서명 키 |
| SMTP_USER, SMTP_PASSWORD | 인증 메일 발송 계정 |
| JUDGE_API_KEY | Jev 호출 키 |
| CORS_ORIGINS | 허용할 프론트 주소 |
| TZ | Asia/Seoul. 없으면 수업 중 판별이 9시간 어긋난다 |
| SEMESTER_START | 학기 시작일. 주차 계산에 쓴다 |
| ENV | dev 또는 prod. dev일 때만 X-Debug-User 헤더로 사용자를 지정할 수 있다. 배포 환경은 반드시 prod다 |
| DEMO_ALWAYS_LIVE | true면 모든 과목을 수업 중으로 본다. 발표와 개발용이다 |

이 밖에 JUDGE_THRESHOLD(기본 0.6)와 JUDGE_MODEL은 기본값이 있어서 바꿀 때만 지정한다.

배포할 때 지킬 것은 세 가지다.

- 인스턴스는 1개로 고정하고 자동 확장을 끈다.
- 빈 프로젝트를 첫날 배포해서 경로를 미리 뚫어둔다.
- 무료 요금제가 서버를 재우는 경우, 발표 전에 미리 한 번 열어둔다.

## 9. 범위 밖과 미정 사항

이번 제출에서 만들지 않는 것은 여덟 가지다.

- 신고, 가려진 질문, 운영진용 관리 화면
- 비밀번호 찾기, 계정 탈퇴
- 교수의 과목·시간표 등록 화면 (초기 데이터로 대체)
- 보강, 휴강, 시간표 밖 수업
- LMS 연동으로 수강 과목 자동 불러오기
- 질문 수정과 삭제
- 질문에 댓글이나 글로 된 답변 달기
- 알림 (푸시, 메일)

정해야 할 것은 다섯 가지다.

- [ ] Jev 확신도 기준값을 몇으로 둘지 (테스트 문장 30개로 정한다)
- [ ] 판단 모델이 응답하지 않을 때 통과시킬지 막을지 (현재 명세는 통과)
- [ ] 프론트 스택과 담당자
- [ ] 데모에 쓸 과목과 시간표, 학기 시작일
- [ ] 발표 때 수업 중 상태를 강제로 켤지, 데모용 과목의 시간표를 발표 시간에 맞출지

## 10. 일정

제출은 11월 24일 화요일 12:00이다. 백엔드는 두 명이 맡고, 처음 30분만 같이 한 뒤 서로의 완성을 기다리지 않고 따로 진행한다.

### 0단계: 같이 (약 30분)

이 단계가 main에 올라가면 두 사람은 완전히 따로 작업할 수 있다.

- 저장소와 FastAPI 뼈대, DB 연결, Dockerfile
- models.py: 5장의 테이블 8개 전부
- 빈 라우터 6개(auth, courses, history, live, questions, stream)를 만들고 main.py에 등록
- 임시 함수 세 개 (아래 표)
- 초기 데이터 스크립트: 교수 1명, 학생 3명, 과목 2개, 시간표
- 오류 응답 헬퍼 api_error()

| 임시 함수 | 임시 동작 | 교체 |
| --- | --- | --- |
| get_current_user() | X-Debug-User 헤더의 ID로 사용자를 찾아 돌려준다 | A가 로그인을 끝낸 뒤 JWT 검증으로 바꾼다. ENV=dev에서는 헤더 방식도 남긴다 |
| get_live_session(course_id) | 오늘 날짜의 차시를 없으면 만들어 항상 돌려준다 | A가 시간표 판별을 끝낸 뒤 바꾼다. 임시 동작은 DEMO_ALWAYS_LIVE로 남긴다 |
| judge(content, course_name) | 항상 통과를 돌려준다 | B가 Jev 연동으로 바꾼다 |

함수 이름과 반환값은 교체 후에도 같다. 그래서 이 함수를 쓰는 쪽 코드는 바뀌지 않는다.

### 1단계: 따로

| 순서 | A: 기반, 인증, 과목 | B: 질문, 판단, 실시간 |
| --- | --- | --- |
| 1 | 빈 서버 배포 (푸시하면 자동 배포) | 질문 목록 /live, 질문 등록 |
| 2 | 메일 인증, 가입, 로그인, /me | 나도 궁금, 답변 완료 |
| 3 | get_current_user()를 JWT로 교체 | SSE와 브로드캐스트 |
| 4 | 과목 목록, 과목 등록 | Jev 연동, 기준값 조정 |
| 5 | 수업 중 판별, get_live_session() 교체 | 수업 종료 이벤트 |
| 6 | 지난 차시 API 2개, 권한 점검 | 프론트 연동 지원 |

A는 엔드포인트 8개(인증 4, 과목 2, 지난 차시 2), B는 7개(수업 중 전부)를 맡는다.

### 파일 소유

| 담당 | 파일 |
| --- | --- |
| A | app/deps.py, app/services/schedule.py, app/routers/auth.py, app/routers/courses.py, app/routers/history.py, scripts/seed.py, Dockerfile |
| B | app/routers/live.py, app/routers/questions.py, app/routers/stream.py, app/services/judge.py, app/services/broadcast.py |
| 공유 (0단계 이후 고정) | app/main.py, app/models.py, app/db.py, app/config.py, app/errors.py |

- 공유 파일을 바꿔야 하면 코드를 고치기 전에 상대에게 먼저 알린다.
- AI에게 작업을 시킬 때는 수정할 파일을 매번 지정한다 (11장 프롬프트).
- 기능 하나가 끝나면 바로 main에 올린다. 파일이 겹치지 않으므로 브랜치를 오래 끌지 않는다.
- API가 하나 끝날 때마다 배포 주소의 /docs를 프론트 담당에게 공유한다.

작업 중에 새로 만드는 파일은 만든 사람이 소유한다. A는 app/services/mail.py와 app/services/security.py, B는 scripts/judge_eval.py와 tests/judge_cases.csv를 만든다.

### 마감까지

| 언제까지 | 무엇을 |
| --- | --- |
| 11/22 일 | 1단계 전부, 프론트와 연결해 2장의 13개 화면이 실제 데이터로 동작 |
| 11/23 월 | 통합 테스트, 버그 수정, 발표 자료. 팀원 전원이 휴대폰으로 한 차시를 끝까지 돌려본다 |
| 11/24 화 12:00 | 제출 |

배포 전에 직접 확인할 것은 세 가지다.

- [ ] 어떤 응답에도 작성자 ID, 메일, 이름이 없다
- [ ] 학생 토큰으로 답변 완료 API를 호출하면 403이 나온다
- [ ] 서버 시각이 한국 시간이고, 배포 환경의 ENV가 prod라서 X-Debug-User 헤더가 먹히지 않는다

## 11. AI 작업 프롬프트

프롬프트는 공통 규칙 1개와 작업별 8개다. 이 문서를 저장소의 docs/SPEC.md로 두고, 작업별 프롬프트 앞에 공통 규칙을 붙여서 쓴다.

### 공통 규칙

```
docs/SPEC.md를 처음부터 끝까지 읽고 시작해. 이 문서가 기준이야.

규칙
- "수정할 파일"에 적힌 파일만 만들거나 고쳐. 다른 파일을 바꿔야 할 것 같으면 고치지 말고 이유를 먼저 말해.
- 경로, 요청·응답 필드 이름, 상태 코드, 오류 코드는 6장과 글자 그대로 맞춰.
- 어떤 응답에도 author_id, 작성자 메일, 작성자 이름을 넣지 마. 교수용 응답도 마찬가지야.
- 오류는 app/errors.py의 api_error(status, code, message)로만 내.
- 시각은 모두 Asia/Seoul 기준이고, 응답에는 +09:00이 붙은 ISO 8601로 내.
- 문서와 다르게 구현해야 할 것 같으면 코드를 쓰기 전에 물어봐.
- 끝나면 바꾼 파일 목록과, 기능을 확인할 curl 명령을 적어줘.
```

### 0단계: 뼈대 (같이)

```
작업: 프로젝트 뼈대 (10장 0단계). 엔드포인트는 구현하지 않고 뼈대만 만든다.

만들 것
- requirements.txt, Dockerfile, .env.example, .gitignore
- app/config.py: 8장의 환경변수를 읽는 설정. JUDGE_THRESHOLD(기본 0.6)와 JUDGE_MODEL도 포함
- app/db.py: SQLModel 엔진과 세션 의존성. 서버가 뜰 때 테이블 생성
- app/models.py: 5장의 테이블 8개. 유일 제약과 인덱스 포함
- app/errors.py: api_error()와, 모든 오류를 {"code", "message"}로 내보내는 예외 핸들러
- app/deps.py
  - get_current_user(): 임시 버전. X-Debug-User 헤더의 사용자 ID로 users에서 찾아 돌려준다. 헤더가 없거나 사용자가 없으면 401 UNAUTHORIZED
  - require_student(), require_professor(): 역할이 다르면 403 FORBIDDEN
  - require_course_member(course_id): 등록 학생이거나 담당 교수가 아니면 403. 과목이 없으면 404
  - require_course_professor(course_id): 담당 교수가 아니면 403
- app/services/schedule.py: 임시 get_live_session(session, course_id). 오늘 날짜의 class_sessions 행을 없으면 만들어서 항상 돌려준다
- app/services/judge.py: 임시 judge(content, course_name). 항상 {"passed": True, "reason": None}을 돌려준다
- app/services/broadcast.py: 아무 일도 하지 않는 publish(course_id, event, data)
- app/routers/ 아래 auth.py, courses.py, history.py, live.py, questions.py, stream.py: 각각 빈 APIRouter만
- app/main.py: 라우터 6개를 /api 아래에 등록, CORS 설정, GET /health
- scripts/seed.py: 교수 1명, 학생 3명, 과목 2개(각각 시간표 2개), 학생들의 수강 등록. 여러 번 실행해도 중복되지 않게

확인
- 서버를 띄우면 /docs와 /health가 열린다
- seed를 돌린 뒤 테이블에 데이터가 있다
```

### A-1: 인증

```
작업: 인증 (6장 인증, 3장 S-01, S-02, P-01)
수정할 파일: app/routers/auth.py, app/deps.py, app/services/mail.py(새로), app/services/security.py(새로)

구현
- POST /api/auth/email-code, POST /api/auth/signup, POST /api/auth/login, GET /api/me
- 인증 코드는 6자리 숫자, 3분 유효. 다시 요청하면 이전 코드는 무효
- 메일은 knu.ac.kr 도메인만 받는다
- SMTP 설정이 비어 있으면 메일을 보내는 대신 코드를 서버 로그에 찍는다 (개발용)
- 비밀번호는 해시로 저장. JWT는 7일 유효, 사용자 ID와 role을 담는다
- 가입으로 만들어지는 계정은 항상 STUDENT
- 응답의 name은 교수면 users.name, 학생이면 메일의 @ 앞부분
- deps.py의 get_current_user()를 JWT 검증으로 바꾼다. ENV=dev일 때는 X-Debug-User 헤더도 계속 받고, ENV=prod에서는 이 헤더를 무시한다
- get_current_user()의 이름과 반환 타입(User)은 그대로 둔다. 다른 라우터가 쓰고 있다

확인
- ENV=prod에서 X-Debug-User만 보낸 요청이 401이다
- 만료된 코드는 CODE_EXPIRED, 틀린 코드는 INVALID_CODE다
```

### A-2: 과목과 수업 중 판별

```
작업: 과목과 수업 중 판별 (6장 과목, 4장 수업 중 판별과 차시)
수정할 파일: app/routers/courses.py, app/services/schedule.py

구현
- GET /api/courses, POST /api/courses/enroll
- schedule.py에 is_live(course, now), next_class_at(course, now), schedule_text(course)
- get_live_session(session, course_id)을 실제 판별로 바꾼다. 수업 중이면 오늘 차시를 없으면 만들어 돌려주고, 아니면 409 NOT_IN_CLASS
- DEMO_ALWAYS_LIVE=true면 지금의 임시 동작(항상 오늘 차시)을 유지한다
- 차시를 만들 때 week는 SEMESTER_START로부터 계산한다
- 동시에 두 요청이 와도 (course_id, date) 차시가 하나만 생기게 한다
- 과목 객체의 code는 교수에게만 내려준다. live_question_count는 수업 중이 아니면 0
- get_live_session()의 이름과 인자, 반환 타입은 그대로 둔다

확인
- 시간표를 지금 시각이 포함되게 바꾸면 is_live가 true가 된다
- 없는 코드는 COURSE_NOT_FOUND, 이미 등록한 과목은 ALREADY_ENROLLED다
```

### A-3: 지난 차시와 권한 점검

```
작업: 지난 차시 조회 (6장 지난 차시, 3장 S-10, P-05)
수정할 파일: app/routers/history.py

구현
- GET /api/courses/{id}/sessions: 최신순, 차시마다 question_count
- GET /api/sessions/{id}/questions: 시간순. 필드는 id, content, created_at, vote_count뿐이다
- 두 API 모두 deps.require_course_member()로 권한을 확인한다
- 질문 수만큼 쿼리가 늘지 않게 집계는 한 번에 한다

마지막으로 app/routers/ 전체를 읽고 아래를 보고만 해. 다른 파일은 고치지 마.
- 권한 검사가 빠진 엔드포인트
- 응답에 작성자 정보가 새어 나가는 곳
- 6장과 다른 오류 코드나 필드 이름
```

### B-1: 질문 목록과 등록

```
작업: 질문 목록과 등록 (6장 수업 중, 3장 S-05, S-06, 4장 검열)
수정할 파일: app/routers/live.py, app/routers/questions.py

그대로 가져다 쓸 것 (내부는 고치지 마)
- 사용자: deps.get_current_user()
- 권한: deps.require_course_member(), deps.require_student()
- 차시: schedule.get_live_session()
- 검열: judge.judge(). 지금은 항상 통과를 돌려주는 임시 함수다
- 알림: broadcast.publish(). 지금은 아무 일도 하지 않는다

구현
- GET /api/courses/{id}/live, POST /api/courses/{id}/questions
- 등록 순서: 앞뒤 공백 제거, 길이 검사(400 INVALID_LENGTH), judge() 호출, 통과면 저장하고 201, 보류면 저장하지 않고 422 QUESTION_HELD와 reason
- 질문 객체 필드: id, content, created_at, vote_count, voted, mine, answered. 교수에게는 voted와 mine이 항상 false
- 목록은 created_at 오름차순. vote_count는 한 번에 집계한다
- 교수는 질문을 등록할 수 없다 (403)
- 저장 뒤에 broadcast.publish(course_id, "question.created", {...})를 호출한다. 데이터는 7장 표의 필드만

확인
- X-Debug-User를 바꿔가며 학생 1이 등록한 질문이 학생 2에게 mine: false로 보인다
- 응답 어디에도 author_id가 없다
```

### B-2: 나도 궁금과 답변 완료

```
작업: 나도 궁금과 답변 완료 (6장 수업 중, 4장 나도 궁금과 답변 완료)
수정할 파일: app/routers/questions.py

구현
- PUT, DELETE /api/questions/{id}/vote
- PUT, DELETE /api/questions/{id}/answered
- 내가 쓴 질문에 누르면 403 OWN_QUESTION, 답변 완료된 질문이면 409 ALREADY_ANSWERED
- 질문이 속한 차시가 지금 수업 중인 차시가 아니면 409 NOT_IN_CLASS
- 같은 요청을 두 번 보내도 오류 없이 같은 결과가 나온다
- answered는 deps.require_course_professor()를 통과한 사람만
- 변경 뒤 broadcast.publish()로 question.voted 또는 question.answered를 보낸다

확인
- 학생의 X-Debug-User로 answered를 호출하면 403이다
```

### B-3: 실시간

```
작업: 실시간 (7장)
수정할 파일: app/services/broadcast.py, app/routers/stream.py

구현
- broadcast.py: 과목 ID별 구독자 큐를 메모리에 둔다. subscribe(course_id), unsubscribe(course_id, queue), publish(course_id, event, data)
- publish()의 이름과 인자는 그대로 둔다. 이미 다른 라우터가 호출하고 있다
- GET /api/courses/{id}/stream: text/event-stream. 20초마다 ": ping" 주석 줄을 보낸다
- 연결이 끊기면 구독을 해제한다. 큐가 가득 찬 느린 구독자는 끊는다
- 차시 종료 시각이 되면 session.ended를 보내고 닫는다. DEMO_ALWAYS_LIVE=true면 보내지 않는다
- 응답 헤더에 Cache-Control: no-cache, X-Accel-Buffering: no
- 이벤트에 mine, voted, author_id를 넣지 않는다

확인
- curl -N으로 스트림 두 개를 열고 질문을 등록하면 양쪽에 이벤트가 온다
- 한쪽을 끊은 뒤에도 다른 쪽은 계속 받는다
```

### B-4: Jev 연동

이 프롬프트는 TypeSafe 공식 문서의 요청·응답 부분을 붙여넣은 뒤에 쓴다. Jev는 2026년 9월에 나온 모델이라 AI가 사용법을 모르고 지어낼 수 있다.

```
작업: Jev 연동 (4장 검열)
수정할 파일: app/services/judge.py, scripts/judge_eval.py(새로), tests/judge_cases.csv(새로)

아래에 붙인 공식 문서대로만 호출해. 네가 기억하는 사용법이나 추측으로 채우지 마. 문서에 없는 부분이 필요하면 멈추고 물어봐.

[여기에 TypeSafe 공식 문서의 요청 형식, 응답 형식, 인증 방법을 붙여넣기]

구현
- judge(content, course_name)이 Jev에 선택지 ON_TOPIC, OFF_TOPIC, PERSONAL, ABUSIVE를 주고 판정받는다
- 반환 형태는 지금과 같다: {"passed": bool, "reason": str | None}. reason은 보류일 때의 선택지 이름
- 판정 규칙은 4장의 표를 따른다. 기준값은 config의 JUDGE_THRESHOLD
- 모델 ID는 config의 JUDGE_MODEL에서 읽는다. 고정 버전을 쓴다
- 타임아웃 3초. 타임아웃이나 오류면 통과로 처리하고 경고 로그를 남긴다
- 로그에 질문 본문을 남기지 않는다. 선택지와 확신도만 남긴다
- JUDGE_API_KEY가 비어 있으면 호출하지 않고 통과를 돌려준다 (개발용)
- scripts/judge_eval.py: tests/judge_cases.csv(문장, 과목명, 기대 결과)를 읽어 judge()를 돌리고, 맞은 수와 틀린 문장을 출력한다
- tests/judge_cases.csv에는 헤더만 넣어둬. 문장은 내가 채운다

확인
- judge_eval.py를 돌려 결과가 출력된다
- API 키를 틀리게 넣어도 질문 등록이 멈추지 않는다
```
