# Release Readiness Report — v0.9.0 Pilot

**대상**: CMC Platform (CSHSP)
**작성일**: 2026-07-04
**리뷰 범위**: 프로젝트 전체 (코드 수정 없이 검토만 수행)
**리뷰 기준**: Architecture consistency, Folder structure, SSOT documentation, ADR decisions, ROADMAP, PROJECT_STATUS, Apps Script implementation, DateFix completion, Reservation flow, Dashboard, Statistics, Test coverage, Known Issues, Remaining Risks, Deployment readiness

---

## 1. Executive Summary

CMC Platform은 Sprint A~I 및 Sprint 2까지 기능 개발을 완료했고, Architecture Freeze(Sprint 0, DECISIONS.md ADR-010)와 구조 Freeze(v0.9.0 기준, ADR-011)를 확정했다. SSOT 문서 5종(CLAUDE/ARCHITECTURE/ROADMAP/DECISIONS/PROJECT_STATUS)과 릴리스 산출물(README/CHANGELOG/LICENSE/.gitignore/requirements.txt/.env.example/RELEASE_NOTES)이 모두 갖춰져 있고, 코드 레벨 테스트(Python 135건 + Node DateFix 15건 = 150건)와 Sprint I 품질 게이트(PASS 13/WARN 2/SKIPPED 1/FAIL 0)가 전부 통과 상태다.

그러나 **STEP1.5 DateFix는 코드 수정과 회귀 테스트는 완료됐지만 실제 운영 중인 Google Apps Script 웹앱에는 아직 배포되지 않았다.** 이는 예약 데이터(생년월일·희망검진일·희망시간)의 정합성에 직접 영향을 미치는 Critical 등급 이슈이며, 실서버 배포는 Google 계정 인증이 필요한 수동 작업이라 에이전트가 대신 수행할 수 없다. 이 항목 하나가 Pilot Ready 판정의 유일한 실질적 차단 요인이다.

**결론**: 문서·아키텍처·테스트 측면은 모두 Pilot 수준을 충족하나, 예약 데이터 정합성을 보장하는 DateFix가 실제로 반영되지 않은 상태에서 Pilot을 개시하는 것은 리스크가 크다. 아래 §7~§8에서 상세 근거와 함께 판정한다.

---

## 2. Scope Completed (검증된 완료 범위)

### 2-1. Architecture consistency
- 3개 실행 영역(Frontend 정적 HTML/JS, Backend Python/FastAPI, Backend Google Apps Script) 구조가 ARCHITECTURE.md에 기술된 내용과 실제 코드 구조가 일치함을 확인.
- 이중 백엔드(Sheets ↔ 로컬 JSON) 구조는 알려진 설계 특성으로 문서화되어 있으며(ARCHITECTURE.md §7, DECISIONS.md ADR-003), 임의의 불일치가 아니라 의도된 단계적 전환 결과(ADR-001)임을 확인.

### 2-2. Folder structure
- 목표 구조(CSHSP/) 대비 분석이 `docs/STRUCTURE_REORG_ANALYSIS_new.md`에 기록되어 있고, 구조는 v0.9.0 기준으로 Freeze됨(ADR-011). 이번 리뷰에서 구조를 변경하지 않았으며, 현재 루트 구성(SSOT 12개 표준 문서 + app/admin/chat/src/data/docs/tests 7개 폴더)이 해당 문서와 일치함을 재확인.

### 2-3. SSOT documentation
- CLAUDE.md, ARCHITECTURE.md, ROADMAP.md, DECISIONS.md, PROJECT_STATUS.md 5종 모두 존재하며 상호 링크가 일관됨.
- PROJECT_STATUS.md는 2026-07-04 기준 최신 상태(DateFix 코드 완료/실배포 대기)로 갱신되어 있음을 확인.

### 2-4. ADR decisions
- DECISIONS.md에 ADR-001~ADR-011까지 11건 기록. 미결 상태는 ADR-009(배포 후 스모크 체크 정책, 미결)뿐이며 나머지는 모두 "확정" 상태.
- ADR-010(Architecture Freeze와 Pilot Ready 분리), ADR-011(구조 Freeze) 결정이 ROADMAP/PROJECT_STATUS에 일관되게 반영되어 있음을 확인.

