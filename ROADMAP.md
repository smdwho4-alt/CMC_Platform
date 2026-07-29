# ROADMAP.md — CMC Platform (CSHSP)

> 완료된 이력과 향후 계획을 함께 관리한다. Sprint 완료 시 "완료된 작업"으로 이동시키고, 새 Sprint 계획은 하단에 추가한다.

---

## 완료된 작업 (Sprint A ~ Sprint I, Sprint 2)

| Phase/Sprint | 내용 | 상태 |
|---|---|---|
| Phase 1 | 예약 UI, localStorage 기반 | ✅ |
| Phase 2 | 대시보드, 관리자 콘솔 초안 | ✅ |
| Phase 3 | Google Sheets/Calendar/Gmail 직접 연동(GWS 어댑터) | ✅ |
| Phase 4 | Apps Script Web App 경유 연동 (18컬럼) | ✅ |
| Phase 4.5 | 예약 시트 29컬럼 확장 + ERD/워크플로우 문서화 | ✅ |
| STEP0-1 | 예약 쓰기 경로 배선·검증 | ✅ |
| STEP1.5 | DateFix QA — 결함 발견 및 수정 코드 작성 | ✅ **완료**(2026-07-12, GAS Version 5 재배포·재QA까지 완료 — PROJECT_STATUS.md §1/§2 참조) |
| Sprint A | Core Data Layer (20 Entity JSON, 로더/검증) | ✅ |
| Sprint B | Reservation Engine (상태머신, Slot, 감사로그) | ✅ |
| Sprint C | Admin Console (7개 메뉴, Mock API) | ✅ |
| Sprint D | API Layer (FastAPI, 36 엔드포인트) | ✅ |
| Sprint E | 규칙 기반 AI 에이전트 (5종) | ✅ |
| Sprint F | AI Chat Widget (SSE 스트리밍) | ✅ |
| Sprint G | Claude API 연동, 세션/Rate Limit/AI Dashboard | ✅ |
| Sprint H | 파일럿 전환 절차, 장애 대응, 백업·복구 | ✅ |
| Sprint I | 품질 게이트 (16항목) — PASS | ✅ |
| Sprint 2 *(Dashboard 트랙)* | Dashboard v3 (운영센터, KPI 6종, AI 추천) | ✅ |
| DEV-003 | 관리자 예약관리 Sheets Live 연동(`admin_reservations_v2_new.html`) | ✅ **완료**(2026-07-12, 테스트 60/60 PASS, Live 검증 완료 — PROJECT_STATUS.md §2-1 참조) |
| DEV-004 | 종합검진 선택검사 Rule 기반 UI 전면 개편 | ✅ **완료**(2026-07-12, `v1.1.0-beta1` 태그) |
| Single Admin Portal Sprint 1 *(별도 번호 트랙, 위 "Sprint 2 (Dashboard 트랙)"과 무관)* | Admin Portal Integration Foundation — 조회 계층/관리자 조회 API/Portal 셸 | ✅ |
| Single Admin Portal Sprint 2 | Single Admin Portal Integration — Dashboard/예약조회/예약상세/통계 | ✅ |
| Single Admin Portal Sprint 3 | Operator First — RBAC/CRM통합/Audit/AI지원/운영자UX/통합QA(6 Commit) | ✅ |
| Sprint 3.5 | Platform Integration Architecture Review(READ ONLY) | ✅ |
| Sprint 4 Commit 0 | Reservation Core Integration — 문서 Baseline(ADR-012, Reservation Core Architecture 등) | ✅ |
| Sprint 4 Commit 1 | SSOT 문서 정렬 | ✅ |
| Sprint 4 Commit 2 | 예약 승인(Reservation Approval Foundation, ADR-014) | ✅ |
| Sprint 4 Commit 3 | Slot 통합(Reservation Slot Integration) | ✅ |
| Sprint 4 Commit 3A | Slot Integration Hardening(ADR-015 Draft) | ✅ |
| Sprint 4 Commit 5-1 | Validation Context + Program Mapping Helper | ✅ |
| Sprint 4 Commit 5-2(A 포함) | Approval Pipeline Policy Integration(Policy Layer/Execution Layer 분리) | ✅ |
| Sprint 5 Commit5-3.1 | Portal Error Contract Parser(`parseApiError()`) | ✅ |
| Sprint 5 Commit5-3.2 | Admin Portal UX Integration(Parser 연결, Timeout, `_SLOT_CONFLICT_CODES` P0 수정) | ✅ |
| Sprint 5 Commit5-3.3 | Legacy Migration Preparation(설계 문서) | ✅ |
| Sprint 6 Commit6-1 | Legacy Reservation Approval Transition Guard | ✅ |
| Sprint 6 Commit6-2 | Technical Debt Cleanup(TD-S5-01/02) | ✅ |
| Sprint 6 Commit6-3 | Regression·Documentation·Sprint6 Closeout | ✅ |
| Sprint 7 Commit7-0 | Design Freeze("Operation Readiness Sprint") | ✅ |

