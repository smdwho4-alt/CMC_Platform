# Sprint 6 Closeout Report v1.0

> **기준선(Baseline)**: `e130254` — `refactor: resolve sprint6 technical debt` (Sprint6 Commit6-2, PM 승인)
> **작성일**: 2026-07-29
> **범위**: Sprint6(Commit6-1/6-2) 최종 회귀 검증, 문서 정합성 확인, Release Note, 기술부채 상태 확정. 신규 기능 없음.

---

## 1. 전체 Regression 결과

| 스위트 | 결과 |
|---|---|
| Sprint5 Parser QA(`run_sprint5_commit5_3_1_portal_error_parser_qa.js`) | **58/58 PASS** |
| Sprint6 Legacy Guard QA(`run_sprint6_commit6_1_legacy_approval_guard_qa.js`) | **24/24 PASS** |
| Sprint6 TD Cleanup QA(`run_sprint6_commit6_2_technical_debt_cleanup_qa.js`) | **12/12 PASS** |
| Backend Commit5-2(`run_sprint4_commit5_2_approval_pipeline_policy_integration_qa.py`) | **47/47 PASS** |
| Backend Commit3A(`run_sprint4_commit3a_slot_hardening_qa.py`) | **59/59 PASS** |
| Backend Commit3(`run_sprint4_commit3_slot_integration_qa.py`) | **49/49 PASS** |
| Backend Commit2(`run_sprint4_commit2_approval_qa.py`) | **68/68 PASS** |
| Backend Commit5-1(`run_sprint4_commit5_1_validation_context_program_mapping_qa.py`) | **29/29 PASS** |
| SprintB(`run_sprint_b_tests.py`) | **38/38 PASS** |

전 스위트 실제 재실행(`e130254` 기준선 위에서), 신규 실패 없음. Commit6-1(Legacy Guard)·Commit6-2(TD Cleanup) 반영 이후에도 Backend 6개 스위트 전부 무회귀.

---

## 2. Architecture 문서 정합성 결과

| 문서 | 점검 결과 | 조치 |
|---|---|---|
| `ARCHITECTURE.md` §7 항목4(Legacy 승인 우회 경로) | **불일치 발견** — Sprint6 Commit6-1로 "예약확정" 우회가 실제로 차단됐음에도 문서는 여전히 "완전 우회 중"으로 기술되어 있었고, 후속 작업명도 실제와 다른 "Sprint 4 Commit 5"로 잘못 남아 있었음 | **최소 수정**: 항목4를 "부분 해소(2026-07-29)"로 갱신, Commit6-1의 가드 방식과 검진완료/일정변경/예약취소/거절이 의도적으로 남아있다는 설계 근거, 완전 해소 조건을 정확히 반영. 그 외 §7 항목1~3, 문서 나머지 구조는 무변경(대규모 개편 없음) |
| `ADR-015_Slot_Status_Policy_Draft.md` | Sprint6은 Slot 상태 정책(AVAILABLE/FULL/BLOCKED/HOLD/WAITING)을 전혀 건드리지 않았음(Commit6-1/6-2는 Legacy Portal UI 가드·통계 소스 교체) — **확인 결과 변경 불필요** | 무변경(상태 "Proposed" 그대로 유지, PM 확인 필요 사항도 그대로) |
| `Sprint5_Commit5_3_3_Legacy_Migration_Preparation_v1.0.md` | Stage 3을 "전체 쓰기 경로 비활성화"로 기술한 원안은 Sprint6 Design Freeze에서 발견한 사실(검진완료/일정변경/예약취소는 Admin Portal에 대응 기능 없음)에 따라 실제로는 더 좁게 구현됨 — 이 divergence는 이미 Sprint6 Design Freeze 문서 §5에 명시적으로 기록되어 있어 두 문서를 함께 읽으면 정합함 | 무변경(과거 시점 문서로 보존, 최신 해석은 Design Freeze 문서가 담당) |
| `Sprint6_Design_Freeze_v1.0.md` | Commit6-1/6-2 실제 구현이 이 문서의 S1(예약확정만 차단)·S2(_extractDetailMessage 삭제)·S3(통계 카드 소스 교체) 제안과 정확히 일치함을 재확인 | 무변경 |

---

## 3. Sprint6 Release Note

**1. Sprint6 목표**
Sprint5 Closeout에서 인계된 기술부채(TD-S5-01~05)와 Legacy Portal의 남은 Critical Risk(예약확정 우회)를 안전하게 정리한다.

**2. 구현 내용**
- Commit6-1: Legacy Portal(`admin_reservations_v2_new.html`)의 `AA.saveStatus()`에 `approvalBlocked` 가드 추가 — "예약접수→예약확정" 전이만 차단, 그 외 검진완료/일정변경/예약취소/거절/메모저장은 무영향.
- Commit6-2: `admin_portal_new.html`의 미사용 `_extractDetailMessage()` 삭제(`parseApiError()`로 일원화), Legacy Portal 통계 카드 데이터 소스를 `localStorage` 샘플에서 실제 Sheets 캐시(`this.cache`)로 교체.

**3. Resolved 항목**
- TD-S5-01(`_extractDetailMessage()` 미사용) — 삭제 완료
- TD-S5-02(Legacy 통계 카드 데이터 소스 불일치) — 실데이터 소스로 교체 완료
- TD-S5-04(Legacy 승인 우회 경로) — **부분 해소**: 정원/Policy 우회의 핵심인 "예약확정" 전이만 차단, 나머지 전이는 설계상 의도된 대로 유지

