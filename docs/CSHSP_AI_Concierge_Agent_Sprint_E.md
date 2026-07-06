# CSHSP AI Concierge Agent — Sprint E 산출 문서

> **프로젝트:** Cheonan Medical Center AI Health Screening Concierge Platform (CSHSP)
> **Sprint:** E — AI Concierge Agent Layer
> **작성일:** 2026-07-03
> **위치:** `99_임시보관_정리대기/CMC_Platform_new/src/agents/`

---

## 1. Sprint E 목적

Sprint D REST API 위에 AI 예약비서·검진 코디네이터·문진·CRM·운영비서 에이전트 기반을 구축한다.

**불변 원칙 (코드 레벨 강제):**
- AI는 예약을 확정하지 않는다 → 확정 도구 자체가 없고, API도 403으로 차단 (이중 방어)
- AI는 진단·처방·결과해석을 하지 않는다 → Safety Guard가 도구 호출 전에 차단
- AI는 예약 '신청'까지만 수행 → 모든 신청 응답에 "직원 확인 후 확정" 문구 고정
- 의료 판단 필요 시 "의료진 상담 필요" 안내 + CRM 자동 에스컬레이션

## 2. AI Agent 구조

```
사용자 입력
   ↓
agent_orchestrator.AgentOrchestrator.handle_message(text, context)
   ① safety_guard.check() — 진단/처방/결과해석/응급 차단, 즉시확정→절차안내 전환
   ② 의도 분류 (키워드 규칙 — 향후 LLM 분류기 교체 지점)
   ③ 에이전트 위임
        ├ reservation_agent    예약 신청·가능시간 조회 (X-User-Id: USR-9000)
        ├ recommendation_agent 프로그램·선택검사·FAQ 안내 (KB 기반)
        ├ questionnaire_agent  사전문진 시작 (응답 수집만)
        ├ crm_agent            상담 접수 + Notification PENDING
        └ operation_agent      직원용 운영 브리핑 (직원 계정 — 권한 분리)
   ↓
function_tools.FunctionTools — 도구 8종 단일 실행기
   ↓
ApiClient → Sprint D REST API (in-process ASGI / base_url로 원격 전환)
   ↓
Reservation Engine → data/*.json + audit_logs
```

- LLM 연동 지점: `function_tools.TOOL_SCHEMAS`(Claude tool-use 형식)를 Claude API/MCP에 등록하고,
  `FunctionTools.execute(name, args)`를 도구 실행기로 사용
- 신규 API 2종을 api_server.py에 보완: `POST /api/questionnaires/start`, `POST /api/crm/notifications`
  (AI 역할 권한 notification:draft·crm:log와 정합)

## 3. Function Tool 8종

| # | Tool | 연결 | 설명 |
|---|------|------|------|
| 1 | list_available_slots | GET /api/slots?status=AVAILABLE | 예약 가능 슬롯 조회 |
| 2 | recommend_alternative_slots | GET /api/slots/recommend | 대체 슬롯 ≤5 추천 |
| 3 | create_reservation_request | POST /api/reservations | 예약 신청 (→PENDING_APPROVAL) |
| 4 | recommend_program | knowledge_base.json | 프로그램 안내 (가격·구성 기준) |
| 5 | recommend_optional_tests | knowledge_base.json | 선택검사 안내 (수가 미등록 표기) |
| 6 | start_questionnaire | POST /api/questionnaires/start | 사전문진 DRAFT 생성 (5문항 템플릿) |
| 7 | create_crm_notification | POST /api/crm/notifications | CRM OPEN + Notification PENDING |
| 8 | search_knowledge | knowledge_base.json | RAG 초안 키워드 검색 |

**확정(approve)·거절·취소 도구는 의도적으로 제공하지 않는다.**

## 4. Safety Guard

| 분류 | 예시 입력 | 처리 |
|------|----------|------|
| DIAGNOSIS | "위암인가요?", "무슨 병이죠?" | 차단 + "의료진 상담 필요" + CRM 에스컬레이션 |
| PRESCRIPTION | "혈압약 처방 바꿔도 되나요?" | 차단 + 동일 |
| RESULT_INTERPRETATION | "결과 수치 해석해 주세요" | 차단 + 동일 |
| EMERGENCY | "가슴이 아프고 숨이 안 쉬어져요" | 즉시 119/응급실 안내 |
| CONFIRM_REDIRECT | "지금 바로 확정해줘" | 차단 아님 — 절차 안내 문구 강제 첨부 |

