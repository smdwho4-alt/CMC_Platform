# DECISIONS.md — CMC Platform (CSHSP)

> 아키텍처적으로 의미 있는 결정을 기록한다(ADR, Architecture Decision Record). 새 결정은 파일 하단에 추가하고, 기존 항목은 상태만 갱신한다(내용 삭제 금지).

각 항목 형식: **배경 → 결정 → 대안 → 상태**

---

## ADR-001: 데이터 소스를 localStorage → Google Sheets(Apps Script)로 단계적 전환

- **배경**: 초기(Phase 1)는 브라우저 localStorage로 예약 데이터를 저장. 여러 기기/직원이 공유해야 하는 운영 요구가 생김.
- **결정**: Phase 3에서 Google Sheets API v4 직접 호출 → Phase 4에서 Google Apps Script Web App 경유 방식으로 전환. OAuth 없이 URL 배포로 접근 가능하게 함.
- **대안 검토**: 자체 DB 서버 구축(당시 인프라·인력 부담으로 보류), Firebase(검토 기록 없음).
- **상태**: ✅ 확정, Phase 4 이후 표준. 현재 배포본: `app/apps_script/sheets_api_v3_final.gs`.

---

## ADR-002: 예약 시트를 18컬럼 → 29컬럼으로 확장

- **배경**: Phase 4의 18컬럼 구조로는 접수·검진·결제·결과 단계를 표현할 수 없었음.
- **결정**: Phase 4.5에서 29컬럼으로 확장 (`sheets_api_v2_new.gs`). ERD/워크플로우 다이어그램(`app/docs/`)으로 문서화.
- **상태**: ✅ 확정.

---

## ADR-003: Core Data Layer를 JSON 파일 기반으로 구축 (DB 서버 미도입)

- **배경**: Sprint A에서 예약 엔진 이하 전체 서비스(20 Entity)를 지원할 데이터 계층이 필요.
- **결정**: SQLite/PostgreSQL 등 DB 서버 대신 JSON 파일(`data/*.json`) + 파일 락(`FileJsonLock`) 기반으로 구축. 빠른 개발 속도와 낮은 운영 부담을 우선.
- **대안 검토**: SQLite 마이그레이션 계획은 문서화해 둠(`docs/SQLite_Migration_Plan.md`)하되 착수하지 않음.
- **상태**: ✅ 확정(파일럿 단계 기준). 트래픽 증가 시 재검토 필요 — [ROADMAP.md](ROADMAP.md) SQLite 마이그레이션 항목 참조.
- **부채**: Google Sheets(예약 원장) ↔ 로컬 JSON(Core Data Layer) 이원화 미해결. ARCHITECTURE.md §7 참조.

---

## ADR-004: AI 에이전트는 규칙 기반을 기본으로 하고 Claude API를 옵트인 경로로 둠

- **배경**: Sprint E에서 AI 컨시어지 기능 도입. 초기부터 LLM에 전면 의존하면 안전성 검증(금지응답 차단 등)이 어려움.
- **결정**: 의도 분류·응답 로직을 규칙 기반으로 우선 구현(Sprint E), `ANTHROPIC_API_KEY` 설정 시에만 Claude API 경로(`claude_client.py` + `tool_loop.py`)로 자동 전환(Sprint G). 미설정 시 규칙 기반으로 자동 폴백.
- **대안 검토**: Claude API 전면 도입 후 검증 — 초기 파일럿 단계의 예측 불가능성 리스크로 기각.
- **상태**: ✅ 확정. LLM 기반 의도 분류로의 완전 전환은 향후 Sprint 과제로 보류(ROADMAP.md 참조).

---

## ADR-005: AI 에이전트는 예약을 직접 확정할 수 없다 (3중 방어)

- **배경**: AI가 오판단으로 예약을 임의 확정하는 리스크 차단 필요.
- **결정**: (1) Safety Guard 35개 금지응답 필터, (2) 서버측 Allowed Tool 화이트리스트, (3) API 레벨 RBAC(403, ROLE-STAFF/ADMIN만 승인 가능) — 3중 방어. AI 에이전트가 생성할 수 있는 최대 상태는 `PENDING_APPROVAL`.
- **상태**: ✅ 확정, Sprint I 품질 게이트에서 검증 완료(금지응답 35/35 차단).

---

## ADR-006: 세션 저장 시 대화 원문을 저장하지 않는다

- **배경**: 개인정보(PII) 노출 최소화 요구.
- **결정**: `session_store.py`는 `patientId`, `verifyState`, `pendingCode` 3개 필드만 영속화. 대화 메시지 원문은 저장하지 않음. 로그는 `privacy_logger.py`로 전화번호/주민번호를 마스킹.
- **상태**: ✅ 확정, Sprint I 개인정보 검증(PASS) 기준선.

---

## ADR-007: 관리자 예약관리 Sheets 연동은 원본 파일을 수정하지 않고 신규 파일로 추가 (DEV-003)

- **배경**: 기존 `admin_reservations_new.html`(localStorage 기반)이 이미 운영 중. Sheets 연동판으로 교체 시 회귀 리스크.
- **결정**: `admin_reservations_v2_new.html`을 신규로 추가하고 원본은 보존. 범위는 목록/상세/상태변경/메모저장으로 한정(대시보드/권한관리는 제외). 상태변경·메모저장에는 Lock 필수 적용. 메모 필드는 `update` 액션으로 `{note}` 단일 필드만 전송(옵션 A로 확정, PM 2차 승인).
- **대안 검토**: 기존 파일 직접 수정(회귀 리스크로 기각), 메모를 별도 이력 배열로 관리(옵션 B, 과설계로 기각).
- **상태**: ✅ 설계 확정(`DEV-003_..._Design_Final_new.md`). ⚠️ **구현 미착수** — ROADMAP.md 참조.

