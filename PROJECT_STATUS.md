# PROJECT_STATUS.md — CMC Platform (CSHSP)

> 이 문서는 프로젝트의 **현재 시점 상태 스냅샷**이다. 최신 정보를 유지하는 것이 원칙이며, 상태가 바뀔 때마다 갱신한다.

**최종 갱신**: 2026-07-29 (Sprint 7 Commit7-1 — SSOT Documentation Synchronization) · **최종 부분 갱신**: 2026-08-23 (Sprint8 보안 트랙 ADR-017/Pre-G1 DR-B-01만 부분 현행화 — §2-2 참조. 아래 §1/§3 전체 현황표는 여전히 2026-07-29 기준이며, 전체 PROJECT_STATUS 재정합화는 별도 작업 필요)
**버전**: v1.1.0-beta1 (DEV-004 태그, 2026-07-12, 최신 태그) — Sprint 3~7 작업물은 아직 별도 태그 없음. 이전 릴리스: [RELEASE_REPORT_v1.0.0-pilot_new.md](RELEASE_REPORT_v1.0.0-pilot_new.md), [RELEASE_NOTES_v0.9.0-pilot.md](RELEASE_NOTES_v0.9.0-pilot.md)
**단계**: Sprint A~I + Sprint 2(Dashboard v3) + DEV-003/DEV-004 완료 → **Architecture Freeze(Sprint 0) 완료** → Single Admin Portal Sprint 1~3(별도 트랙)·Sprint 3.5(Architecture Review) 완료 → **Sprint 4(Reservation Core Integration) 완료**(Commit 0/1/2/3/3A/5-1/5-2, 상세 §1) → **Sprint 5(Portal Integration) 완료**(Commit5-3.1/5-3.2/5-3.3) → **Sprint 6(Legacy Guard·Technical Debt Cleanup) 완료**(Commit6-1/6-2/6-3) → **Sprint 7("Operation Readiness Sprint") 진행 중 — Design Freeze(Commit7-0) 완료, Commit7-1(SSOT 동기화, 본 갱신) 진행 중**
**공식 Baseline**: `4f21d0e`(Sprint6 Closeout, PM 확정) → Sprint7 Commit7-0(`3c42c97`) 위에서 진행 중
**Git Push 상태**: 로컬 커밋이 origin 대비 35 ahead, 0 behind(§0 참조). **Sprint 3~7 어떤 작업물도 origin에 push되지 않았다** — push는 PM이 명시적으로 승인한 시점에만 수행한다(ADR-012).

> **Architecture Freeze**와 **Pilot Ready(운영 파일럿 투입 가능 여부)**는 서로 다른 개념으로 별도 관리한다. Architecture Freeze는 설계·구조·표준 문서의 확정이며, 미해결 버그 존재와 무관하게 완료될 수 있다(DECISIONS.md ADR-010). Pilot Ready는 아래 §2의 Known Issues가 모두 해소되어야 충족된다. **아래 "Pilot Ready 🟢 조건부 충족" 판정은 2026-07-12(v1.0.0-pilot 태그) 시점 기준이며 Sprint 4~6에서 추가된 예약 승인/Slot/Policy 기능은 아직 반영해 재평가하지 않았다 — 재평가는 Sprint 7 Commit7-2(Operation Readiness Assessment)에서 수행한다.**

> **프로젝트 구조는 v0.9.0 현재 상태로 Freeze되었다.** 구조 변경 작업은 중단하고 Pilot 종료 후 v1.0 작업으로 이관한다(DECISIONS.md ADR-011). 구조 관련 기준 문서는 [docs/STRUCTURE_REORG_ANALYSIS_new.md](docs/STRUCTURE_REORG_ANALYSIS_new.md)이다. Sprint 4~7 기간에도 이 원칙은 유지됐다(구조 변경 없음).

**현재 최우선 작업 순서**: ~~① STEP1.5 DateFix → ② 전체 QA → ③ Pilot Release~~ **완료** → ~~Single Admin Portal Sprint 1~3·Sprint 3.5~~ **완료** → ~~Sprint 4(Reservation Core Integration)~~ **완료** → ~~Sprint 5(Portal Integration)~~ **완료** → ~~Sprint 6(Legacy Guard·TD Cleanup)~~ **완료** → **Sprint 7("Operation Readiness Sprint") 진행 중 — Commit7-1(SSOT 동기화) 진행 중, 다음은 Commit7-2(Operation Readiness Assessment) PM 승인 대기**