> **⚠️ 번호 체계 참고(문서 간 모순 검토로 발견, Sprint 4 Commit 1에서 표기만 정정)**: "Sprint 2"라는 이름이 위 표에서 **두 개의 서로 다른 트랙**을 가리킨다 — ① 기존 "Sprint 2 (Dashboard v3)"와 ② 이번 세션에서 진행한 "Single Admin Portal Sprint 2(Single Admin Portal Integration)". 두 트랙은 별개 작업이며 시점도 다르다. 과거 완료 이력을 소급 변경하지 않기 위해 기존 행은 그대로 두고 신규 행에 "Single Admin Portal" 접두어를 붙여 구분했다. 향후 Sprint 번호를 새로 붙일 때는 이 충돌을 참고해 트랙명을 함께 표기할 것을 권장한다.

---

## Sprint 0 — Architecture Freeze: ✅ 완료

- 목표: 신규 기능 개발 중단, SSOT 문서(CLAUDE.md/ARCHITECTURE.md/ROADMAP.md/DECISIONS.md/PROJECT_STATUS.md) 확립
- Architecture Freeze는 설계·구조·표준 문서 확정을 의미하며, 미해결 버그(STEP1.5 DateFix 등)와 무관하게 완료된다(DECISIONS.md ADR-010).
- Architecture Freeze 완료와 Pilot Ready(운영 파일럿 투입 가능 여부)는 별개로 관리한다. Pilot Ready는 아래 "Sprint J 이전 필수 해결 과제"가 모두 해소되어야 재평가한다 (PROJECT_STATUS.md 참조).

---

## 구조 Freeze 및 최우선 작업 순서 (2026-07-04 확정)

Pilot용 프로젝트 구조는 **v0.9.0 현재 상태로 Freeze**한다. 구조 변경(§ `docs/STRUCTURE_REORG_ANALYSIS_new.md` 참조)은 착수하지 않으며, `docs/STRUCTURE_REORG_ANALYSIS_new.md`를 구조 관련 기준 문서(baseline)로 삼는다(DECISIONS.md ADR-011). 구조 변경이 필요한 작업은 전부 **Pilot 종료 후 v1.0 작업으로 이관**한다.

Pilot 전 최우선 작업은 다음 순서로 진행했다(**Sprint 4 Commit 1 기준 3단계 모두 완료 확인** — 아래는 완료 이력이며, 이 섹션이 서술하는 "대기 중" 상태는 더 이상 현재 상태가 아니다).

```
1) STEP1.5 DateFix   ✅ 완료 (코드 2026-07-04 / 실배포 2026-07-12, GAS Version 5)
      ↓
2) 전체 QA           ✅ 완료 (Sprint A/B/D/E/I 재실행, 150건+13/2/1/0, 회귀 없음)
      ↓
3) v0.9.0 → v1.0.0-pilot Pilot Release   ✅ 완료 (2026-07-12, 태그 생성·push 완료 — PROJECT_STATUS.md §1 참조)
```

STEP1.5 DateFix 실배포는 Google 계정 인증이 필요한 수동 작업이라 에이전트가 대신 수행할 수 없었으나, 2026-07-12에 사용자가 직접 수행 완료했다 — 상세: [STEP1.5.2_DateFix_Complete_new.md](STEP1.5.2_DateFix_Complete_new.md), [PROJECT_STATUS.md](PROJECT_STATUS.md) §2. 이 3단계 완료 이후 DEV-003·DEV-004·Single Admin Portal Sprint 1~3·Sprint 3.5·Sprint 4가 순차 진행됐다(위 "완료된 작업" 표 참조).

