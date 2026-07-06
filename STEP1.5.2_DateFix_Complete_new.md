# STEP 1.5.2 — DateFix 코드 수정 완료 & 회귀 테스트

> 목적: STEP1.5(날짜 포맷 결함) / STEP1.5.1(1차 수정 시도, 배포 미반영으로 실패)에 이어
> 코드 수정을 완료하고 회귀 테스트로 검증한다.
> 대상: `app/apps_script/sheets_api_v3_final.gs`
> 작성: 2026-07-04
> 구조 변경 없음 (Structure Freeze v0.9.0 유지, DECISIONS.md ADR-011)

---

## 1. Root Cause (근본 원인)

### 1-1. 원본 원인 (STEP1.5에서 이미 확인됨, 재확인)

Google Sheets는 `appendRow`/`setValue`로 들어오는 문자열이 날짜·시간처럼 보이면 셀 서식이 명시적으로 텍스트('@')가 아닌 한 자동으로 **Date/시간 serial로 변환**한다.

- `birth`(`1980-05-05`) → `1980-05-05 00:00:00`
- `wishDate`(`2026-07-20`) → `2026-07-20 00:00:00`
- `wishTime`(`09:00`) → `1899-12-30 09:00:00` (스프레드시트 기준일 1899-12-30 기반 datetime으로 왜곡)

읽을 때 과거 `_rowToObj`가 모든 Date 값을 `DATE_FORMAT='yyyy-MM-dd HH:mm:ss'`로 일괄 포맷했기 때문에 날짜에 시간이 붙고 시간 필드는 완전히 왜곡되어 표시됐다.

STEP1.5.1에서 이미 (a) `_actionCreate`에서 3개 필드를 텍스트('@')로 재기록, (b) `_rowToObj`에서 필드별 포맷(생년월일·희망검진일→`yyyy-MM-dd`, 희망시간→`HH:mm`) 적용이라는 수정을 작성했으나, **Apps Script 배포 시 "새 버전"을 선택하지 않아 실제 `/exec` 엔드포인트에는 반영되지 않았다** (재QA 1차 실패, 0004 더미로 확인). 이는 코드 결함이 아니라 배포 절차 누락이었다.

### 1-2. 이번에 추가로 발견한 근본 원인 (STEP1.5.1이 놓친 부분)

코드를 재검토한 결과, STEP1.5.1의 수정은 **`_actionCreate`(신규 등록)와 `_rowToObj`(표시용 읽기)만 보호**했고, 아래 2곳은 여전히 취약했다:

1. **`_actionUpdate`(전체 필드 수정 API)**: `birth`/`wishDate`/`wishTime`을 수정할 때 텍스트 서식을 강제하지 않았다. 신규 생성 시에는 셀 서식이 이미 '@'로 고정되어 있어 문제가 즉시 드러나지 않지만(서식이 "sticky"하게 유지됨), **STEP1.5 배포 이전에 생성된 레거시 행**(셀 서식이 아직 자동/Date인 행 — 예: 기존 QA 더미 `20260701-0001~0004`)을 이 경로로 수정하면 Sheets가 다시 Date로 자동 변환해 결함이 재발한다. DEV-003(관리자 예약관리 Sheets연동)이 구현되면 이 API가 실제로 쓰이게 되므로 반드시 선제 수정이 필요했다.
2. **`_actionSummary`(당일 운영 요약)**: `_rowToObj`를 거치지 않고 시트 원본 셀 값을 `String(r[COL.희망검진일-1]) === today`로 **직접 문자열 비교**하고 있었다. 셀이 Date 타입으로 저장돼 있으면(레거시 행, 또는 1번 경로로 재손상된 행) `String(Date객체)`가 `'yyyy-MM-dd'`와 절대 일치하지 않아 **당일 통계가 0으로 집계**되는 문제가 원본 STEP1.5 QA에서 우려했던 그대로 남아 있었다. `_rowToObj`가 이미 필드별 정규화를 하고 있음에도 `_actionSummary`만 이를 우회하고 있었던 것이 근본 원인이다.

**결론**: 날짜 자동변환이라는 근본 원인 자체(Google Sheets의 동작 방식)는 우회할 수 없으므로, "쓰기 시 텍스트 강제 + 읽기 시 정규화"라는 원칙을 **모든 쓰기 경로(create·update)와 모든 읽기/집계 경로(get·list·summary)에 빠짐없이 적용**하는 것이 올바른 해결책이다. STEP1.5.1은 이 원칙을 create/rowToObj에만 적용했고, 이번 STEP1.5.2에서 update/summary까지 확장했다.

---

## 2. 수정 내용

파일: `app/apps_script/sheets_api_v3_final.gs`