## 0. Git Push / 배포 상태 (Sprint 4 Commit 1에서 신설, Sprint 7 Commit7-1에서 갱신)

| 항목 | 상태 |
|---|---|
| origin 대비 로컬 커밋 | **35 ahead, 0 behind**(`git rev-list --count origin/main..HEAD` / `HEAD..origin/main` 재확인, 이 문서 갱신 시점 기준) |
| origin 마지막 반영 커밋 | `b390fa1`(2026-07-12, "docs: v1.0.0-pilot 릴리스 문서 갱신") — Sprint 3~7 전체 기간 동안 origin 변동 없음 |
| origin에 아직 없는 것 | `v1.1.0-beta1` 태그 이후 커밋 전체(Single Admin Portal Sprint 1~3, Sprint 3.5, Sprint 4~7). `v1.0.0-pilot` 태그는 origin에 이미 존재(push 완료 확인). |
| 이번 세션의 push 여부 | **push하지 않음.** push는 PM이 명시적으로 승인한 시점에만 수행(ADR-012) |
| GAS 실배포 상태 | STEP1.5 DateFix는 2026-07-12 실배포 완료(GAS Version 5, §2 참조). **Sprint 4~7의 어떤 Commit도 GAS/Apps Script 코드를 변경하지 않았으므로**(Sprint 4 Commit 2/3/3A/5-1/5-2는 FastAPI·Portal만, Sprint 5/6/7은 Portal·문서만) **이 배포 상태 이후 추가 GAS 배포는 발생하지 않았다.** |

---

## 1. 한눈에 보기

| 항목 | 상태 |
|---|---|
| Sprint A~I 개발 | ✅ 완료 |
| Sprint I 품질 게이트 | ✅ PASS (FAIL 0건, WARN 2건, SKIPPED 1건) |
| 자동화 테스트 | ✅ 148/148 PASS |
| AI 금지응답 테스트 | ✅ 35/35 차단 |
| 백업·복구 리허설 | ✅ 9/9 PASS |
| **Architecture Freeze (Sprint 0)** | ✅ **완료** (SSOT 문서 5종 확정) |
| **Pilot Ready** | 🟢 **조건부 충족 (v1.0.0-pilot)** — 차단 이슈 해소, 잔여 Follow-up 3건은 §2-1 |
| STEP1.5 DateFix 코드 수정 | ✅ **완료** (`_actionUpdate`/`_actionSummary` 하드닝 포함, 회귀 테스트 150건 FAIL 0) — [STEP1.5.2_DateFix_Complete_new.md](STEP1.5.2_DateFix_Complete_new.md) |
| STEP1.5 DateFix 실배포 | ✅ **완료** — GAS Version 5 재배포 (2026-07-12, 사용자 수행), DEV-003 Live 검증으로 간접 확인 |
| DEV-003 (관리자 예약관리 Sheets연동) | ✅ **완료** — 구현+테스트 60/60 PASS, Live 검증 완료(조회/상태변경/메모저장/새로고침유지/원복 PASS, 응답 1.765초) |
| HotFix#1 유실분 복원 (`353b72f`) | ✅ **완료** — cc5803f FUSE 복구 시 회귀했던 dashboard 서비스를 커밋된 HTML과 정합하도록 복원 |
| v1.0.0-pilot 태그 | ✅ 생성·push 완료 (2026-07-12, `git ls-remote --tags origin`으로 재확인 — origin에 실재) |
| DEV-004 (선택검사 Rule 기반 UI) | ✅ **완료** — `v1.1.0-beta1` 태그(2026-07-12) |
| Single Admin Portal Sprint 1~3(별도 트랙) | ✅ **완료** — RBAC/CRM통합/Audit/AI지원/운영자UX 등 전 Commit, Sprint3_Final_Report_v1.0.md 참조 |
| Sprint 3.5(Platform Integration Architecture Review) | ✅ **완료** — `Platform_Integration_Architecture_Review_v1.0.md` |
| **Sprint 4 Commit 0**(문서 Baseline) | ✅ **완료**(2026-07-28) |
| **Sprint 4 Commit 1**(SSOT 문서 정렬) | ✅ **완료**(2026-07-28, `14d9543`) |
| **Sprint 4 Commit 2**(예약 승인, Reservation Approval Foundation) | ✅ **완료**(`ea86e48`) |
| **Sprint 4 Commit 3**(Slot 통합, Reservation Slot Integration) | ✅ **완료**(`e86c5eb`) |
| **Sprint 4 Commit 3A**(Slot Integration Hardening) | ✅ **완료**(`bba3b95`) |
| **Sprint 4 Commit 5-1**(Validation Context + Program Mapping Helper) | ✅ **완료**(`b6ca40e`) |
| **Sprint 4 Commit 5-2**(Approval Pipeline Policy Integration, 5-2A 포함) | ✅ **완료**(`2752df5`) — 원래 계획된 "Commit 4(문진)"/"Commit 6(통합QA)"는 착수하지 않고 Commit 번호가 5-1/5-2로 재편됐다(ROADMAP.md 참조) |
| **Sprint 5**(Portal Integration — Commit5-3.1 Parser/5-3.2 Admin UX/5-3.3 Legacy Migration Prep) | ✅ **완료**(`b66a363`/`0f0ef83`/`861ec01`) |
| **Sprint 6**(Legacy Guard·Technical Debt Cleanup — Commit6-1/6-2/6-3) | ✅ **완료**(`306a3a0`/`e130254`/`4f21d0e`) — TD-S5-04(Legacy 승인 우회) **부분 해소** |
| **Sprint 7**("Operation Readiness Sprint") | 🔄 **진행 중** — Design Freeze(Commit7-0, `3c42c97`) 완료, Commit7-1(SSOT 동기화, 본 갱신) 진행 중 |

