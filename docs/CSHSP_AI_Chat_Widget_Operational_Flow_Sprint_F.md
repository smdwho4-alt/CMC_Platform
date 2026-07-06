# CSHSP AI Chat Widget & Operational Flow — Sprint F 산출 문서

> **프로젝트:** Cheonan Medical Center AI Health Screening Concierge Platform (CSHSP)
> **Sprint:** F — AI 채팅 위젯 · 본인확인 · 알림 워커 · 문진 제출/검토 · 운영 리허설
> **작성일:** 2026-07-03

---

## 1. Sprint F 목적

Sprint E Agent Layer를 실제 수검자 접점(채팅 위젯)과 직원 운영 흐름(승인→알림→문진 검토)에 연결한다.
AI는 예약을 확정하지 않고, 본인확인 전에는 민감정보를 노출하지 않으며, 알림은 PENDING 큐까지만 처리한다(실발송 없음).

## 2. 구성 요소

```
chat/
├── index.html               위젯 데모 페이지 (예약 페이지 임베드 예시)
├── chat_widget.js           CSHSPChat.init({apiBase, mount}) — 삽입형 위젯
└── chat_widget.css

src/api/routes_agents.py     /api/agents/* — 채팅·본인확인·문진 제출 (공개, 세션 기반)
src/workers/notification_worker.py   PENDING → SENT/FAILED Mock 처리 (+재시도)
src/questionnaire/questionnaire_service.py   문진 상태 전이 관리
admin/questionnaire_review.html      직원 문진 검토 화면 (SUBMITTED → REVIEWED/REJECTED)
```

api_server.py 보완: agents 라우터 포함(`include_agents` 파라미터로 순환 생성 방지),
직원용 `GET /api/questionnaires`·`POST /api/questionnaires/{id}/review` 추가.
reservation_audit에 `SAFETY_BLOCKED` 이벤트 추가.

## 3. AI Chat Widget

- 임베드: CSS+JS 2파일 로드 후 `CSHSPChat.init({ apiBase })` 한 줄 — 예약 페이지 어디든 삽입 가능
- 우하단 플로팅 버튼 → 패널: 대화창 + 퀵버튼(프로그램 추천/금식 안내/예약 신청/내 예약 확인/상담원 연결) + 예약 미니폼 + 본인확인 폼
- 하단 고정 고지: "AI는 예약 신청까지만 접수하며, 확정은 직원 확인 후 진행됩니다."
- 세션: sessionStorage 기반 sessionId → 서버 세션(본인확인 상태)과 매칭
- `POST /api/agents/chat` 단일 진입 — Safety Guard → 본인확인 게이트 → 에이전트 위임

## 4. 본인확인 흐름

| 상태 | 도달 방법 | 허용 범위 |
|------|----------|----------|
| UNVERIFIED | 초기 | 프로그램 안내·FAQ만. 예약 신청·조회 불가 |
| VERIFIED_BASIC | 이름+전화번호 일치 | 예약 신청 가능. 개인정보 **마스킹** 표시 (1999****, 010-****-0003) |
| VERIFIED_PHONE | 인증번호(Mock: 123456) 확인 | 기본정보 전체 표시 |

- **클라이언트가 보낸 patientId는 무시** — 서버 세션의 검증된 patientId만 사용 (테스트로 실증)
- 실서비스 전환 시 인증번호 발급을 SMS 발송으로 교체 (Mock 코드 상수 1곳)

## 5. 문진 제출·검토 흐름

```
AI 채팅 "사전 문진" → POST /api/questionnaires/start (DRAFT, 5문항 템플릿)
→ 수검자 응답 → POST /api/agents/questionnaires/{id}/submit  (세션 소유자 검증, 미응답 항목 차단)
→ SUBMITTED → 직원 검토 화면(admin/questionnaire_review.html)
→ POST /api/questionnaires/{id}/review → REVIEWED(확인) | REJECTED(보완 요청 → 재제출 가능)
```
상태 전이는 `questionnaire_service.STATUS_TRANSITIONS`로 강제 (REVIEWED 후 재검토 400 확인).
문진은 응답 수집·기록만 하며 의학적 평가는 하지 않는다.

## 6. Notification Worker

