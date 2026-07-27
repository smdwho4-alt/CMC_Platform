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
- **부채**: Google Sheets(예약 원장) ↔ 로컬 JSON(Core Data Layer) 이원화는 **`Reservation` Entity에 한해 ADR-013으로 해소**(Sheets를 SSOT로 확정, 2026-07-27). `Patient`/`CRM`/`AuditLog` 등 나머지 Entity는 이원화 이슈 자체가 없었으므로(로컬 JSON 단일 저장) 영향 없음. ARCHITECTURE.md §1/§7 참조.

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
- **상태**: ✅ **구현 완료**(2026-07-12, Live 검증 포함 — PROJECT_STATUS.md §2-1 참조). *(Sprint 4 Commit 1에서 정정: 종전 "⚠️ 구현 미착수" 표기는 DEV-003 완료 이후 갱신되지 않은 낡은 정보였음)*

---

## ADR-008: 버전 관리는 git 대신 파일명 접미사로 수행

- **배경**: 이 프로젝트는 git 저장소로 초기화되지 않았고, 상위 폴더(건강검진)의 작업 규칙("기존 파일 덮어쓰지 않음, 새 파일은 `_new` 접미사")을 그대로 계승해왔다.
- **결정**: `_v2`, `_v3`, `_final`, `_new` 등 파일명 접미사로 버전 이력을 관리. Architecture Freeze 문서(CLAUDE.md 등 5종)는 향후 세션에서 지침으로 실제 동작해야 하므로 표준 파일명(접미사 없음)으로 예외 적용(2026-07-04 사용자 확정).
- **상태**: ⚠️ **Superseded by ADR-012**(2026-07-28). 이 ADR이 전제한 "git 저장소로 초기화되지 않았다"는 배경은 결정 직후인 2026-07-06에 git 저장소가 실제로 초기화되면서 사실과 어긋나기 시작했고, 이후 커밋 기반 운영이 계속됐다(Sprint 4 Architecture Gate에서 확인). 파일명 접미사 관행 자체는 ADR-012에서도 보조 수단으로 유지되므로 이 ADR 원문은 삭제하지 않고 이력으로 보존한다.

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

---

## ADR-012: 버전 관리는 Git 커밋 기반으로 운영한다 (Supersedes ADR-008)

- **배경**: ADR-008(2026-07-04)은 "git 저장소로 초기화되지 않았다"는 전제로 파일명 접미사만을 버전 관리 수단으로 결정했으나, 불과 2일 뒤인 2026-07-06에 git 저장소가 실제로 초기화되어(최초 커밋 `0d6e3a2`) 이후 오늘까지 커밋 기반 운영이 예외 없이 계속됐다(`v1.0.0-pilot`/`v1.1.0-beta1` 태그가 origin에도 push됨, Single Admin Portal Sprint 1~3 전체가 Commit 단위로 진행됨). Sprint 4 Architecture Gate에서 이 불일치가 공식 식별됐다.
- **결정**: 이 프로젝트의 버전 관리는 **Git 커밋을 기준**으로 운영한다. 파일명 접미사(`_new`/`_v2`/`_v3`/`_final`) 관행은 폐지하지 않고 상위 폴더 규칙 계승 및 "원본 파일 무수정 원칙"을 위한 **보조 수단**으로 병행 유지한다. `git add .`/`git add -A` 금지, 커밋 전 `git diff --cached --name-only` 확인, PM이 명시 승인한 경우에만 push하는 원칙을 확정한다. 상세 정책(Branch/Commit/Release)은 `ADR-012_Git_Based_Version_Control.md`를 정식 근거 문서로 삼는다.
- **대안 검토**: 파일명 접미사 체계로 전면 회귀(기각 — 이미 32개 커밋과 2개 릴리스 태그가 git에 쌓여 있어 회귀 시 이력 손실), git과 파일명 접미사 중 하나만 남기고 완전 통일(기각 — 두 체계 모두 실사용 근거가 있어 공존을 인정하는 쪽이 현실적).
- **상태**: ✅ **Accepted** (2026-07-28, Sprint 4 Commit 1). ADR-008을 Supersede한다.

---

## ADR-013: 예약(Reservation) Master Data / SSOT는 Google Sheets로 확정한다

- **배경**: 예약 데이터가 Google Sheets(수검자 웹 폼 경로)와 로컬 JSON(`reservation_engine.py`, AI 채팅·관리자 콘솔 경로) 두 저장소에 나뉘어 있고 상호 동기화 코드가 없음이 `Platform_Integration_Architecture_Review_v1.0.md`(Sprint 3.5)와 `Sprint4_Architecture_Gate_Report_v1.0.md`(Sprint 4 Architecture Gate)에서 확인됐다. Single Admin Portal(Sprint 1~3)을 포함한 통합 작업을 진행하려면 공식 원장을 하나로 확정해야 한다.
- **결정**: **예약 Master Data(SSOT)는 Google Sheets로 확정한다.** 계층 역할은 Google Sheets(Data/SSOT) → Google Apps Script(Integration Layer) → FastAPI(Business/Security/AI Layer) → Single Admin Portal(Presentation Layer)로 정의한다(ARCHITECTURE.md §1 계층 구조 참조). **기존 로컬 JSON 예약 데이터(`data/reservations.json`)는 삭제하지 않으며, 신규 예약의 공식 원장으로는 더 이상 사용하지 않되 기존 기능 호환·테스트 Fixture·마이그레이션 검증·Rollback 참고 용도로 유지한다.** 이 결정은 `Reservation` Entity에 한정되며, `Patient`/`CRM`/`AuditLog` 등 나머지 19개 Core Data Layer Entity(ADR-003)의 로컬 JSON 저장 방식에는 영향을 주지 않는다.
- **근거**: 상세 필드 매핑·ID 충돌·상태값 매핑·PII·마이그레이션 범위 분석은 `Reservation_Data_Mapping_and_Migration_Plan_v1.0.md`, 계층별 목표 흐름(예약/승인/Slot/문진)은 `Reservation_Core_Architecture_v1.0.md`를 정식 근거 문서로 삼는다. 현재 로컬 JSON 예약 데이터는 5건(전부 QA 더미)으로 확인되어 이관 부담이 낮다.
- **대안 검토**: 로컬 JSON(Core Data Layer)을 SSOT로 삼고 Sheets를 리포팅 전용 미러로 전환(기각 — 수검자 웹 폼의 유일한 실제 접수 경로가 이미 Sheets이고, Single Admin Portal이 이미 Sheets 조회 기준으로 구축되어 있어 전환 비용이 더 큼).
- **영향**: 승인 게이트(현재 로컬 JSON에만 존재)·Slot 정원 통제(현재 로컬 JSON에만 존재)·문진 참조 키(현재 로컬 JSON `Reservation.id` 참조)를 Sheets 기준으로 재설계해야 하는 과제가 남으며, 각각 Sprint 4 Commit 2/3/4의 PM 승인 대상이다(`Sprint4_Implementation_Plan_v1.0.md` 참조).
- **상태**: ✅ **Accepted** (2026-07-27, PM 최종 결정 — Sprint 4 Commit 0/1에서 문서 반영).
