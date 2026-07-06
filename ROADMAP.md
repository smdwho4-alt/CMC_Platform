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
| STEP1.5 | DateFix QA — 결함 발견 및 수정 코드 작성 | ⚠️ 코드 완료, **배포 미반영** (PROJECT_STATUS.md 참조) |
| Sprint A | Core Data Layer (20 Entity JSON, 로더/검증) | ✅ |
| Sprint B | Reservation Engine (상태머신, Slot, 감사로그) | ✅ |
| Sprint C | Admin Console (7개 메뉴, Mock API) | ✅ |
| Sprint D | API Layer (FastAPI, 36 엔드포인트) | ✅ |
| Sprint E | 규칙 기반 AI 에이전트 (5종) | ✅ |
| Sprint F | AI Chat Widget (SSE 스트리밍) | ✅ |
| Sprint G | Claude API 연동, 세션/Rate Limit/AI Dashboard | ✅ |
| Sprint H | 파일럿 전환 절차, 장애 대응, 백업·복구 | ✅ |
| Sprint I | 품질 게이트 (16항목) — PASS | ✅ |
| Sprint 2 | Dashboard v3 (운영센터, KPI 6종, AI 추천) | ✅ |

---

## Sprint 0 — Architecture Freeze: ✅ 완료

- 목표: 신규 기능 개발 중단, SSOT 문서(CLAUDE.md/ARCHITECTURE.md/ROADMAP.md/DECISIONS.md/PROJECT_STATUS.md) 확립
- Architecture Freeze는 설계·구조·표준 문서 확정을 의미하며, 미해결 버그(STEP1.5 DateFix 등)와 무관하게 완료된다(DECISIONS.md ADR-010).
- Architecture Freeze 완료와 Pilot Ready(운영 파일럿 투입 가능 여부)는 별개로 관리한다. Pilot Ready는 아래 "Sprint J 이전 필수 해결 과제"가 모두 해소되어야 재평가한다 (PROJECT_STATUS.md 참조).

---

## 구조 Freeze 및 최우선 작업 순서 (2026-07-04 확정)

Pilot용 프로젝트 구조는 **v0.9.0 현재 상태로 Freeze**한다. 구조 변경(§ `docs/STRUCTURE_REORG_ANALYSIS_new.md` 참조)은 착수하지 않으며, `docs/STRUCTURE_REORG_ANALYSIS_new.md`를 구조 관련 기준 문서(baseline)로 삼는다(DECISIONS.md ADR-011). 구조 변경이 필요한 작업은 전부 **Pilot 종료 후 v1.0 작업으로 이관**한다.

Pilot 전 최우선 작업은 다음 순서로 진행한다.

```
1) STEP1.5 DateFix   ✅ 코드 수정+회귀테스트 완료 (2026-07-04) / 🔴 실배포 대기 (사용자 조치)
      ↓
2) 전체 QA           ✅ 완료 (Sprint A/B/D/E/I 재실행, 150건+13/2/1/0, 회귀 없음)
      ↓
3) v0.9.0 Pilot Release   ⏳ 대기 (1의 실배포 확인 후 진행)
```

이 순서를 따르는 동안 구조 변경, DEV-003 구현 등 다른 작업은 후순위로 미룬다. STEP1.5 DateFix의 코드 수정·테스트는 완료되었으나 Google Apps Script 실배포는 Google 계정 인증이 필요한 수동 작업이라 에이전트가 대신 수행할 수 없다 — 상세: [STEP1.5.2_DateFix_Complete_new.md](STEP1.5.2_DateFix_Complete_new.md), [PROJECT_STATUS.md](PROJECT_STATUS.md) §2.

---

## Sprint J 이전 필수 해결 과제 (Pilot Ready 전제조건)