---

## Sprint J 이전 필수 해결 과제 (Pilot Ready 전제조건) — ⚠️ "Sprint J" 명칭은 아래 §Sprint 4~7으로 대체됨

> **번호 체계 정정(Sprint 4 Commit 1)**: 이 섹션이 사용하는 "Sprint J"라는 잠정 명칭은 실제로 도래하지 않았고, 그 사이 PM이 Single Admin Portal Sprint 1~3(별도 트랙)과 Sprint 3.5(Architecture Review)를 진행시킨 뒤 "Sprint 4/5/6"으로 신규 기능 개발 재개 로드맵을 공식 확정했다(§"다음 단계" 하단 참조). 이 표는 **이력 보존을 위해 원문을 남기고**, 상태만 최신화한다.

| 과제 | 상태 | 비고 |
|---|---|---|
| **STEP1.5 DateFix 코드 수정** | ✅ **완료** (2026-07-04) | `_actionCreate`/`_rowToObj`(STEP1.5.1) + `_actionUpdate`/`_actionSummary`(STEP1.5.2) 하드닝. STEP1.5.2_DateFix_Complete_new.md |
| **STEP1.5 DateFix 실배포 + 재QA** | ✅ **완료**(2026-07-12, GAS Version 5, 사용자 수행) | PROJECT_STATUS.md §1/§2 |
| 전체 QA (회귀 테스트 스위트 + 시나리오 리허설) | ✅ 완료 (2026-07-04) | Sprint A(30)/B(38)/D(36)/E(31) + Sprint I 품질게이트(13/2/1/0) + DateFix Node 테스트(15) = 150건 FAIL 0 |
| DEV-003 구현 | ✅ **완료**(2026-07-12) | `admin_reservations_v2_new.html` 신규 작성 완료, 테스트 60/60 PASS, Live 검증 완료. PROJECT_STATUS.md §2-1 |
| 더미 데이터/계정 정리 | 🔲 여전히 대기 | `data/reservations.json` QA 더미, `data/users.json` 더미 3계정 — Sprint7 Commit7-2(Operation Readiness Checklist §10-4)에서 최종 확인 예정 |
| 프로젝트 구조 재편 | 🚫 **여전히 착수하지 않음** | v1.0 작업으로 이관(DECISIONS.md ADR-011), 기준 문서: `docs/STRUCTURE_REORG_ANALYSIS_new.md`. Sprint 4~7 기간에도 이 원칙 유지 |

위 6개 과제 중 4개는 완료됐다(STEP1.5 코드·배포, 전체 QA, DEV-003). **남은 2개(더미 데이터/계정 정리, 프로젝트 구조 재편)는 Sprint4~6이 전부 완료된 Sprint7 시점에도 여전히 미해소 상태다**(Sprint7 Commit7-1 재확인, 2026-07-29) — Sprint 4가 PM 승인 하에 착수됐을 때부터 "이 표가 모두 해소되기 전에는 신규 기능 개발을 시작하지 않는다"는 원래 원칙은 사실상 완화되어 적용됐다. 더미 데이터/계정 정리는 Sprint7 Operation Readiness Checklist(P0)에서 다루고, 프로젝트 구조 재편은 계속 v1.0 이관 대상으로 유지한다.

---

## 다음 단계 — 이력 (Sprint 0 이후, Sprint 4 이전에 완료된 항목)

### IMMEDIATE — ✅ 전부 완료(이력 보존)

1. **STEP1.5 DateFix 실배포** — ✅ 완료(2026-07-12, GAS Version 5)
2. **전체 QA** — ✅ 완료 (Sprint A/B/D/E/I 재실행 + DateFix 회귀 테스트, 150건 FAIL 0)
3. **v0.9.0 → v1.0.0-pilot Pilot Release** — ✅ 완료(2026-07-12, 태그 생성·push 완료)

### IMMEDIATE 이후 — ✅ 완료