- `process_pending()`: PENDING 조회 → Mock 발송 → SENT(+sentAt) / FAILED(+failReason, retryCount)
- `retry_failed()`: 한도(3회) 내 FAILED → PENDING 복귀
- 실발송 없음 — sender 함수만 알림톡/SMS API로 교체하는 구조
- 테스트: 실패 주입 → FAILED 기록 → 재시도 → SENT 전환 확인

## 7. Safety Guard 차단 이력

채팅에서 차단 발생 시 `SAFETY_BLOCKED` 감사로그 기록:
`{action: SAFETY_BLOCKED, entityType: ChatSession, entityId: 세션ID, after: {category}, note: 입력 일부}`
— 차단 유형 통계로 Dashboard 연계 가능.

## 8. 운영 리허설 결과 (신청→승인→알림→문진→검토)

| 단계 | 행위자 | 결과 |
|------|--------|------|
| ① 본인확인 | 수검자(채팅) | UNVERIFIED→BASIC→PHONE, 마스킹 정책 확인 |
| ② 예약 신청 | 수검자(채팅) | RSV 생성 PENDING_APPROVAL + Slot HOLD + 감사기록, "직원 확인 후 확정" 고지 |
| ③ 직원 승인 | 직원(API/admin) | CONFIRMED + 알림 PENDING 생성 |
| ④ 알림 처리 | Worker | FAILED(주입) → 재시도 → SENT |
| ⑤ 사전문진 | 수검자(채팅) | DRAFT 생성 → 5문항 응답 제출 → SUBMITTED |
| ⑥ 문진 검토 | 직원(검토 화면) | REVIEWED (검토자·메모 기록) |

최종 상태 검증: RSV=CONFIRMED / NTF=SENT / QST=REVIEWED + 감사로그(신청·승인·차단) + 무결성 0오류.

## 9. 테스트 결과

- **자동 테스트 31/31 PASS** (`tests/run_sprint_f_tests.py`, 결과 CSV 저장, 원본 data/ 불변)
- 회귀: Sprint D 36/36, Sprint E 31/31 유지
- **브라우저 실증** (정적 :4000 + uvicorn :8600/샌드박스): 위젯 로드 → FAQ 응답 → 의료질문 차단(주황 말풍선) → 본인확인 2단계 → 예약 신청 접수(신청번호 20260703-0001) → 서버 JSON에 PENDING_APPROVAL + SAFETY_BLOCKED 감사로그 영속 확인. 문진 검토 화면: SUBMITTED 목록 마스킹 표시 + AI 계정 403 (스크린샷 확보)

## 10. 발견된 문제

1. FastAPI + `from __future__ import annotations` 환경에서 함수 내부 정의 Pydantic 모델이 query 파라미터로 오인 → 모듈 레벨로 이동해 해결
2. 오케스트레이터 in-process 클라이언트가 create_app을 재귀 생성 → `include_agents=False`로 순환 차단
3. 채팅 세션이 프로세스 메모리 저장 — 서버 재시작 시 본인확인 초기화 (실서비스: Redis/DB 세션 필요)
4. 인증번호가 Mock 상수(123456) — 실 SMS 발급 전 보안 의미 없음 (내부 테스트 전용)

## 11. 보완 필요사항

- 세션 영속화 + 세션 만료 정책, 인증번호 실발송(알림톡/SMS)
- 대화 다중턴 상태 관리(슬롯 채우기) — 현재는 미니폼으로 대체, LLM 연동 시 자연어 추출로 교체
- 알림 워커 스케줄링(주기 실행) 및 발송 이력 화면
- 문진 REJECTED 시 수검자 재제출 안내 알림 자동 생성
- admin 콘솔에 문진 검토 메뉴 통합(현재 별도 페이지)

## 12. 다음 Sprint 제안 (Sprint G)

| 우선순위 | 작업 |
|:---:|------|
| 1 | Claude API 실연동 — 자연어 → 의도/슬롯 추출, TOOL_SCHEMAS 도구 호출 루프 |
| 2 | 운영 배포 준비: 세션 저장소, 실인증, HTTPS, 프로세스 매니저 |
| 3 | 알림 실발송 연동(카카오 알림톡) + 발송 이력 관리 |
| 4 | admin 통합(문진 메뉴, 알림 큐 모니터), Dashboard에 AI 상담/차단 통계 |
| 5 | 부하·보안 점검 (rate limit, 입력 검증, 개인정보 로그 정책) |

---

*CSHSP Sprint F | 2026-07-03 | 천안의료원 건강검진센터*
