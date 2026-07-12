# PROJECT_STATUS.md — CMC Platform (CSHSP)

> 이 문서는 프로젝트의 **현재 시점 상태 스냅샷**이다. 최신 정보를 유지하는 것이 원칙이며, 상태가 바뀔 때마다 갱신한다.

**최종 갱신**: 2026-07-12 (DEV-003 구현 완료 반영)
**버전**: v0.9.0-pilot (릴리스 상세: [RELEASE_NOTES_v0.9.0-pilot.md](RELEASE_NOTES_v0.9.0-pilot.md), 최종 검토: [PILOT_READINESS_REVIEW.md](PILOT_READINESS_REVIEW.md))
**단계**: Sprint A~I + Sprint 2(Dashboard v3) 완료 → **Architecture Freeze(Sprint 0) 완료** → **구조 Freeze(v0.9.0 기준) 확정** → **Pilot Ready 미충족 (준비 중)**

> **Architecture Freeze**와 **Pilot Ready(운영 파일럿 투입 가능 여부)**는 서로 다른 개념으로 별도 관리한다. Architecture Freeze는 설계·구조·표준 문서의 확정이며, 미해결 버그 존재와 무관하게 완료될 수 있다(DECISIONS.md ADR-010). Pilot Ready는 아래 §2의 Known Issues가 모두 해소되어야 충족된다.

> **프로젝트 구조는 v0.9.0 현재 상태로 Freeze되었다.** 구조 변경 작업은 중단하고 Pilot 종료 후 v1.0 작업으로 이관한다(DECISIONS.md ADR-011). 구조 관련 기준 문서는 [docs/STRUCTURE_REORG_ANALYSIS_new.md](docs/STRUCTURE_REORG_ANALYSIS_new.md)이다.

**현재 최우선 작업 순서**: ① STEP1.5 DateFix → ② 전체 QA → ③ v0.9.0 Pilot Release (ROADMAP.md 참조)

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
| **Pilot Ready** | 🔴 **미충족** — Known Issues §2 해결 후 재평가 |
| STEP1.5 DateFix 코드 수정 | ✅ **완료** (`_actionUpdate`/`_actionSummary` 하드닝 포함, 회귀 테스트 150건 FAIL 0) — [STEP1.5.2_DateFix_Complete_new.md](STEP1.5.2_DateFix_Complete_new.md) |
| STEP1.5 DateFix 실배포 | 🔴 **미반영 — 사용자 조치 필요** (Apps Script는 이 세션에서 배포 불가) |
| DEV-003 (관리자 예약관리 Sheets연동) | ✅ 구현+테스트 완료(60/60 PASS), Lock 재배포 대기 — Subagent-Driven Development로 구현, Architecture Freeze 준수 확인(신규 파일/폴더 구조 변경 없음, 지정된 파일만 최소 수정) |

---

## 2. Known Issues (Pilot Ready 차단 요인)

### 🟡 STEP1.5 DateFix — 코드 수정 완료, 실배포 대기 (2026-07-04 갱신)

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

---

## 2-1. DEV-003 완료 (2026-07-12) — 관리자 예약관리 Sheets Live 연동

- **구현 방식**: Subagent-Driven Development(태스크별 구현→리뷰→수정, 최종 통합 리뷰 후 단일 커밋).
- **범위**: `admin_reservations_v2_new.html` 신규 생성(원본 무수정), `sheets_api_v3_final.gs`의 `_actionUpdateStatus`/`_actionUpdate`에 LockService 보강, `config_v2_new.js` sheetName 값 정정, `google_sheets_service_v2_new.js` 503 오류 메시지 전달 수정(어댑터가 `res.error`를 버리던 결함).
- **Architecture Freeze 준수 확인**: 신규 폴더 없음, 신규 파일은 계획서에 명시된 `_v2_new`/테스트 파일뿐, 원본 `admin_reservations_new.html` 등 기존 화면 무수정(git diff 0 확인), 다른 Apps Script 액션(`create`/`list`/`get`/`summary`/`updateOps`) 로직·응답 포맷 무변경.
- **테스트**: 신규 3개 스위트 60/60 PASS(`tests/run_dev003_backend_qa.js` 26건, `tests/run_dev003_frontend_qa.js` 29건, `tests/run_dev003_adapter_error_qa.js` 5건). LOCAL 모드 브라우저 QA 통과, 원본 화면 회귀 없음.
- **DEV-003_..._Design_Final_new.md §11 QA Checklist**: 20개 항목 중 14개 완료, 1개 부분(간접) 확인, 5개는 아래 Release Checklist 항목에 의존해 대기.

### Release Checklist (Pilot Ready 전 필수, DEV-003 커밋 범위 밖)

| # | 항목 | 비고 |
|---|------|------|
| 1 | Google Apps Script(`sheets_api_v3_final.gs`) 재배포 — "새 버전" | STEP1.5 DateFix + DEV-003 Lock 보강 동시 반영됨. 사용자 조치 필요(Google 계정 인증 필요, 이 세션에서 불가) |
| 2 | Live 모드 API 응답시간 실측(NFR 기준 3초 이내) | 재배포 후 실측 |
| 3 | `reservation_v2_new.html` 실제 브라우저 QA | 이번 세션 도구(스크린샷) 장애로 미완, 파일 자체는 무수정 확인됨(회귀 위험 낮음) |
| 4 | `CMC_CONFIG.load()` 미호출 — 모드전환 롤백 미작동 | Follow-up 세션 진행 중(task_a8cf5790). DEV-003 발견이나 이 폴더 전체(원본 페이지 포함)에 적용되는 기존 결함이라 별도 티켓으로 분리 |

---

## 3. 진행 중 / 대기 항목

| 항목 | 상태 | 비고 |
|---|---|---|
| `admin_reservations_v2_new.html` (DEV-003 구현) | ✅ 완료, Lock 재배포만 대기 | §2-1 Release Checklist 참조 |
| 더미 예약 데이터 정리 | 파일럿 1주차 허용 | `data/reservations.json` 중 QA 더미 |
| 더미 계정 정리 (USR-0001~0003) | WARN, 운영 전 정리 필요 | `data/users.json` |
| LLM 기반 의도 분류 전환 | 규칙 기반이 기본, Claude API는 Key 설정 시만 | `agent_orchestrator.py` 교체 지점 주석 있음 |
| 실키 실호출 스모크 테스트 | 미실시 (`CSHSP_SMOKE_LIVE=1` 옵트인) | 파일럿 전 1회 필요 |
| SQLite 마이그레이션 | 계획 문서만 존재 | `docs/SQLite_Migration_Plan.md` |
| 관리자 인증(로그인) | 미구현 | 운영 전 필수 |
| HTTPS 적용 | 시제품 미적용 | 운영 전 필수 |

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