### 2-5. ROADMAP / PROJECT_STATUS
- ROADMAP.md의 "구조 Freeze 및 최우선 작업 순서"(① DateFix → ② 전체 QA → ③ Pilot Release)가 PROJECT_STATUS.md의 최우선 작업 순서 문구와 일치.
- "Sprint J 이전 필수 해결 과제" 표에 DateFix 코드 수정(완료)과 실배포(미해결)가 별도 행으로 분리되어 정확히 추적되고 있음.

### 2-6. Apps Script implementation
- `app/apps_script/sheets_api_v3_final.gs`(Version 1.1) 검토 결과, `_actionCreate`/`_rowToObj`(STEP1.5.1) + `_actionUpdate`/`_actionSummary`(STEP1.5.2) 4곳 모두에 DateFix가 일관되게 적용되어 있음을 코드 레벨에서 확인. `doGet`/`doPost` 라우팅, `_generateNo`(예약번호 채번), `LockService` 동시성 보호 로직은 변경 없이 원형 유지.

### 2-7. DateFix completion (코드 레벨)
- 근본 원인(Google Sheets 자동 Date 변환) 및 잔존 취약점(_actionUpdate, _actionSummary 미보호)이 STEP1.5.2_DateFix_Complete_new.md에 상세 기록.
- 코드 수정은 **완료**, 회귀 테스트로 검증 완료. 단 **실배포는 미완료** — 상세는 §3, §5.

### 2-8. Reservation flow
- Python 기반 예약 엔진(Sprint B): 상태머신(PENDING_APPROVAL→CONFIRMED/REJECTED→COMPLETED/CANCELLED), Slot 검증, 감사로그, RBAC(AI 계정 승인 차단) 등 38개 시나리오 전부 PASS.
- API 계층(Sprint D): 36개 엔드포인트, 동시 신청 처리(스레드 8), 예약번호 채번 충돌 없음(Lock) 검증 포함 전부 PASS.
- Google Sheets 경로(Apps Script): create/update/summary 로직이 Node 모의 테스트로 검증 완료(15/15 PASS), 단 실사이트 미배포.

### 2-9. Dashboard
- `admin_dashboard_v3_new.html` + `dashboard_service_v2_new.js`(Sprint 2): KPI 6종, 검사실 현황 8종, AI 추천 기능이 ROADMAP/ARCHITECTURE 문서에 완료로 기록되어 있고 Sprint 2 항목이 "완료된 작업" 표에 반영됨. 이번 리뷰에서 코드 변경 없이 문서-코드 일치 여부만 확인(직접 UI 구동 테스트는 범위 밖).

### 2-10. Statistics
- `data/statistics.json`(KPI 정의), `src/dashboard/ai_metrics.py`(AI 상담 통계) 존재 확인. `_actionSummary`의 당일 통계 집계 로직은 이번 STEP1.5.2에서 `_rowToObj` 정규화를 거치도록 강화되어 Date 타입 셀로 인한 "당일 통계 0건" 버그가 코드 레벨에서 해소됨(§2-7 참조, 배포 후 유효).

### 2-11. Test coverage
- 상세는 §4 Test Summary 참조. Sprint A/B/D/E/I + DateFix 전용 테스트 = 150건 코드 레벨 검증 + 품질 게이트 16항목, 전부 FAIL 0.

---

## 3. Outstanding Issues (미해결 이슈)

| # | 이슈 | 등급 | 상태 | 근거 |
|---|---|---|---|---|
| 1 | **STEP1.5 DateFix 실배포 미완료** | 🔴 Critical | 코드/테스트 완료, 배포만 미완료 | PROJECT_STATUS.md §2, STEP1.5.2_DateFix_Complete_new.md §5 |
| 2 | DEV-003(관리자 예약관리 Sheets연동) 미구현 | 🟡 Medium | 설계만 확정(Final), 코드 미작성 | DECISIONS.md ADR-007 |
| 3 | 더미 데이터/계정 미정리 | 🟡 Medium | QA 더미 12건, 더미 계정 3개(USR-0001~0003) | PROJECT_STATUS.md §3, Sprint I 품질게이트 WARN 2건 |
| 4 | 실인증 미구현 | 🟡 Medium | Mock 인증(X-User-Id)으로 대체 운영 중 | PILOT_READINESS_REVIEW.md §3 |
| 5 | 실발송 미구현 | 🟡 Medium | 알림톡/SMS는 Mock 발송(PENDING 큐)까지만 동작 | PILOT_READINESS_REVIEW.md §3 |
| 6 | 관리자 인증(로그인) 미구현 | 🟡 Medium | 운영(Go-Live) 전 필수, Pilot 단계는 내부망 한정으로 완화 | PROJECT_STATUS.md §3 |
| 7 | HTTPS 미적용 | 🟡 Medium | 시제품 단계 미적용 | PROJECT_STATUS.md §3 |
| 8 | 기존 QA 더미 3건(20260701-0001~0004)의 셀 손상 | 🟢 Low | DateFix 배포와 무관하게 자동 치유되지 않음, 더미 정리로 해결 가능 | STEP1.5.2_DateFix_Complete_new.md §5-2 |
| 9 | ADR-009 미결(배포 후 스모크 체크 정책) | 🟢 Low | 정책 문서화만 남음, 기능적 영향 없음 | DECISIONS.md |