---

## ADR-008: 버전 관리는 git 대신 파일명 접미사로 수행

- **배경**: 이 프로젝트는 git 저장소로 초기화되지 않았고, 상위 폴더(건강검진)의 작업 규칙("기존 파일 덮어쓰지 않음, 새 파일은 `_new` 접미사")을 그대로 계승해왔다.
- **결정**: `_v2`, `_v3`, `_final`, `_new` 등 파일명 접미사로 버전 이력을 관리. Architecture Freeze 문서(CLAUDE.md 등 5종)는 향후 세션에서 지침으로 실제 동작해야 하므로 표준 파일명(접미사 없음)으로 예외 적용(2026-07-04 사용자 확정).
- **상태**: ✅ 확정. 단, 코드 변경 이력 추적의 한계는 알려진 부채로 남김(ARCHITECTURE.md §7).

---

## ADR-009 (미결, 후보): STEP1.5 DateFix 배포 이후 재발 방지 정책

- **배경**: DateFix 수정 코드는 작성됐으나 배포 절차 누락으로 실제 반영되지 않은 채 방치됨(재QA 1차 실패로 발견). 코드 작성 완료와 실제 배포 사이의 확인 절차 부재가 근본 원인.
- **결정 후보**: 배포 후 자동 스모크 체크(`?action=ping` + 더미 재QA)를 배포 체크리스트에 필수 항목으로 명문화.
- **상태**: 🔲 미결 — Sprint J 이전 필수 해결 과제로 ROADMAP.md에 등록됨.

---

## ADR-010: Architecture Freeze는 미해결 버그와 독립적으로 수행한다

- **배경**: STEP1.5 DateFix(ADR-009)처럼 알려진 미해결 이슈가 있는 상태에서 Architecture Freeze(Sprint 0)를 진행해야 하는 상황 발생. Freeze의 목적이 "완벽한 무결점 상태 확정"인지 "설계·구조·표준의 SSOT 확정"인지 정의가 필요했음.
- **결정**: Architecture Freeze는 **현재 프로젝트의 설계, 구조, 표준 문서를 Single Source of Truth(SSOT)로 확정하는 단계**로 정의한다. 미해결 이슈(버그, 미구현 기능 등)가 존재하더라도 Architecture Freeze는 수행·완료할 수 있다. 단, 미해결 이슈는 반드시 PROJECT_STATUS.md의 Known Issues와 ROADMAP.md의 필수 해결 과제로 등록해 추적한다.
- **Architecture Freeze와 Pilot Ready(운영 파일럿 투입 가능 여부)는 서로 다른 개념으로 분리 관리한다.**
  - Architecture Freeze 완료 = 구조·표준 문서 확정 (본 ADR 기준으로 2026-07-04 완료 선언)
  - Pilot Ready = 운영 투입 전제조건(현재는 STEP1.5 DateFix 등 Known Issues) 충족 여부. 별도로 재평가한다.
- **대안 검토**: 모든 Known Issue 해결 후 Freeze 선언(기각 — 구조 확정과 버그 수정을 하나의 게이트로 묶으면 SSOT 문서화 자체가 무기한 지연됨).
- **상태**: ✅ 확정 (2026-07-04). 이 결정에 따라 STEP1.5 DateFix는 Architecture Freeze의 차단 조건이 아니며, Sprint J 이전 필수 해결 과제로만 관리한다.

---

## ADR-011: Pilot 구조는 v0.9.0 현재 상태로 Freeze하고, 구조 변경 작업은 v1.0으로 이관한다

- **배경**: `docs/STRUCTURE_REORG_ANALYSIS_new.md`에서 목표 구조(CSHSP/) 대비 현재 구조를 분석한 결과, 저위험 이동 후보 15개 파일(deployment/ 3개, archive/ 12개)을 포함한 구조 재편 여지가 확인되었다. 그러나 Pilot 운영 개시가 임박한 시점에 구조 변경 작업을 병행하면 STEP1.5 DateFix 등 더 시급한 이슈 해결이 지연되고, 구조 변경 자체가 새로운 회귀 리스크를 유발할 수 있다.
- **결정**: **Pilot용 프로젝트 구조는 v0.9.0(현재 상태)로 Freeze한다.** `docs/STRUCTURE_REORG_ANALYSIS_new.md`를 구조 관련 기준 문서(baseline)로 삼아 향후 재편 시 그대로 활용하되, 구조 변경 작업 자체는 지금 착수하지 않는다. 대신 아래 순서로 작업을 진행한다.
  1. STEP1.5 DateFix 배포 + 재QA
  2. 전체 QA (회귀 테스트 스위트 + 시나리오 리허설)
  3. v0.9.0 Pilot Release (Pilot 운영 개시)
- 구조 변경이 필요한 항목(§`docs/STRUCTURE_REORG_ANALYSIS_new.md` §9 "Pilot 이후 정리 대상" 포함, `src/`·`app/` 내부 재편 등)은 전부 **Pilot 종료 후 v1.0 작업으로 이관**한다.
- **대안 검토**: 구조 재편(저위험 15개 파일 이동)을 먼저 수행한 뒤 DateFix 작업 착수(기각 — 급하지 않은 정리 작업이 Critical 이슈 해결보다 먼저 진행될 이유가 없고, 리소스가 분산됨).
- **상태**: ✅ 확정 (2026-07-04). 구조 관련 모든 논의는 `docs/STRUCTURE_REORG_ANALYSIS_new.md`를 기준으로 하며, 실제 이동/재편 착수는 v1.0 단계에서 별도 승인 후 진행한다.
