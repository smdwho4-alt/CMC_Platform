# ARCHITECTURE.md — CMC Platform (CSHSP)

> Cheonan Medical Center AI Health Screening Concierge Platform.
> 이 문서는 시스템 구조의 **Single Source of Truth**다. 구조 변경 시 반드시 갱신한다.

---

## 1. 시스템 개요

CMC Platform은 세 개의 실행 영역으로 구성된다.

1. **Frontend** — 정적 HTML/JS (예약, 관리자 콘솔, AI 채팅 위젯)
2. **Backend (Python)** — FastAPI 기반 REST API + AI 에이전트 오케스트레이션
3. **Backend (Google Apps Script)** — Google Sheets를 예약 원장(ledger)으로 사용하는 별도 백엔드

두 백엔드(Python API / Apps Script)는 **독립적으로 존재**하며, 예약 데이터의 최종 저장소는 현재 **Google Sheets**(Apps Script 경유)와 **로컬 JSON**(`data/`, Python 계층)으로 이원화되어 있다. 이는 개발 단계별로 순차 도입된 결과이며, 향후 일원화 필요 여부는 [DECISIONS.md](DECISIONS.md)에서 다룬다.

---

## 2. 디렉토리 구조와 책임

```
CMC_Platform_new/
├── app/            프론트엔드(예약 UI, 대시보드) + Apps Script 백엔드
│   ├── pages/        HTML 페이지 (reservation_v2, admin_dashboard_v3 등)
│   ├── services/      JS 서비스 계층 (Sheets/Calendar/Gmail 어댑터)
│   ├── apps_script/    Google Apps Script 코드 (.gs) — 현재 배포본: sheets_api_v3_final.gs
│   ├── components/     공통 UI 컴포넌트
│   ├── data/          프론트엔드 상수 (프로그램 목록, 샘플 데이터)
│   ├── styles/         CSS
│   └── docs/          ERD/워크플로우/시트구조 다이어그램 (HTML)
│
├── admin/          Sprint C 관리자 콘솔 (SPA, Mock API 어댑터 기반)
├── chat/           Sprint E/F AI 채팅 위젯 (SSE 스트리밍)
│
├── src/            Python 백엔드 (Sprint A~I)
│   ├── core/         Core Data Layer — 20 Entity JSON 로더/검증 (Sprint A)
│   ├── reservation/   예약 엔진 — 상태머신, Slot 검증, 감사로그 (Sprint B)
│   ├── questionnaire/ 문진 처리 (Sprint C)
│   ├── api/          FastAPI REST 서버, 라우터 (Sprint D)
│   ├── agents/        AI 에이전트 오케스트레이터 + 5종 서브에이전트 (Sprint E~G)
│   ├── dashboard/     AI 상담 통계 (Sprint G)
│   ├── security/       Rate Limit, PII 마스킹 (Sprint G/H)
│   ├── workers/        알림 발송 워커 (Sprint H)
│   └── deploy/         운영 절차 문서 (백업/프로세스/체크리스트)
│
├── data/           20 Entity JSON 파일 (Core Data Layer의 실제 저장소)
├── docs/           Sprint 산출 문서, 운영 매뉴얼
└── tests/          Sprint별 pytest 스크립트 + 결과 CSV
```

---

## 3. 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | HTML5 / CSS3 / Vanilla JavaScript (프레임워크 없음) |
| 프론트-백엔드 연동 | Google Sheets API v4 (Phase 3) → Apps Script Web App (Phase 4+, 현재 표준) |
| 외부 연동 | Google Calendar API, Gmail API |
| Backend API | Python 3.9+ / FastAPI / uvicorn (포트 8600) |
| AI | Anthropic Claude API (SDK 0.116) + 규칙 기반 폴백 |
| 데이터 저장 | JSON 파일 (20 Entity, `data/`) — append-only 감사로그/AI 이벤트 |
| 예약 원장 저장 | Google Sheets (29컬럼, Apps Script `sheets_api_v3_final.gs` 경유) |
| 배포 | 로컬 웹서버(`npx serve`/`http.server`) + Windows Task Scheduler(NSSM) |
| 버전 관리 | 없음 (git 미사용, 파일명에 `_v2/_v3/_final/_new` 등 버전 접미사로 이력 관리) |

---

## 4. 핵심 데이터 흐름

### 4.1 예약 생성 (환자 → Google Sheets)