| 함수 | 수정 전 | 수정 후 |
|---|---|---|
| `_actionUpdate` | `sheet.getRange(sheetRow, col).setValue(val)` — 모든 필드 동일 처리 | `birth`/`wishDate`/`wishTime`은 `setNumberFormat('@').setValue(String(val))`로 텍스트 강제. 그 외 필드는 기존과 동일 |
| `_actionSummary` | `rows.filter(r => r[0] !== '' && String(r[COL.희망검진일-1]) === today).map(_rowToObj)` — 원본 셀 직접 비교 | `rows.filter(r => r[0] !== '').map(_rowToObj).filter(r => r.wishDate === today)` — `_rowToObj` 정규화 후 비교 |
| 파일 헤더 | Version 1.0 | Version 1.1, DateFix 강화 내역 명기 |

`_actionCreate`, `_rowToObj`(STEP1.5.1에서 이미 수정됨), `doGet`/`doPost` 라우팅, `_generateNo`, `LockService` 사용, 그 외 26개 컬럼 처리 로직은 **변경하지 않았다.**

---

## 3. 변경 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `app/apps_script/sheets_api_v3_final.gs` | `_actionUpdate`, `_actionSummary` 로직 수정 + 헤더 주석 갱신 (신규 작성 아님, 기존 "최종 배포본" 파일 직접 수정 — 이 파일은 이미 STEP1.5.1에서 직접 수정된 전례가 있음) |
| `tests/run_step1_5_datefix_qa.js` | 신규 작성 — Node `vm` 기반 Apps Script 모의 실행 회귀 테스트 (15개 시나리오) |
| `tests/step1_5_datefix_qa_result.csv` | 신규 생성 — 위 테스트 결과 |
| `tests/sprint_a_test_result.csv` / `sprint_b_test_result.csv` / `sprint_d_test_result.csv` / `sprint_e_test_result.csv` / `sprint_i_quality_gate_result.csv` | 재실행으로 갱신 (회귀 없음 확인) |
| `STEP1.5.2_DateFix_Complete_new.md` | 이 문서 (신규) |

**구조 변경 없음**: 새 폴더 생성, 파일 이동, 이름변경 없음 (Structure Freeze v0.9.0 준수, DECISIONS.md ADR-011).

---

## 4. 테스트 결과

### 4-1. 신규: DateFix 전용 회귀 테스트 (Node, `tests/run_step1_5_datefix_qa.js`)

Apps Script는 로컬에서 직접 실행할 수 없으므로, `sheets_api_v3_final.gs` 원본을 Node `vm` 샌드박스에 그대로 로드하고 `SpreadsheetApp`/`Utilities`/`LockService`/`ContentService`를 모의(mock)하여 **실제 배포 코드와 항상 동일한 파일**을 검증한다. 가짜 시트는 Google Sheets의 "서식이 텍스트가 아니면 날짜처럼 보이는 문자열을 Date로 자동 변환"하는 동작을 그대로 재현한다.

```
총 15건 중 실패 0건
```

검증 시나리오:
1. 신규 예약 생성 후 `birth`/`wishDate`/`wishTime`이 시간·에폭 왜곡 없이 정상 반환됨
2. 생성 직후 시트 원본 셀이 실제로 문자열로 저장됨(표시값이 아닌 원본 타입 확인)
3. 신규 예약이 `summary` 당일 통계에 정상 포함됨
4. **레거시(Date 타입) 행을 `update`로 수정하면 텍스트로 강제 전환됨** — `_actionUpdate` 수정 검증
5. 레거시 행 수정 후 `summary`가 새 날짜로 정상 집계됨
6. 일반 `update` 호출 후에도 셀이 텍스트로 유지됨(재손상 없음)
7. `update` 이후 신규/이전 날짜 모두 `summary` 매칭 정상
8. **레거시(Date 타입) 손상 데이터가 존재해도 `summary`가 `_rowToObj` 정규화를 거쳐 정상 집계됨** — `_actionSummary` 수정 검증
9. 레거시 데이터도 `get` 조회 시 정상 포맷으로 표시됨

**테스트 유효성 검증(가짜 통과 방지)**: 수정 전 코드로 되돌린 상태에서 동일 테스트를 실행해 실제로 실패하는지 확인했다.
- `_actionSummary` 수정을 되돌리면 → 레거시 데이터 집계 테스트 실패 (총 15건 중 1건 실패) 확인
- `_actionUpdate` 수정을 되돌리면 → 레거시 행 update 테스트 실패 (총 15건 중 1건 실패) 확인
- 두 수정을 모두 적용한 최종 상태에서 15/15 전체 통과 재확인

### 4-2. 예약 흐름 전체 QA (Python, 기존 Sprint 테스트 스위트 재실행)

DateFix는 Google Sheets(Apps Script) 경로에만 관련되며 Python JSON 기반 예약 엔진과는 독립적이지만(ARCHITECTURE.md §7 이중 백엔드), "예약 흐름 전체"에 대한 회귀 여부를 확인하기 위해 예약 관련 전체 스위트를 재실행했다.