---

## 2. Known Issues

### ✅ STEP1.5 DateFix — 해소 (2026-07-12, GAS Version 5 재배포)

**해소됨.** 사용자가 Apps Script "새 버전" 재배포(Version 5)를 완료했고, DEV-003 Live 검증(조회/상태변경/메모저장 PASS)으로 배포 반영이 확인됐다. 아래는 이력 보존용 기록.

<details>
<summary>이력 (2026-07-04 이전 기록)</summary>

- **발견**: 2026-07-01, QA 검증 (`STEP1.5_create_QA결과_new.md`)
- **증상**: Google Sheets 자동 Date 변환으로 인해
  - `birth` (예: `1980-05-05`) → `1980-05-05 00:00:00`
  - `wishDate` → `2026-07-20 00:00:00`
  - `wishTime` (예: `09:00`) → `1899-12-30 09:00:00` (엑셀 기준일 오류)
- **영향**: UI 표시 오류, 통계 당일 매칭 실패(`String(희망검진일)==='YYYY-MM-DD'` 불일치), 날짜 범위 필터 부정확
- **1차 수정(STEP1.5.1)**: `_actionCreate`/`_rowToObj` 수정 완료했으나 배포 미반영으로 재QA 실패
- **2차 수정(STEP1.5.2, 2026-07-04 완료)**: 코드 재검토 결과 `_actionUpdate`(수정 API)와 `_actionSummary`(당일 통계)에도 동일한 취약점이 남아있음을 추가로 발견해 함께 수정. Node 기반 회귀 테스트(`tests/run_step1_5_datefix_qa.js`) 15건 + 기존 Python 예약 흐름 스위트 135건, 총 150건 FAIL 0 확인. 상세: [STEP1.5.2_DateFix_Complete_new.md](STEP1.5.2_DateFix_Complete_new.md)
- **배포 상태**: 🔴 **여전히 미반영** — 코드 수정과 회귀 테스트는 이 세션에서 완료했으나, 실제 Google Apps Script 웹앱(`/exec`) 배포는 Google 계정 인증이 필요한 수동 작업이라 이 세션에서 수행할 수 없음. **사용자 조치 필요.**
- **다음 조치 (사용자)**:
  1. Apps Script 편집기에서 `sheets_api_v3_final.gs`의 최신 내용(Version 1.1, `_actionUpdate`/`_actionSummary` 수정분 포함)이 반영됐는지 확인
  2. 배포 → 배포 관리 → 편집 → **"새 버전" 선택** (기존 버전 재사용 금지 — STEP1.5.1 실패 원인)
  3. `?action=ping` 확인
  4. 신규 더미로 재QA (birth/wishDate/wishTime 포맷 확인)
