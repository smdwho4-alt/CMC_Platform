# ARCHITECTURE.md — CMC Platform (CSHSP)

> Cheonan Medical Center AI Health Screening Concierge Platform.
> 이 문서는 시스템 구조의 **Single Source of Truth**다. 구조 변경 시 반드시 갱신한다.

---

## 1. 시스템 개요

CMC Platform은 세 개의 실행 영역으로 구성된다.

1. **Frontend** — 정적 HTML/JS (예약, 관리자 콘솔, AI 채팅 위젯)
2. **Backend (Python)** — FastAPI 기반 REST API + AI 에이전트 오케스트레이션
3. **Backend (Google Apps Script)** — Google Sheets를 예약 원장(ledger)으로 사용하는 별도 백엔드

### 1-1. 계층 구조(Layer Model) — Reservation Core 기준(ADR-013, 2026-07-27 확정)

예약(Reservation) 도메인은 아래 4계층으로 통일한다. 상세 흐름(예약/승인/Slot/문진)은 `Reservation_Core_Architecture_v1.0.md`를 정식 근거 문서로 삼는다.

| 계층 | 구성요소 | 책임 |
|---|---|---|
| **Presentation** | Single Admin Portal(`admin_portal_new.html`), 수검자 웹 폼(`reservation_v3_new.html`) 등 | 사용자 화면 |
| **Business** | FastAPI(`src/api/*`, `src/agents/*`) | 인증·RBAC·승인 워크플로·감사로그·AI 오케스트레이션 |
| **Integration** | Google Apps Script(`sheets_api_v3_final.gs`) | Sheets 접근 중개(action 기반 API) |
| **Data** | **Google Sheets**(예약 Master Data / SSOT) | 예약 데이터의 유일한 영구 저장소 |

**예약(Reservation) 데이터의 공식 SSOT는 Google Sheets로 확정됐다(ADR-013).** 기존 로컬 JSON 예약 데이터(`data/reservations.json`)는 삭제하지 않으나 신규 예약의 공식 원장으로는 더 이상 사용하지 않으며, 기존 기능 호환·테스트 Fixture·마이그레이션 검증·Rollback 참고 용도로만 유지한다. **이 결정은 `Reservation` Entity에 한정된다** — `Patient`/`CRM`/`AuditLog` 등 나머지 19개 Core Data Layer Entity(ADR-003)는 여전히 로컬 JSON(`data/`)이 유일한 저장소이며 이번 결정의 영향을 받지 않는다.

승인 게이트·Slot 정원 통제·Policy 검증(휴진일/의료진/검사실/장비/프로그램 제한)은 **Sprint 4 Commit 2/3/3A/5-1/5-2에서 Sheets 기준으로 재배선 완료**됐다(`routes_admin_portal.py::_process_reservation_approval()`이 승인 API 경유로 `POST /api/admin/reservations/{no}/approve|reject`에서 Slot 점유·Policy 검증·Audit을 전부 수행). Legacy Portal(`admin_reservations_v2_new.html`)을 통한 우회는 Sprint 6 Commit6-1에서 "예약확정" 전이에 한해 부분 차단됐다(§7 항목4). **문진 참조 키**(현재 로컬 JSON `Reservation.id` 참조)만 Sheets 기준 재설계가 **여전히 미착수**다 — 원래 계획된 "Sprint 4 Commit 4(문진)"가 실행되지 않았기 때문(ROADMAP.md 참조). 즉 이 문서 갱신 시점(Sprint 7 Commit7-1, 공식 Baseline `4f21d0e`)에는 **SSOT 지정에 더해 승인/Slot/Policy 3개 축의 재배선까지 완료됐고, 문진 참조 키 재배선만 남아 있다.**

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
| 버전 관리 | **Git 커밋 기반**(ADR-012, 2026-07-06 저장소 초기화 이후 표준) + 파일명 접미사(`_v2/_v3/_final/_new`, 상위 폴더 규칙 계승, 보조 수단) 병행 |

---

## 4. 핵심 데이터 흐름