4. **DEV-003 구현** — ✅ 완료(2026-07-12, 테스트 60/60 PASS, Live 검증 완료)
5. **더미 데이터/계정 정리** — 🔲 **여전히 미착수**(Sprint 4 착수 시점 기준)

---

## Sprint 4~7 로드맵 (PM 확정, 2026-07-27/28, Sprint7은 2026-07-29 승인)

위 IMMEDIATE 단계 완료 이후, Single Admin Portal Sprint 1~3(별도 트랙)·Sprint 3.5(Architecture Review)를 거쳐 PM이 신규 기능 개발 재개를 아래 Sprint로 공식 확정했다(과거 "Sprint J"라는 잠정 명칭을 대체). **Sprint7 Commit7-1(2026-07-29)에서 실제 실행 결과 기준으로 전면 갱신** — Sprint 5/6은 최초 계획(Patient Portal Integration / Pilot Ready)과 실제 실행 내용이 달랐다. 계획 변경 과정은 이력 보존을 위해 원문을 접어 남기고, 실제 실행 내용을 본문으로 삼는다.

### Sprint 4 — Reservation Core Integration: ✅ 완료

예약(Reservation) 도메인을 Google Sheets SSOT(ADR-013) 기준으로 통합했다. Commit별 상세는 `Sprint4_Implementation_Plan_v1.0.md`(원안) 참조.

| Commit | 내용 | 상태 |
|---|---|---|
| 0 | 문서 Baseline(ADR-012, Reservation Core Architecture 등) | ✅ 완료 |
| 1 | SSOT 문서 정렬 | ✅ 완료 |
| 2 | 예약 승인(Approval, Reservation Approval Foundation) | ✅ 완료 |
| 3 | Slot(정원 관리, Reservation Slot Integration) | ✅ 완료 |
| 3A | Slot Integration Hardening(상태검증 강화/중복점유 방지/Rollback Audit 명확화) | ✅ 완료 |
| 5-1 | Validation Context + Program Mapping Helper(`validate_slot()` Policy Layer 준비) | ✅ 완료 |
| 5-2(A 포함) | Approval Pipeline Policy Integration — validate_slot()을 승인 Pipeline에 연결, Policy Layer/Execution Layer 분리 | ✅ 완료 |

> **원안 대비 변경**: 원래 계획된 "Commit 4(문진)"와 "Commit 6(통합 QA)"는 착수하지 않았고, "Commit 5(Legacy Admin 흡수)"는 실제로는 Commit 5-1/5-2(Validation Context/Policy Pipeline Integration)로 재편되어 실행됐다 — Legacy Admin 흡수(승인 우회 차단) 자체는 이 Sprint가 아니라 **Sprint 6 Commit6-1**에서 실행됐다. 문진(Questionnaire) 통합은 여전히 미착수이며 향후 별도 Sprint 배정 필요.

### Sprint 5 — Portal Integration: ✅ 완료

<details>
<summary>원안(계획 시점, 실제와 다름 — 이력 보존)</summary>

수검자(Patient) 측 Portal 통합. `Platform_Integration_Architecture_Review_v1.0.md` §6(권장 Portal 구조)에서 식별된 신규 페이지(Home/검진안내/검진프로그램/예약조회/My Page)와 AI 채팅 위젯 실제 임베드를 포함할 것으로 예상되나, 착수 시점에 별도 Implementation Plan으로 범위를 확정한다. 실인증/실발송 연동, 관리자 인증(로그인) 구현이 후보였다.

</details>

**실제 실행**: Sprint4 Commit5-2에서 신설된 Backend Policy(`RESERVATION_POLICY_BLOCKED` 등)를 Admin Portal이 올바르게 표시하도록 하는 **Portal Error Contract 통합**으로 범위가 확정됐다(수검자 Portal이 아니라 Admin Portal 대상). 상세: `Sprint5_Portal_Integration_Implementation_Plan_v1.0.md`.

| Commit | 내용 | 상태 |
|---|---|---|
| 5-3.1 | Portal Error Contract Parser(`parseApiError()`) 정의(연결 없음) | ✅ 완료 |
| 5-3.2 | Admin Portal UX Integration — Parser 연결, `_SLOT_CONFLICT_CODES`에 `RESERVATION_POLICY_BLOCKED` 추가(P0), Timeout(AbortController) 추가 | ✅ 완료 |
| 5-3.3 | Legacy Migration Preparation(설계 문서, 4단계 Stage 정의) | ✅ 완료 |