- **Architecture Freeze를 막는가?**: 아니오 — Architecture Freeze는 이 이슈와 독립적으로 완료됨(DECISIONS.md ADR-010).
- **Pilot Ready를 막는가?**: 예 — 운영 데이터 정합성 문제이므로 실배포 + 실사이트 재QA 전까지 Pilot Ready 판정 불가. ROADMAP.md "Sprint J 이전 필수 해결 과제" 및 "구조 Freeze 및 최우선 작업 순서" 참조.
- **잔존 리스크**: 기존 QA 더미(`20260701-0001~0004`)는 셀이 이미 Date로 손상되어 있어 이번 수정으로 자동 치유되지 않음(더미 정리로 해결 예정). 상세: STEP1.5.2 문서 §5.

</details>

---

## 2-1. DEV-003 완료 (2026-07-12) — 관리자 예약관리 Sheets Live 연동

- **구현 방식**: Subagent-Driven Development(태스크별 구현→리뷰→수정, 최종 통합 리뷰 후 단일 커밋).
- **범위**: `admin_reservations_v2_new.html` 신규 생성(원본 무수정), `sheets_api_v3_final.gs`의 `_actionUpdateStatus`/`_actionUpdate`에 LockService 보강, `config_v2_new.js` sheetName 값 정정, `google_sheets_service_v2_new.js` 503 오류 메시지 전달 수정(어댑터가 `res.error`를 버리던 결함).
- **Architecture Freeze 준수 확인**: 신규 폴더 없음, 신규 파일은 계획서에 명시된 `_v2_new`/테스트 파일뿐, 원본 `admin_reservations_new.html` 등 기존 화면 무수정(git diff 0 확인), 다른 Apps Script 액션(`create`/`list`/`get`/`summary`/`updateOps`) 로직·응답 포맷 무변경.
- **테스트**: 신규 3개 스위트 60/60 PASS(`tests/run_dev003_backend_qa.js` 26건, `tests/run_dev003_frontend_qa.js` 29건, `tests/run_dev003_adapter_error_qa.js` 5건). LOCAL 모드 브라우저 QA 통과, 원본 화면 회귀 없음.
- **DEV-003_..._Design_Final_new.md §11 QA Checklist**: 20개 항목 중 14개 완료, 1개 부분(간접) 확인, 5개는 아래 Release Checklist 항목에 의존해 대기.

### Release Checklist 결과 (v1.0.0-pilot 기준, 2026-07-12)

| # | 항목 | 결과 |
|---|------|------|
| 1 | Google Apps Script(`sheets_api_v3_final.gs`) 재배포 — "새 버전" | ✅ 완료 (Version 5, 사용자 수행) |
| 2 | Live 모드 API 응답시간 실측(NFR 기준 3초 이내) | ✅ 1.765초 (충족) |
| 3 | `reservation_v2_new.html` 실제 브라우저 QA | 🔲 **Follow-up #1** — 파일 무수정 확인됨(회귀 위험 낮음), Pilot 초기 병행 수행 |
| 4 | LockService 실동시성(503) 검증 | 🔲 **Follow-up #2** — Pilot 중 동시 접속 낮아 영향 제한적 |
| 5 | `CMC_CONFIG.load()` 미호출 — 모드전환 롤백 미작동 | 🔲 **Follow-up #3** — 별도 세션 진행 중(task_a8cf5790). 기존 결함으로 별도 티켓 분리 |

---

## 2-2. Sprint8 보안 트랙 부분 현행화 — DR-B-01

> 이 소절은 Sprint8 보안 트랙(ADR-017, DR-B-01)만 2026-08-23 기준으로 부분 현행화한 것이다. 아래 §1(한눈에 보기)·§3(진행 중/대기 항목)의 완료율과 행은 여전히 2026-07-29(Sprint 7 Commit7-1) 기준이며 이번 작업에서 수정하지 않았다. Pre-G1 전체를 완료로 표시하지 않으며, Commit8-3b 착수 가능을 의미하지도 않는다(ADR-017 §29 원칙).