**4. Deferred 항목**
- TD-S5-03(`nav_new.js` 오래된 링크) — Migration Stage 2에서 함께 처리 예정, 이번 Sprint 범위 아님
- TD-S5-05(sprint3_rbac 테스트 CSV 스냅숏 미갱신) — 코드 결함 아님, 해당 테스트를 정당한 사유로 재실행하는 시점에 자연 해소
- Legacy 승인 우회의 **완전 해소**(검진완료/일정변경/예약취소를 Admin Portal에 구현) — Backend 신규 기능 필요, 별도 Sprint

**5. Regression 결과**
§1 표 참조 — 전 스위트(Node 3개 + Backend 6개) PASS, 신규 실패 없음.

**6. 영향 범위**
`admin_portal_new.html`, `admin_reservations_v2_new.html` 2개 Portal 파일 + 관련 테스트만. Backend/FastAPI/Reservation Portal/Google Sheets/Apps Script 전부 Sprint6 전체 기간 무변경(Commit6-1/6-2 각 완료 보고에서 git diff로 실측 확인, 이번 Closeout에서 최종 재확인).

**7. Sprint7 인계사항**
1. Legacy 승인 우회의 완전 해소 — Admin Portal에 검진완료/일정변경/예약취소 기능 신설(신규 FastAPI 엔드포인트 필요, 규모 있는 별도 과제).
2. TD-S5-03(`nav_new.js` 링크 정리) — Migration Stage 2 착수 시 함께.
3. Migration Stage 2(Admin Portal 우선 사용 운영 정책 문서화) — 코드 변경 없이 가능, Sprint7 초반 후보.
4. Legacy 실제 접근 로그 확인(운영 인프라 협의) — Stage 3 완전판/Stage 4 검토의 선행조건.
5. Reservation Portal → FastAPI 연계는 계속 제외 권고(Backend 신규 write 경로 선행 필요, Sprint5/6에서 반복 확인된 결론).

---

## 4. 기술부채 상태(최종 확정)

| ID | 상태 | 근거 |
|---|---|---|
| TD-S5-01 | **Resolved** | Commit6-2에서 `_extractDetailMessage()` 삭제, 호출부 재확인 0건 |
| TD-S5-02 | **Resolved** | Commit6-2에서 `renderStats()`를 `this.cache` 기준으로 교체, 오프라인 테스트 12건 PASS로 실제 집계 정확성 확인 |
| TD-S5-03 | **Deferred** | Migration Stage 2로 이월, 영향도 낮음(Low Risk, Sprint5 등록 그대로 유효) |
| TD-S5-04 | **Partial** | Commit6-1로 "예약확정" 우회(정원/Policy 검증 우회, 원래 등록됐던 위험의 핵심)는 해소. 검진완료/일정변경/예약취소는 `reservation_approval_states.py` 설계상 원래 이 화면 전담 범위라 우회가 아니며, 완전 해소는 Admin Portal 기능 확장이 선행돼야 함(별도 Sprint) |
| TD-S5-05 | **Deferred** | 코드 결함 아님(스냅숏 CSV 미갱신), 재실행 시 자연 해소 |

---

## 5. Workspace Hygiene(분류)

`git status --short` / `git diff --stat` 실행 결과:

| 구분 | 항목 |
|---|---|
| Sprint6 관련(이번 Commit 대상) | `ARCHITECTURE.md`(§7 항목4 갱신), `Sprint6_Closeout_Report_v1.0.md`(신규) |
| 이전부터 존재한 변경(Sprint6 무관) | `ADR-015_Slot_Status_Policy_Draft.md`(Sprint4 Commit4부터 계속 보류 중, 이번에도 무변경 확인만 함) |
| 기술부채 관련 | `tests/sprint3_rbac_test_result.csv`(TD-S5-05, 원인 이미 확정) |
| 무관한 문서(Sprint4 이전) | 35개 untracked `.md` + `tools/backup/` + `tools/reports/Daily_Check_20260712.html` — 전부 그대로 |

**새로운 이상 없음** — Sprint5 Closeout 시점 분류와 동일한 항목들만 계속 존재, Sprint6 작업으로 인한 신규 미분류 변경사항 없음.

---

## 6. Sprint6 산출물

| Commit | 파일 |
|---|---|
| Commit6-1(`306a3a0`) | `app/pages/admin_reservations_v2_new.html`, `tests/run_sprint6_commit6_1_legacy_approval_guard_qa.js`, 결과 CSV |
| Commit6-2(`e130254`) | `app/pages/admin_portal_new.html`, `app/pages/admin_reservations_v2_new.html`, `tests/run_sprint4_commit3_slot_integration_qa.py`, `tests/run_sprint5_commit5_3_1_portal_error_parser_qa.js`, `tests/run_sprint6_commit6_2_technical_debt_cleanup_qa.js`, 결과 CSV 3개 |
| Commit6-3(이번) | `ARCHITECTURE.md`, `Sprint6_Closeout_Report_v1.0.md` |
| Design Freeze(비-Commit, 이전 단계) | `Sprint6_Design_Freeze_v1.0.md`(미커밋 상태로 존재, Sprint5의 Design Freeze 문서와 동일한 패턴) |

---

## 완료 조건 준수 확인

Backend/FastAPI/Admin Portal 기능/Reservation Portal/Legacy Portal 기능/Google Sheets/Apps Script/Business Rule — 전부 무변경(git diff로 재확인). 대규모 문서 개편 없음(ARCHITECTURE.md 1개 항목만 최소 수정).
