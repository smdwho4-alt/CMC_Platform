# CSHSP Claude API 실연동 & 배포 준비 — Sprint G 산출 문서

> **프로젝트:** Cheonan Medical Center AI Health Screening Concierge Platform (CSHSP)
> **Sprint:** G — Claude API 연동 구조 · 자연어 처리 · 세션 영속화 · 보안 · AI Dashboard
> **작성일:** 2026-07-03

---

## 1. Sprint G 목적

규칙 기반 AI Agent(Sprint E~F)를 Claude API 기반 자연어 Agent로 확장할 수 있는 구조를 구축하고,
운영 배포에 필요한 세션 영속화·보안(Rate Limit/PII 마스킹/인젝션 차단)·AI 상담 통계를 보완한다.

## 2. Claude API 연동 구조

```
src/agents/claude_client.py   ClaudeClient — Messages API 어댑터
src/agents/tool_loop.py       run_tool_loop — TOOL_SCHEMAS 기반 수동 tool-use 루프
src/agents/slot_extractor.py  자연어 → 이름/전화/프로그램/일자/시간 추출
```

- **API Key**: 환경변수 `ANTHROPIC_API_KEY`로만 관리 (코드 하드코딩 금지, 예시값도 없음).
  Key 미설정 시 **Mock 모드**로 동작 — 플랫폼은 규칙 기반으로 계속 서비스된다.
- **모델**: 기본 `claude-opus-4-8` (환경변수 `CSHSP_CLAUDE_MODEL`로 변경).
- **timeout/retry**: 실 API는 anthropic SDK 내장(`timeout=60s`, `max_retries=2` — 429/5xx/연결오류
  지수 백오프 자동 재시도). 커스텀 transport(테스트)는 자체 재시도 루프(검증: 2회 실패 후 3번째 성공).
- 응답은 `{stop_reason, content[]}` 정규화 dict — SDK 미설치/미인증 환경과 테스트에서 동일 인터페이스.
- anthropic SDK 0.116 설치됨. `refusal` stop_reason 처리 포함.

## 3. Tool Loop 구조

```
run_tool_loop(client, tools, user_message)
  ① SYSTEM_PROMPT (한국어 절대규칙: 확정불가·의료판단불가·개인정보·수가미등록·인젝션 방어)
  ② messages.create(tools=TOOL_SCHEMAS)
  ③ stop_reason == tool_use →
       허용 목록(TOOL_SCHEMAS 8종) 검사
       · 허용: FunctionTools.execute → tool_result (전체 결과를 하나의 user 메시지로)
       · 미허용(approve_reservation 등): is_error tool_result "차단됨" — 실행 안 함
  ④ end_turn까지 반복 (최대 6회) / refusal 시 안내 후 종료
```

- **예약 신청 tool은 있고 승인 tool은 없다** — 스키마 부재 + 루프 allowlist + API 403의 3중 방어.
- 미허용 도구 요청 후에도 예약 상태 불변임을 테스트로 확인.
- 현재 채팅 기본 경로는 규칙 기반 오케스트레이터이며, tool_loop는 Key 설정 시 전환할 LLM 경로
  (Sprint H에서 chat 라우터 기본 경로 전환 예정).

## 4. 자연어 의도 분류·슬롯 추출

- 의도 분류: 오케스트레이터 규칙(예약/추천/문진/CRM/운영) — LLM 분류기 교체 지점 주석 유지
- `slot_extractor.extract()`: "7월 21일 오전 9시에 스마트로 예약, 테스트박 010-0000-0003"
  → `{name, phone, programId: PRG-SMART, date: 2026-07-21, time: 09:00}` (내일/모레, 오후N시 반 지원)
- 채팅 라우터가 메시지에서 programId/date/time을 자동 보충 → 문맥 없이도 자연어 예약 신청 성공
- **부족한 정보만 추가 질문**: `ask_for_missing()` — "검진 프로그램, 희망 날짜, 희망 시간을 알려주세요"
- 추출된 이름/전화는 본인확인 입력으로만 쓰며 응답에 원문 반환하지 않음

## 5. Session Store 구조

- `src/agents/session_store.py` — `SessionStore` 인터페이스 + `FileSessionStore`(JSON, 스레드 잠금,
  임시파일 교체 저장) + `MemorySessionStore`
- **Redis 교체 지점 명시**: `get/set/delete` 3메서드만 구현한 RedisSessionStore를 라우터 주입부
  1곳에서 교체하면 된다 (`routes_agents.py`의 `FileSessionStore(...)` 라인)
- 저장 최소화: verifyState/patientId/pendingCode만 저장 (대화 원문 저장 안 함)
- 서버 재시작 후 본인확인 상태 복구 검증 (새 앱 인스턴스에서 VERIFIED_PHONE 유지)
- 인증번호 실발송 교체 지점: `routes_agents.py` verify의 `MOCK_VERIFY_CODE` 발급 라인 (주석 표기),
  알림톡/SMS 실발송 교체 지점: `notification_worker.default_mock_sender` (sender 함수 주입 구조)