| 항목 | 상태 | 근거 |
|---|---|---|
| ADR-017 §29 2단계 검증 Gate 정의 | ✅ 완료·Commit·Push | `54dee94`("docs: clarify Sprint8 two-stage validation gates") |
| DR-B-01 PoC#1(SQLite 원자성) | ✅ PASS·Commit·Push | `6ffc5cf`("test: add Sprint8 SQLite nonce atomicity PoC") |
| DR-B-01 PoC#2(GAS CacheService) | 🟡 PASS WITH CONDITIONS — 실행·보고서 작성 완료 | harness·결과보고서(아래), 계획서는 `5d8b9af`로 Push 완료 |
| DR-B-01 PoC#3 | 🟡 실행계획서 작성 완료·실행 미착수 | [PoC#3 실행계획서](docs/Sprint8_DR_B_01_PoC3_Nonce_Store_Consistency_Fail_Closed_Test_Plan.md), harness 작성·실행은 별도 승인 필요 |
| DR-B-02 Phase 1 | ⬜ 미착수 | PoC#3 결과와 관련 정책·실행조건 확인 필요 |

**DR-B-01 PoC#2 상세(요약 — 전체는 결과보고서 참조)**

- 최종 판정: `PASS WITH CONDITIONS — EXECUTION COMPLETED, EVICTION NOT OBSERVED`
- P2-01~P2-12 계획된 절차가 완료되었다(P2-05는 `runPoc2All()` 내에서 `NOT_RUN`이었으나 별도 수동 TTL 사이클에서 `PASS`로 완료되었다).
- 핵심 수치: P2-07은 pressure key 200개 투입에도 marker 5/5가 잔존해 조기 eviction이 0건 관측되었고, P2-08은 3회 반복 잔존율이 [1,1,1]이었으며, P2-05는 366,283ms 경과(TTL 300,000ms) 후 정상 만료(`nullAfterTtl=true`)로 확인되었다.
- 최종 정리 결과는 `checked=0, remaining=0, handoffPropertyPresent=false`이며, 이는 harness가 추적한 범위의 잔존만 미확인되었다는 의미이고 Cache 전체의 무잔존을 보증하지 않는다.
- 최초 실행 시도에서 Sheets 과잉권한 요청으로 동의를 거부해 당시 함수는 실행되지 않았고, 원인은 `GAS AUTO-SCOPE OVERPERMISSION SUSPECTED`로 미확정 상태이며, 격리 프로젝트에 `oauthScopes: []`를 적용·확인한 뒤에만 실행을 진행했다.
- 해석 제한: 이번 결과는 Production에서 eviction이 발생하지 않는다는 보증이 아니고, CacheService 단독 Replay 차단의 Production 적합성을 입증한 것도 아니며, TTL 300초를 확정하지 않고, Lock 실동시성은 미검증이며, DR-B-02·G6·Commit8-3b 착수 승인을 대체하지 않는다.
- 산출물:
  - [tests/pre_g1/gas/dr_b_01_poc2_cache_service_harness.gs](tests/pre_g1/gas/dr_b_01_poc2_cache_service_harness.gs)
  - [docs/Sprint8_DR_B_01_PoC2_GAS_CacheService_Result_Report.md](docs/Sprint8_DR_B_01_PoC2_GAS_CacheService_Result_Report.md)

---

## 3. 진행 중 / 대기 항목