**Critical 등급은 #1 하나뿐이며, 이것이 Pilot Ready 판정의 유일한 실질적 차단 요인이다.**

---

## 4. Test Summary (테스트 요약)

| 스위트 | 결과 | 비고 |
|---|---|---|
| Sprint A (Core Data Layer) | 30/30 PASS | 20 Entity 로더/검증 |
| Sprint B (Reservation Engine) | 38/38 PASS | 상태머신·Slot·감사로그·RBAC |
| Sprint D (API Layer) | 36/36 PASS | 36 엔드포인트, 동시성(스레드 8) 포함 |
| Sprint E (AI 에이전트) | 31/31 PASS | reservation_agent 포함 5종 에이전트 |
| Sprint I (품질 게이트, 16항목) | PASS 13 / WARN 2 / SKIPPED 1 / FAIL 0 | 게이트 통과 판정 (WARN: 더미 계정·더미 데이터, SKIPPED: 실키 미설정) |
| STEP1.5 DateFix 전용 (Node, `run_step1_5_datefix_qa.js`) | 15/15 PASS | 실제 `.gs` 원본을 vm 샌드박스에 로드해 검증. 수정 되돌리면 실제로 실패함을 확인(테스트 유효성 검증 완료) |
| **합계** | **150건 코드 레벨 테스트 FAIL 0** + 품질 게이트 PASS | Sprint C/F/G/H는 이번 리뷰에서 재실행하지 않음(직전 세션에서 148/148 PASS 확인된 이력 존재, PROJECT_STATUS.md §4) |

**미실행 항목**: 실키(ANTHROPIC_API_KEY) 스모크 테스트(SKIPPED, 옵트인 필요), 실사이트 Apps Script 재QA(배포 후에만 가능).

---

## 5. Deployment Prerequisites (배포 전제조건)

| # | 항목 | 상태 |
|---|---|---|
| 1 | STEP1.5 DateFix 코드 수정 | ✅ 완료 |
| 2 | STEP1.5 DateFix 회귀 테스트 | ✅ 완료 (150건 FAIL 0) |
| 3 | **STEP1.5 DateFix 실배포** (Apps Script "새 버전" 배포) | 🔴 **미완료 — 사용자 조치 필수** |
| 4 | 배포 후 `?action=ping` 확인 | ⏳ 대기 (3번 이후) |
| 5 | 배포 후 신규 더미로 재QA (birth/wishDate/wishTime 포맷) | ⏳ 대기 (3번 이후) |
| 6 | `app/config_v2_new.js`의 `appsScript.webAppUrl` 설정 확인 | 미검증 (실 배포 URL 값은 이 리뷰 범위 밖) |
| 7 | 환경변수(.env) 설정 — `CSHSP_DATA_DIR` 등 | README.md §4 절차 존재, 실제 운영 서버 값 설정은 배포 시점에 수행 필요 |
| 8 | Production Checklist(`src/deploy/production_checklist.md`) A~F 24개 항목 | 전 항목 미체크 — PILOT_READINESS_REVIEW.md §5에서 이미 "Known Issues 해소 후 착수 권장"으로 명시됨 |

**§5-3(실배포)이 완료되고 §5-4·5-5(ping 확인, 재QA)가 통과해야 나머지 배포 절차를 진행할 수 있다.**

---

## 6. Operational Risks (운영 리스크)