## 6. AI Dashboard 구조

- 이벤트 기록: `data/ai_events.json` (append-only, **메시지 원문·개인정보 미저장** — type/sessionId/시각만)
- `src/dashboard/ai_metrics.py` → `GET /api/dashboard/ai` (인증 필요)
- 지표: 총 상담 수 / 고유 세션 / 예약 신청 전환 수·전환율 / Safety 차단 수(+유형별) /
  본인확인 완료·휴대폰 인증 / 문진 제출 / 상담원 연결 / 요청 제한 / 시간대별(0~23시) 상담량
- 화면: `admin/ai_dashboard.html` — KPI 카드 10종 + 시간대 차트 + 차단 유형 배지 +
  차단 이력 50건(마스킹된 입력 표시). admin 콘솔 사이드바에 **문진 검토 / AI 상담 통계** 메뉴 연결

## 7. Security 보완

| 항목 | 구현 |
|------|------|
| Rate Limit | `src/security/rate_limit.py` 슬라이딩 윈도우 (기본 30회/60초, `CSHSP_CHAT_RATE`) — 채팅 세션 단위, 초과 시 429 + RATE_LIMITED 집계 |
| PII 로그 마스킹 | `src/security/privacy_logger.py` — 전화(010-****-XXXX)/주민번호/이메일. SAFETY_BLOCKED 감사기록 note는 마스킹 후 저장 (검증: 원문 전화번호 미저장) |
| Prompt Injection | safety_guard에 인젝션 패턴 6종(지시 무시/프롬프트 공개/권한 전환, 한·영) → 고정 거절 문구 + SAFETY_BLOCKED(PROMPT_INJECTION) 기록. SYSTEM_PROMPT에도 방어 조항 |
| 민감정보 저장 최소화 | 세션: 3필드만 / ai_events: 원문 없음 / 감사 note: 마스킹 / 생년월일은 로그 금지 원칙 |

## 8. 테스트 결과

**Sprint G 30/30 PASS** (`tests/run_sprint_g_tests.py`, 결과 CSV) — 요구 12개 시나리오 전부 포함:
Mock 모드 / timeout·retry(3회 시도 복구+소진 예외) / 허용 Tool 실행 / 미허용 Tool 차단(+예약 불변) /
자연어 예약 신청(추출→엔진→PENDING_APPROVAL) / 정보 부족 시 추가 질문 / 본인확인 전 마스킹 /
세션 재시작 복구 / AI Metrics 집계 / Safety 차단 통계 / Rate Limit 429 / mask_pii.

회귀: Sprint D 36/36 · E 31/31 · F 31/31 유지. 원본 data/ 불변 (sessions/ai_events 미생성 확인).

**브라우저 실증**: AI Dashboard 로드 — KPI 카드, 시간대 차트(24구간), 차단 유형
(RESULT_INTERPRETATION·PROMPT_INJECTION), 마스킹된 차단 이력 표시. admin 사이드바 메뉴 연결 확인.

## 9. 발견된 문제

1. tool_loop가 messages 리스트를 계속 변형해 transport가 캡처한 참조로는 시점 검증 불가 → 테스트를 최종 history 기준으로 수정 (기능 정상)
2. 시간대별 집계를 08~18시로 한정하면 심야 테스트에서 0 → 0~23시 전체로 확장
3. 실 Claude API 경로는 Key 부재로 실호출 미검증 — transport 계층까지는 검증 완료, Key 설정 시 SDK 어댑터만 동작하면 됨
4. Rate Limiter가 프로세스 메모리 기반 — 다중 인스턴스 배포 시 Redis 카운터 필요 (세션 스토어와 동일 교체 구조)

## 10. 보완 필요사항

- 채팅 기본 경로의 LLM 전환 (Key 설정 시 orchestrator → tool_loop 자동 스위치) + 대화 히스토리 관리
- 인증번호·알림톡 실발송 연동 (교체 지점 정리 완료 — 발급/발송 함수 2곳)
- 세션 만료(TTL) 정책, IP 단위 rate limit 병행
- 프롬프트 인젝션 룰 확장 + LLM 레벨 가드(시스템 프롬프트는 적용됨) 평가

## 11. 다음 Sprint 제안 (Sprint H)

| 우선순위 | 작업 |
|:---:|------|
| 1 | 채팅 라우터 LLM 경로 전환 (Key 감지 시 tool_loop 기본화, 멀티턴 히스토리, 스트리밍) |
| 2 | 운영 배포: HTTPS/프로세스 매니저/백업, launch 스크립트, 운영 점검 체크리스트 |
| 3 | 알림톡/SMS 실발송 + 인증번호 실발송 (지정된 교체 지점 2곳) |
| 4 | 직원 실사용 파일럿 (관리자 콘솔 + 채팅 위젯) 및 피드백 반영 |
| 5 | SQLite 이관 검토 (JSON 파일 규모 한계 대비) |

---

*CSHSP Sprint G | 2026-07-03 | 천안의료원 건강검진센터*