### 4.1 예약 생성 (환자 → Google Sheets)

```
reservation_v3_new.html (Sprint 7 Commit7-1 정정 — DEV-004 이후 현재 서비스 중인 실제 파일. reservation_v2_new.html은 보존된 이전 버전, 현재 서비스 라인업 아님)
  → config_v2_new.js (dataSource='google')
  → google_sheets_service_v2_new.js (CMC_SheetsServiceV2.create)
  → Apps Script Web App (POST ?action=create)
  → sheets_api_v3_final.gs :: _actionCreate()
       - LockService 획득
       - 예약번호 채번 (YYYYMMDD-NNNN, 서버 채번)
       - Sheet.appendRow()
       - birth/wishDate/wishTime 텍스트 서식 재설정 (DateFix, 2026-07-12 실배포 완료 — PROJECT_STATUS.md §2 참조)
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

1. **이중 백엔드(Reservation 한정, 대부분 해소)**: Google Sheets(Apps Script) vs 로컬 JSON(Python) — 예약(Reservation) 데이터에 한해 SSOT가 Google Sheets로 확정됐다(ADR-013). 승인 게이트·Slot 정원 통제·Policy 검증의 실제 재배선(코드 변경)은 Sprint 4 Commit 2/3/3A/5-1/5-2에서 완료됐다(§1-1 참조) — **문진 참조 키 재배선만 여전히 미착수**(원래 계획된 Sprint 4 Commit 4, 시점 미정). `Patient`/`CRM`/`AuditLog` 등 다른 Entity는 애초에 이원화 대상이 아니었으므로 이 항목과 무관.
2. **버전 관리 이원화**: Git 커밋(표준, ADR-012)과 파일명 접미사(`_v2`, `_v3`, `_final`, `_new`, 보조 수단)가 병행되어 "이 파일의 진짜 최신 이력"을 확인하려면 두 체계를 모두 봐야 하는 부채는 남아있음 — git 사용 자체가 없다는 서술은 ADR-012로 정정됐으나, 두 체계 공존 자체는 해소되지 않았다.
3. **JSON 파일 기반 저장**: 동시성은 파일 락으로 처리하나 확장성 한계 존재 (`docs/SQLite_Migration_Plan.md` 참조, 미착수).
4. **Legacy 승인 우회 경로**(Sprint 4 Commit 3A에서 공식 등록, 2026-07-28 — **Sprint 6 Commit6-1(2026-07-29)에서 부분 해소**): `admin_reservations_v2_new.html`에서 직원이 예약 상태를 직접 `예약확정`으로 변경하면 Single Admin Portal의 승인 API(`POST /api/admin/reservations/{no}/approve`, Sprint 4 Commit 3/3A/5-2)가 수행하는 Slot 존재·상태·정원·중복·Policy(휴진일/의료진/검사실/장비/프로그램 제한) 검사와 Audit 기록을 전혀 거치지 않던 문제였다. **Sprint 6 Commit6-1에서 이 화면의 `예약확정` 저장만 클라이언트 측에서 차단**하도록 수정해(`AA.saveStatus()`의 `approvalBlocked` 가드), 실제 정원/Policy 우회 경로는 제거됐다(TD-S5-04, Partial Resolved). 단, `검진완료`/`일정변경`/`예약취소`/`거절` 전이는 `reservation_approval_states.py`가 원래부터 "이 화면이 전담한다"고 설계한 범위이므로(Admin Portal에 대응 기능이 없음) 의도적으로 그대로 남아 있다 — 이는 우회가 아니라 기존 설계다. 완전 해소(Admin Portal에 저 3개 전이 기능 신설)는 별도 Sprint 대상(상세: `Sprint5_Commit5_3_3_Legacy_Migration_Preparation_v1.0.md`, `Sprint6_Design_Freeze_v1.0.md`).

이 부채들에 대한 결정 여부는 [DECISIONS.md](DECISIONS.md)와 [ROADMAP.md](ROADMAP.md)에서 관리한다.