| 리스크 | 영향 | 완화 방안 |
|---|---|---|
| DateFix 미배포 상태로 실제 예약이 발생하면 생년월일/희망일자/희망시간이 다시 왜곡되어 저장됨 | 데이터 정합성 손상, 당일 통계 오류 재발 | 배포 전 실사용 금지, 배포 후 재QA 필수 (§5) |
| 관리자 콘솔(로컬 JSON 경로)과 환자 예약 화면(Sheets 경로)이 자동 동기화되지 않음(이중 백엔드) | 관리자가 보는 데이터와 실제 시트 데이터가 어긋날 수 있음 | ARCHITECTURE.md §7에 기 문서화, DEV-003 구현 시 통합 검토 필요 |
| Mock 인증/Mock 발송 상태로 Pilot 진행 시 실제 신원확인·알림 보장 없음 | 오배정, 안내 누락 가능성 | PILOT_READINESS_REVIEW.md §4의 조건부 운영 지침(육안 재확인, 수동 대체 발송) 준수 필요 |
| 기존 QA 더미(0001~0004)가 손상된 채로 시트에 남아있음 | 실제 운영 데이터와 혼재되어 혼선 유발 가능 | Pilot 개시 전 더미 삭제 권장(사용자 승인 필요, 자동 삭제하지 않음) |
| Google 계정 인증이 필요한 배포 작업을 에이전트가 대신 수행할 수 없음 | 배포 지연 시 전체 일정 지연 | 사용자가 §5-3 절차를 직접 수행해야 함 |
| git 미사용으로 인한 변경 이력 추적 한계(ADR-008) | 롤백/원인 추적이 파일명 접미사에 의존 | 이번 STEP1.5.2 수정은 기존 "최종 배포본" 파일을 직접 수정(전례 있음), 별도 버전 파일 없이 진행되었으므로 문제 발생 시 STEP1.5.2 문서의 diff 설명을 참조해 수동 롤백 가능 |

---

## 7. Go / No-Go Assessment

| 판정 축 | 상태 | 근거 |
|---|---|---|
| Architecture | 🟢 PASS | §2-1~2-6, Freeze 완료(ADR-010), 구조 일관성 확인 |
| Documentation (SSOT) | 🟢 PASS | §2-3~2-5, 5종 문서 최신·일관 |
| Code-level correctness (DateFix 포함) | 🟢 PASS | §2-6~2-7, §4, 150건 FAIL 0 |
| **Production deployment (실배포)** | 🔴 **FAIL** | §3-#1, §5-#3, Apps Script 미배포 |
| 부가 운영 요건(실인증/실발송/관리자인증/HTTPS) | 🟡 조건부 | §3-#4~#7, Pilot 규모에서는 조건부 운영으로 완화 가능(PILOT_READINESS_REVIEW.md §4) |

**종합 판단**: 문서·아키텍처·코드·테스트는 Pilot 수준의 기준을 모두 충족한다. 그러나 예약 데이터 정합성을 보장하는 STEP1.5 DateFix가 **실제 운영 환경에는 아직 반영되지 않은 상태**이며, 이는 Pilot에서 다루는 실제 예약 데이터의 정합성에 직접적이고 확인된 영향(재QA 1차 실패 이력 존재)을 미치는 항목이다. 부가 운영 요건(실인증/실발송 등)은 조건부 운영으로 완화 가능하지만, 데이터 정합성 문제는 완화가 아니라 해결이 필요한 유형이다.

---

## 8. Recommendation

1. **즉시**: STEP1.5 DateFix를 Apps Script에 "새 버전"으로 배포하고 `?action=ping` 확인 후 신규 더미로 재QA를 수행한다(PROJECT_STATUS.md §2 절차).
2. 재QA 통과 확인 후 본 보고서의 §7 판정을 재평가하여 PROJECT_STATUS.md와 ROADMAP.md의 Known Issue 상태를 "해소"로 갱신한다.
3. 재QA 통과 시점부터 v0.9.0 Pilot Release를 진행할 수 있다(구조 변경 없이, Structure Freeze v0.9.0 유지).
4. Pilot 운영 중에는 §6에 명시한 조건부 운영 지침(Mock 인증/발송 보완, 관리자 콘솔-Sheets 이원화 인지)을 준수한다.
5. DEV-003 구현, 더미 데이터 정리, 실인증/실발송 연동은 Pilot 개시 이후 순차 진행한다(ROADMAP.md "IMMEDIATE 이후"·"SHORT-TERM" 항목).

---

## 결론

❌ NOT READY FOR PILOT