| 스위트 | 결과 |
|---|---|
| Sprint A (Core Data Layer) | 30/30 PASS |
| Sprint B (Reservation Engine — 상태머신·Slot·감사로그) | 38/38 PASS |
| Sprint D (API Layer — 36개 엔드포인트, 동시성 포함) | 36/36 PASS |
| Sprint E (AI 에이전트 — reservation_agent 포함) | 31/31 PASS |
| Sprint I (품질 게이트, 16항목) | PASS 13 / WARN 2 / SKIPPED 1 / FAIL 0 (배포 전과 동일 — 회귀 없음) |

**총 135건(Python) + 15건(Node DateFix) = 150건, FAIL 0.**

---

## 5. 남은 리스크 (Remaining Risks)

### 🔴 1) 실제 Google Apps Script 배포는 이 세션에서 수행하지 못함 (가장 중요)

이번 작업은 저장소 내 `.gs` **소스 코드**를 수정하고 로컬 모의환경에서 검증한 것이며, **실제로 운영 중인 Google Apps Script 웹앱(`/exec` 엔드포인트)에는 반영되지 않았다.** Apps Script는 Google 계정 인증이 필요한 웹 콘솔(또는 clasp+OAuth) 작업이며, 이 세션에는 해당 자격증명·브라우저 접근 권한이 없다. **사용자가 직접 아래 절차로 배포해야 한다** (STEP1.5.1 문서와 동일 절차):
1. Apps Script 편집기에서 `sheets_api_v3_final.gs`의 최신 내용(Version 1.1, `_actionUpdate`/`_actionSummary` 수정분 포함)이 반영됐는지 확인
2. 배포 → 배포 관리 → 편집 → **"새 버전" 선택** → 배포 (기존 버전 재사용 시 반영되지 않음, STEP1.5.1에서 이미 겪은 실패 원인)
3. `?action=ping` 정상 확인
4. 신규 더미로 재QA: birth/wishDate/wishTime이 시간·에폭 없이 저장되는지 확인

**배포 전까지는 Known Issue가 "코드 수정 완료, 배포 대기"로만 격상되며, 완전히 해소된 것은 아니다.**

### 🟡 2) 기존에 손상된 레거시 데이터는 이번 수정으로 자동 치유되지 않음

실제 운영 시트에 이미 존재하는 QA 더미(`20260701-0001~0004`)나 배포 전에 생성된 행은 셀이 여전히 Date 타입으로 저장되어 있다. 이번 수정은 **`_actionSummary`가 이런 행도 정상 집계**하도록 방어했지만, **표시값 자체(셀의 저장 타입)를 일괄 재정렬(migration)하지는 않는다.** 해당 더미는 PROJECT_STATUS.md에 이미 "파일럿 전 정리 대상"으로 등록되어 있으므로 별도 마이그레이션 스크립트 없이 삭제로 해결 가능하다고 판단한다. 삭제 대신 보존이 필요하다면 별도 마이그레이션 작업이 필요하다.

### 🟡 3) 테스트는 Apps Script의 "모의(mock)" 환경이며 실제 Google Sheets 동작과 100% 동일하지 않을 수 있음

`tests/run_step1_5_datefix_qa.js`의 가짜 `SpreadsheetApp`은 알려진 자동변환 규칙(`yyyy-MM-dd`, `HH:mm`, `yyyy-MM-dd HH:mm:ss` 패턴)만 재현한다. 실제 Google Sheets의 로케일·타임존 설정에 따른 미세한 차이(예: 다른 지역 로케일에서의 날짜 파싱 규칙)까지 완전히 재현하지는 못한다. **배포 후 실제 시트에서의 재QA(위 §5-1 4번)가 최종 검증으로서 반드시 필요하다.**

### 🟢 4) DEV-003(관리자 예약관리 Sheets연동)과의 연관성

DEV-003이 구현되면 관리자가 `_actionUpdate`(또는 이를 감싼 API)로 예약을 자주 수정하게 된다. 이번에 `_actionUpdate`를 선제적으로 강화해 두었으므로 DEV-003 구현 시 추가 조치는 필요하지 않을 것으로 예상하나, 실제 구현 시점에 이 경로를 통합 테스트하는 것을 권장한다.

---

## 6. 판정

| 항목 | 상태 |
|---|---|
| Root cause 규명 | ✅ 완료 (원본 원인 재확인 + `_actionUpdate`/`_actionSummary` 잔존 취약점 추가 규명) |
| 코드 수정 | ✅ 완료 (`_actionUpdate`, `_actionSummary`, 구조 변경 없음) |
| 회귀 테스트 작성/갱신 | ✅ 완료 (신규 Node 테스트 15건 + 기존 Python 스위트 135건, 총 150건 FAIL 0) |
| 예약 흐름 전체 QA | ✅ 완료 (Sprint A/B/D/E/I 재실행, 회귀 없음) |
| **실 배포** | 🔴 **미완료 — 사용자 조치 필요** (§5-1) |
| STEP1.5 Known Issue 최종 해소 | ⏳ 배포 + 실사이트 재QA 후 확정 |

이 결과는 [PROJECT_STATUS.md](PROJECT_STATUS.md)의 Known Issues, [ROADMAP.md](ROADMAP.md)의 최우선 작업 순서에 반영한다.