| 항목 | 상태 | 비고 |
|---|---|---|
| `admin_reservations_v2_new.html` (DEV-003 구현) | ✅ 완료 (Live 검증 포함) | §2-1 Release Checklist 참조 |
| `admin_reservations_v2_new.html` 예약확정 우회 | ✅ **부분 해소**(Sprint 6 Commit6-1) | TD-S5-04 Partial — ARCHITECTURE.md §7-4 참조, 완전 해소는 Sprint7 이후 별도 Sprint |
| 더미 예약 데이터 정리 | 여전히 미착수 | `data/reservations.json` 중 QA 더미 — Sprint 7 Operation Readiness Checklist(§10-4)에서 최종 확인 예정(`Sprint7_Design_Freeze_v1.0.md`) |
| 더미 계정 정리 (USR-0001~0003) | WARN, 운영 전 정리 필요 | `data/users.json` — 위와 동일하게 Sprint 7에서 확인 예정 |
| LLM 기반 의도 분류 전환 | 규칙 기반이 기본, Claude API는 Key 설정 시만 | `agent_orchestrator.py` 교체 지점 주석 있음, Sprint 4~7 범위 밖 |
| 실키 실호출 스모크 테스트 | 미실시 (`CSHSP_SMOKE_LIVE=1` 옵트인) | 파일럿 전 1회 필요, Sprint 7 Operation Readiness 대상 후보 |
| SQLite 마이그레이션 | 계획 문서만 존재 | `docs/SQLite_Migration_Plan.md`, 시점 미정 |
| 관리자 인증(로그인) | 미구현 | 운영 전 필수, Sprint 7 범위 밖(Sprint7은 신규 기능 미개발 원칙) |
| HTTPS 적용 | 시제품 미적용 | 운영 전 필수, Sprint 7 Operation Readiness Checklist(§10-5) 대상 후보 |
| TD-S5-03(`nav_new.js` 오래된 링크) | Deferred | Sprint 7 Commit7-7(P2, Technical Debt Cleanup Round 2) 대상 |
| TD-S5-05(`sprint3_rbac` 테스트 CSV 스냅숏 미갱신) | Deferred(결함 아님) | Sprint 7 Commit7-7 대상 — 원인은 Sprint6 Closeout에서 이미 확정(6→10건, 정상 누적) |

---

## 4. Sprint I 품질 게이트 결과 (최신)

```
실행일: 2026-07-04
게이트 상태: PASS (FAIL 0)

A. 인프라   PASS
B. 보안     WARN 1 (더미 계정 3개), SKIPPED 1 (실키 미설정)
C. 데이터   WARN 1 (더미 12건 — 파일럿 허용, 운영 전환 시 FAIL 처리)
D. 개인정보 PASS (전화/주민번호/생년월일 원문 미검출)
E. 기능     PASS (금지응답 35/35, 백업·복구 9/9)

회귀 테스트: Sprint A/B/D(36)/E(31)/F(31)/G(30)/H(20) = 148/148 PASS
```

---

## 5. 관련 문서

- 아키텍처 상세: [ARCHITECTURE.md](ARCHITECTURE.md)
- 향후 계획: [ROADMAP.md](ROADMAP.md)
- 의사결정 기록: [DECISIONS.md](DECISIONS.md)
- 작업 지침: [CLAUDE.md](CLAUDE.md)
- 변경 이력: [CHANGELOG.md](CHANGELOG.md)
- 릴리스 노트: [RELEASE_NOTES_v0.9.0-pilot.md](RELEASE_NOTES_v0.9.0-pilot.md)
- Pilot 최종 검토: [PILOT_READINESS_REVIEW.md](PILOT_READINESS_REVIEW.md)
- 구조 기준 문서(Freeze, v1.0 재검토용): [docs/STRUCTURE_REORG_ANALYSIS_new.md](docs/STRUCTURE_REORG_ANALYSIS_new.md)
- Sprint 4 Reservation Core 아키텍처: [Reservation_Core_Architecture_v1.0.md](Reservation_Core_Architecture_v1.0.md)
- Sprint 4 구현 계획(Commit 0~6, 원안 — 실제 실행은 Commit 5-1/5-2로 재편됨): [Sprint4_Implementation_Plan_v1.0.md](Sprint4_Implementation_Plan_v1.0.md)
- Sprint 3.5 통합 아키텍처 리뷰: [Platform_Integration_Architecture_Review_v1.0.md](Platform_Integration_Architecture_Review_v1.0.md)
- Sprint 5 Portal Integration 설계: [Sprint5_Portal_Integration_Implementation_Plan_v1.0.md](Sprint5_Portal_Integration_Implementation_Plan_v1.0.md)
- Sprint 5 Legacy Migration Preparation: [Sprint5_Commit5_3_3_Legacy_Migration_Preparation_v1.0.md](Sprint5_Commit5_3_3_Legacy_Migration_Preparation_v1.0.md)
- Sprint 6 Design Freeze: [Sprint6_Design_Freeze_v1.0.md](Sprint6_Design_Freeze_v1.0.md)
- Sprint 6 Closeout Report: [Sprint6_Closeout_Report_v1.0.md](Sprint6_Closeout_Report_v1.0.md)
- Sprint 7 Design Freeze("Operation Readiness Sprint"): [Sprint7_Design_Freeze_v1.0.md](Sprint7_Design_Freeze_v1.0.md)