| 과제 | 상태 | 비고 |
|---|---|---|
| **STEP1.5 DateFix 코드 수정** | ✅ **완료** (2026-07-04) | `_actionCreate`/`_rowToObj`(STEP1.5.1) + `_actionUpdate`/`_actionSummary`(STEP1.5.2) 하드닝. STEP1.5.2_DateFix_Complete_new.md |
| **STEP1.5 DateFix 실배포 + 재QA** | 🔴 미해결, **최우선(사용자 조치)** | Apps Script "새 버전" 배포 필요, 에이전트가 대신 수행 불가. PROJECT_STATUS.md §2 |
| 전체 QA (회귀 테스트 스위트 + 시나리오 리허설) | ✅ 완료 (2026-07-04) | Sprint A(30)/B(38)/D(36)/E(31) + Sprint I 품질게이트(13/2/1/0) + DateFix Node 테스트(15) = 150건 FAIL 0 |
| DEV-003 구현 | ⚠️ 설계만 확정, 후순위 | `admin_reservations_v2_new.html` 신규 작성, Lock 적용(DECISIONS.md ADR-007) |
| 더미 데이터/계정 정리 | 대기, 후순위 | `data/reservations.json` QA 더미, `data/users.json` 더미 3계정 |
| 프로젝트 구조 재편 | 🚫 **Pilot 기간 중 착수하지 않음** | v1.0 작업으로 이관(DECISIONS.md ADR-011), 기준 문서: `docs/STRUCTURE_REORG_ANALYSIS_new.md` |

이 표의 항목이 모두 해소되기 전에는 Sprint J(신규 기능 개발 재개) 착수 및 Pilot Ready 선언을 하지 않는다. 단, DEV-003과 더미 데이터 정리는 §"구조 Freeze 및 최우선 작업 순서"의 1~3단계 완료 이후로 순서를 조정한다.

---

## 다음 단계 (Sprint 0 이후 후보)

### IMMEDIATE (최우선 순서 — 위 "구조 Freeze 및 최우선 작업 순서" 참조)

1. **STEP1.5 DateFix 실배포** — 코드 수정 완료, Apps Script "새 버전" 배포는 사용자 조치 필요 + 재QA. (PROJECT_STATUS.md §2)
2. **전체 QA** — ✅ 완료 (Sprint A/B/D/E/I 재실행 + DateFix 회귀 테스트, 150건 FAIL 0)
3. **v0.9.0 Pilot Release** — 1의 실배포 확인 후 개시

### IMMEDIATE 이후 (Pilot Release 후 순차 진행)

4. **DEV-003 구현** — `admin_reservations_v2_new.html` 신규 작성, Lock 적용, 설계는 이미 확정됨(DECISIONS.md ADR-007).
5. **더미 데이터/계정 정리** — `data/reservations.json` QA 더미, `data/users.json` 더미 3계정.

### SHORT-TERM (2~3주)

6. **LLM 기반 의도 분류 전환 검토** — 현재 규칙 기반이 기본, Claude API는 옵트인. 전환 여부는 별도 ADR로 결정 필요.
7. **실키 실호출 스모크 테스트** — `CSHSP_SMOKE_LIVE=1`로 1회 실행, 과금·응답 검증.
8. **관리자 인증(로그인) 구현** — 현재 미구현, 운영 전 필수.
9. **HTTPS 적용** — 현재 시제품 미적용, 운영 전 필수.
10. **실인증/실발송 연동** — 현재 Mock, Pilot Conditional Go 조건 해소용(PILOT_READINESS_REVIEW.md §3 참조).

### MEDIUM-TERM (1개월 이상, v1.0 후보)

11. **프로젝트 구조 재편** — `docs/STRUCTURE_REORG_ANALYSIS_new.md` 기준으로 v1.0 단계에서 착수 여부 재검토(DECISIONS.md ADR-011).
12. **SQLite 마이그레이션 검토** — `docs/SQLite_Migration_Plan.md` 기반, JSON 대비 성능/동시성 비교 후 착수 여부 결정.
13. **파일럿 운영** — 일일 체크리스트(`CSHSP_Pilot_Daily_Checklist.md`) 가동, Stop Criteria 모니터링(`CSHSP_Pilot_Stop_Criteria.md`).
14. **Go-Live 준비** — Go-Live 기준(`CSHSP_GoLive_Decision_Criteria.md`) 충족 확인.

---

## 보류/미착수 (우선순위 미정)

- 이중 백엔드(Sheets ↔ 로컬 JSON) 통합 여부 결정
- git 버전관리 도입 여부 (현재 파일명 접미사로 대체, DECISIONS.md ADR-008)
- 프로젝트 구조 재편 (v1.0 이관, DECISIONS.md ADR-011)