### Sprint 6 — Legacy Guard·Technical Debt Cleanup: ✅ 완료

<details>
<summary>원안(계획 시점, 실제와 다름 — 이력 보존)</summary>

Sprint 4~5로 통합된 플랫폼 기준의 파일럿 재검증("Pilot Ready"). HTTPS 적용, 실키 실호출 스모크 테스트, 더미 데이터/계정 정리, 파일럿 운영 체크리스트/Stop Criteria, Go-Live 기준 충족 확인이 후보였다.

</details>

**실제 실행**: Sprint5 Design Freeze에서 발견한 사실(`reservation_approval_states.py`가 검진완료/일정변경/예약취소는 Legacy Portal이 전담하도록 원래부터 설계)에 따라, Legacy 승인 우회의 **핵심 위험("예약확정" 전이)만** 정밀하게 차단하는 것으로 범위가 확정됐다. "Pilot Ready" 원안의 HTTPS/실키 스모크테스트/더미정리 등은 Sprint7로 이월됐다.

| Commit | 내용 | 상태 |
|---|---|---|
| 6-1 | Legacy Reservation Approval Transition Guard — "예약확정" 전이만 차단, 그 외 4개 전이는 무영향 | ✅ 완료 |
| 6-2 | Technical Debt Cleanup — TD-S5-01(`_extractDetailMessage()` 삭제)/TD-S5-02(Legacy 통계 카드 데이터 소스 교체) | ✅ 완료 |
| 6-3 | Regression·Documentation·Sprint6 Closeout | ✅ 완료 |

### Sprint 7 — "Operation Readiness Sprint": 🔄 진행 중

신규 기능 개발이 아니라 **실제 천안의료원 운영환경 적용 가능 수준의 운영 준비 완료**가 목표. 상세: `Sprint7_Design_Freeze_v1.0.md`.

| Commit | 내용 | 우선순위 | 상태 |
|---|---|---|---|
| 7-0 | Design Freeze Documentation | — | ✅ 완료 |
| 7-1 | SSOT Documentation Synchronization(본 갱신 포함) | P0 | 🔄 진행 중 |
| 7-2 | Operation Readiness Assessment & Checklist | P0 | 🔲 대기 |
| 7-3 | Legacy Stage3 Phase B Design(설계만, 구현 아님) | P0 | 🔲 대기 |
| 7-4 | Admin Operations Manual + Incident Response Manual | P1 | 🔲 대기 |
| 7-5 | Backup/Restore · Release Checklist · Rollback Guide | P1 | 🔲 대기 |
| 7-6 | Pilot Operations Plan(KPI/절차/피드백 체계) | P1 | 🔲 대기 |
| 7-7 | Technical Debt Cleanup Round 2(TD-S5-03/05) | P2 | 🔲 대기 |

### 시점 미정(Sprint 4~7 어디에도 아직 배정되지 않음)

- **LLM 기반 의도 분류 전환 검토** — 현재 규칙 기반이 기본, Claude API는 옵트인. 전환 여부는 별도 ADR로 결정 필요.
- **프로젝트 구조 재편** — `docs/STRUCTURE_REORG_ANALYSIS_new.md` 기준, v1.0 단계에서 착수 여부 재검토(DECISIONS.md ADR-011). Sprint 4~7 기간에도 착수하지 않는다.
- **SQLite 마이그레이션 검토** — `docs/SQLite_Migration_Plan.md` 기반, JSON 대비 성능/동시성 비교 후 착수 여부 결정.

---

## 보류/미착수 (우선순위 미정)

- 이중 백엔드(Sheets ↔ 로컬 JSON) 통합 여부 결정 — ✅ **Reservation Entity에 한해 해소**(ADR-013, Sheets를 SSOT로 확정). 나머지 Entity는 애초에 해당 없음.
- git 버전관리 도입 여부 — ✅ **해소**(ADR-012, Git 커밋 기반 운영으로 확정. ADR-008은 Superseded)
- 프로젝트 구조 재편 (v1.0 이관, DECISIONS.md ADR-011) — 여전히 보류