고정 문구는 `safety_guard.STAFF_CONFIRM_NOTICE` 상수 하나로 관리하며
`ensure_staff_notice()`가 모든 예약 응답에 포함을 보장한다.

## 5. RAG Knowledge Base 초안

`data/knowledge_base.json` — 13개 청크 (program 6 / optional_test 1 / faq 4 / policy 2).
실제 2026 브로셔 가격 반영, 수가 미등록 검사는 금액 추정 금지 정책 명시.
현재는 키워드 스코어링 검색이며, 향후 임베딩 기반 검색으로 교체할 수 있도록
청크 구조(id/category/title/content/keywords)로 설계했다.

## 6. API 연계 결과

- 에이전트의 모든 병원 데이터 접근이 REST API를 경유함 (파일 직접 접근 없음)
- AI 신원(USR-9000/ROLE-AI-AGENT) 권한이 API 레벨에서 강제됨: 신청 201, 승인 403, 예약조회 403
- 운영비서는 직원 계정으로 호출 — AI 예약비서와 권한 분리 실증
- in-process ASGI(TestClient) ↔ 원격(base_url) 전환 가능한 ApiClient 구조

## 7. 테스트 결과

**31/31 PASS** (`tests/run_sprint_e_tests.py`, 결과 `tests/sprint_e_test_result.csv`)
샌드박스 사본 실행, 원본 data/ 불변 검증 포함. 회귀: Sprint B 38/38, Sprint D 36/36 유지.

요구 8개 시나리오 전부 포함:
AI 예약 신청 성공(PENDING_APPROVAL 파일 기록) / AI 확정 차단(도구 미제공 + API 403) /
진단 질문 차단 / 결과해석 차단 / FULL Slot 대체추천(≤5) / Notification PENDING 생성 /
감사로그(AI 신청 기록) 확인 + 추가(응급 안내, 즉시확정 절차 전환, 27세→YOUNG 추천,
KB 검색, 문진 DRAFT, CRM OPEN, 운영 브리핑, 무결성 0오류).

## 8. 발견된 문제

1. Sprint A 시드 예약에 reservationNo 필드가 없어 운영 브리핑에서 KeyError → `.get()` 폴백으로 수정
2. Safety Guard는 정규식 규칙 기반 — 우회 표현(오타, 돌려 말하기) 방어 한계. LLM 연동 시 시스템 프롬프트 + 모델 수준 가드와 병행 필요
3. 의도 분류가 키워드 규칙이라 복합 문장에서 오분류 가능 (LLM 분류기 교체 지점 주석 표기)
4. 본인확인 절차 부재 — patientId를 context로 신뢰함. 실서비스 전 전화번호 인증 등 필수

## 9. 보완 필요사항

- Claude API 실연동 (TOOL_SCHEMAS 등록 + 대화 루프) 및 시스템 프롬프트 작성
- 문진 응답 제출/수정 API (현재 시작만 구현)
- Notification PENDING 발송 워커 (카카오 알림톡/SMS)
- 대기예약(WAITING) 자동 승격과 AI 안내 연계
- Safety Guard 룰 확장 + 차단 이력 감사로그 기록

## 10. 다음 Sprint 제안 (Sprint F)

| 우선순위 | 작업 |
|:---:|------|
| 1 | Claude API 실연동 — 시스템 프롬프트 + TOOL_SCHEMAS + 대화 세션 관리 |
| 2 | 웹 채팅 UI (예약 페이지 내 AI 비서 위젯, admin과 동일 정적 구조) |
| 3 | 본인확인(전화번호 인증) + 환자 매칭 플로우 |
| 4 | 알림 발송 워커 + 발송 이력 관리 |
| 5 | 문진 응답 제출 API + 직원 검토 화면 |
| 6 | 운영 리허설: 직원 시나리오 테스트 (신청→승인→알림→문진→내원) |

---

*CSHSP Sprint E | 2026-07-03 | 천안의료원 건강검진센터*