```
reservation_v2_new.html
  → config_v2_new.js (dataSource='google')
  → google_sheets_service_v2_new.js (CMC_SheetsServiceV2.create)
  → Apps Script Web App (POST ?action=create)
  → sheets_api_v3_final.gs :: _actionCreate()
       - LockService 획득
       - 예약번호 채번 (YYYYMMDD-NNNN, 서버 채번)
       - Sheet.appendRow()
       - birth/wishDate/wishTime 텍스트 서식 재설정 (DateFix, 배포 대기중 — PROJECT_STATUS.md 참조)
       - LockService 해제
  → Google Sheets '종합검진_예약대장'
```

### 4.2 관리자 콘솔 (Sprint C)

```
admin/index.html → admin.js (UI 컨트롤러)
  → admin_api.js (Mock API 어댑터, reservation_engine.py 로직을 JS로 미러링)
     - Mock 모드: data/*.json 직접 fetch
     - Live 모드(Sprint D 이후): REST API(/api/...) 호출
  → RBAC: ROLE-STAFF만 승인 가능, ROLE-AI-AGENT는 승인 불가
```

### 4.3 AI 채팅 (Sprint E~G)

```
chat/chat_widget.js (SSE)
  → POST /api/agents/chat/stream
  → routes_agents.py
  → agent_orchestrator.handle_message()
       1) safety_guard.check() — 35개 금지문항 차단
       2) 의도 분류 (규칙 기반, Claude API는 ANTHROPIC_API_KEY 설정 시 tool_loop 경유)
       3) 서브에이전트 위임: reservation / recommendation / questionnaire / crm / operation
  → SSE 응답 (메시지 청크 + meta 이벤트: blocked/needVerification/needInput/success)
```

**예약 확정 3중 방어선**: Safety Guard → Allowed Tool 리스트 → API 측 권한 검증(403). AI 에이전트는 예약을 직접 확정(CONFIRMED)할 수 없고 PENDING_APPROVAL까지만 생성한다.

### 4.4 예약 상태 머신 (`src/reservation/state_machine.py`)

```
(생성) → PENDING_APPROVAL → CONFIRMED → COMPLETED
                 │                 │
                 └──→ REJECTED     └──→ CANCELLED
```
- `approve_reservation()`은 ROLE-STAFF/ROLE-ADMIN만 호출 가능
- 모든 전이는 `reservation_audit.py`를 통해 append-only 감사로그(`data/audit_logs.json`)에 기록

---

## 5. 데이터 모델 (20 Entity)

전체 정의는 `docs/CSHSP_Core_Data_Layer_Sprint_A.md` 참조. 그룹 요약:

| 그룹 | 파일 | 성격 |
|---|---|---|
| 예약 핵심 | reservations, patients, businesses | PII 포함 |
| 마스터 데이터 | programs, optional_tests, rooms, equipment | 참조용 상수 |
| 인력 | doctors, nurses, users, roles | PII/권한 |
| 일정 | schedules, slots | 운영 캘린더 |
| 문진/동의 | questionnaires, consents | 수집 항목 |
| CRM/통계 | crm, dashboard, statistics | 집계·상담 |
| 로그 | audit_logs, notifications, ai_events | append-only |

---

## 6. 보안 경계

| 계층 | 방어 |
|---|---|
| AI 응답 | Safety Guard (35개 금지 응답 카테고리 차단) |
| AI → 예약 확정 | 서버측 Allowed Tool 화이트리스트 + RBAC 403 |
| API | Rate Limit (기본 30회/60초, 슬라이딩 윈도우) |
| 세션 저장 | patientId/verifyState/pendingCode만 저장 — 대화 원문 미저장 |
| 로그 | `privacy_logger.py`로 전화번호/주민번호 마스킹 |
| Apps Script 동시 접근 | LockService로 쓰기 직렬화 |
| 다중 프로세스(API 서버) | `file_lock.py` (FileJsonLock) |

운영 전 필수(미구현): 관리자 로그인 인증, HTTPS.

---

## 7. 알려진 아키텍처 부채

1. **이중 백엔드**: Google Sheets(Apps Script) vs 로컬 JSON(Python) — 두 저장소가 동기화되어 있지 않음. 관리자 콘솔은 아직 로컬 JSON/Mock API 기준으로 동작하고, 환자용 예약 화면은 Sheets 기준으로 동작.
2. **버전 관리 부재**: git 미사용, 파일명 접미사(`_v2`, `_v3`, `_final`, `_new`)로 이력 관리 — 롤백/diff 추적 어려움.
3. **JSON 파일 기반 저장**: 동시성은 파일 락으로 처리하나 확장성 한계 존재 (`docs/SQLite_Migration_Plan.md` 참조, 미착수).

이 부채들에 대한 결정 여부는 [DECISIONS.md](DECISIONS.md)와 [ROADMAP.md](ROADMAP.md)에서 관리한다.
