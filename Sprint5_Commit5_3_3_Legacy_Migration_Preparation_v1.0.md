# Sprint 5 Commit 5-3.3 — Legacy Migration Preparation v1.0

> **상태**: 설계 문서(분석/문서화/영향도 평가/기술부채 정리만 수행). 코드 변경 없음, Commit 없음, Push/Deploy 없음.
> **기준선(Baseline)**: `0f0ef83` — `feat: integrate portal error contract into admin ux` (Sprint5 Commit5-3.2, PM 최종 승인)
> **작성일**: 2026-07-29
> **범위**: Legacy Portal(`admin_reservations_v2_new.html`)을 향후 안전하게 전환하기 위한 Migration Blueprint. 실제 코드/삭제/전환은 이번 Commit에서 수행하지 않는다.

---

## 1. 분석 대상

`app/pages/admin_reservations_v2_new.html`(406줄, "Legacy Portal") 및 이 파일이 실제로 `<script src>`/`<link>`로 불러오는 모든 의존 파일 — `app/data/programs_data_new.js`, `app/data/sample_data_new.js`, `app/services/db_service_new.js`, `app/services/stats_service_new.js`, `app/config_v2_new.js`, `app/services/google_sheets_service_v2_new.js`, `app/components/nav_new.js`, `app/styles/main_style_new.css`. 비교 대상으로 `app/pages/admin_portal_new.html`(Admin Portal), `app/pages/reservation_v3_new.html`(Reservation Portal), `src/api/routes_admin_portal.py`, `src/services/sheets_write_service.py`, `ARCHITECTURE.md`를 함께 확인했다. 전부 실제 코드를 직접 읽어 확인했다(추측 없음).

---

## 2. Legacy 구조

### 2-1. 사용 목적

예약 목록 조회 + 상세 Dialog(`#detailModal`)에서 상태값을 직접 변경하고 메모(`note`)를 저장하는 화면. CSV 다운로드 기능 포함.

### 2-2. 호출 경로 / FastAPI 사용 여부 / GAS 직접 호출 여부

`CMC_SheetsServiceV2.getAll()/getOne()/updateStatus()/update()`(전부 `google_sheets_service_v2_new.js`)를 통해 **Google Apps Script를 직접 호출한다**(`action=list/get/updateStatus/update`). **FastAPI는 단 한 줄도 호출하지 않는다** — `fetch(`, `ADMIN_BASE`, `PORTAL_BASE` 등 FastAPI 관련 문자열이 파일 전체에 전무함을 코드 검사로 확인했다.

### 2-3. Admin Portal과 중복 기능

| 기능 | Legacy | Admin Portal |
|---|---|---|
| 예약 목록 조회 | O(Sheets 직접) | O(FastAPI `/api/admin-portal/reservations` 경유) |
| 예약 승인/거절 | **없음**(상태 드롭다운으로 임의 값 저장만 가능, "승인"이라는 개념 자체가 없음) | O(Slot/Policy 검증 포함, Sprint4 Commit2~5-2) |
| 상태를 "예약확정"으로 직접 변경 | **가능**(드롭다운에서 선택 후 저장) | 불가(승인 API를 통해서만, 검증 수반) |
| CSV 다운로드 | O | 없음 |
| 메모(note) 편집 | O | 없음 |

**중복이 아니라 상호보완**에 가깝다 — Admin Portal은 승인/거절"만" 하고, Legacy는 상태 전체를 임의로 바꿀 수 있는 범용 화면이다. 이 차이 자체가 §7 Risk의 근거다.

### 2-4. Reservation Portal과 중복 기능

없음. Reservation Portal은 신규 예약 "생성"(수검자용), Legacy는 기존 예약 "조회/수정"(직원용) — 대상 사용자와 기능이 겹치지 않는다.

### 2-5. 운영 중 사용 여부(신규 확인 사항)

- **코드는 계속 유지·갱신되고 있다** — 최근 커밋(Sprint4 Commit2)에서도 이 파일의 상태 드롭다운에 "거절" 옵션을 추가했다(파일 수정일 2026-07-28 00:46, 코드로 확인).
- **그러나 현재 활성 화면들의 내비게이션에서 이 파일로 도달하는 링크 경로가 확인되지 않는다.** `app/components/nav_new.js`(이 파일이 로드하는 공용 내비게이션)의 링크 목록은 `admin_dashboard_new.html`/`reservation_new.html`/`admin_reservations_new.html`(전부 더 오래된 v1 세대) **뿐이며, `admin_reservations_v2_new.html` 자기 자신조차 그 목록에 없다.** `admin_portal_new.html`(현재 Single Admin Portal)에도 이 파일로의 링크가 없다. 즉 **북마크나 URL 직접 입력이 아니면 도달할 방법이 코드상 확인되지 않는다** — 실제 운영 접근 로그는 이 조사 범위 밖이므로, "사용 안 함"이 아니라 "발견된 링크 경로 없음"으로 정확히 기록한다.
- Legacy 승인 우회 경로(아래 §7)는 여전히 유효하다 — Slot 조회·상태·정원·중복 검사, Sprint4 Commit5-2 Policy 검증(휴진일/의료진/검사실/장비/프로그램 제한)을 전부 건너뛴다(`ARCHITECTURE.md` §7 항목4에 기 등록).

### 2-6. 우회 경로 존재 여부

존재함(§2-5, §7 재확인). 상태 `<select>`(`#statusSel`)에서 "예약확정"/"일정변경"/"예약취소" 등 어떤 값이든 선택 후 저장하면 `CMC_SheetsServiceV2.updateStatus()`가 Sheets에 직접 쓴다 — Slot 점유도, Policy 검증도, Audit 기록도 전혀 발생하지 않는다.

### 2-7. 이번 조사로 새로 발견한 사항(신규)

Legacy 상단 통계 카드(전체/예약접수/예약확정/검진완료/취소·변경)는 `CMC_Stats.statusCounts()` → `CMC_DB.getAll()` → **브라우저 `localStorage`의 로컬 샘플 데이터**를 읽는다(`db_service_new.js` 코드 확인). 반면 아래 예약 목록 테이블은 `CMC_SheetsServiceV2.getAll()`로 **실제 Google Sheets 데이터**를 읽는다. **두 영역이 서로 다른 데이터 소스를 쓰고 있어, 통계 카드 숫자가 실제 예약 목록과 무관한 값을 보여준다** — 이번 Sprint5 조사에서 처음 확인된 기능적 결함으로, §7에 별도 Risk로 등록한다.

---

## 3. Dependency

### 3-1. Legacy가 참조하는 전체 목록

| 구분 | 파일 | Reservation Portal도 사용? |
|---|---|---|
| CSS | `app/styles/main_style_new.css` + 인라인 `<style>`(Legacy 전용 3개 클래스) | **예** |
| JS | `app/data/programs_data_new.js` | 예 |
| JS | `app/data/sample_data_new.js` | 예 |
| JS | `app/services/db_service_new.js`(localStorage CRUD) | 예 |
| JS | `app/services/stats_service_new.js`(KPI 계산) | 예 |
| JS | `app/config_v2_new.js`(dataSource 설정) | 예 |
| JS | `app/services/google_sheets_service_v2_new.js`(GAS 호출 래퍼) | 예 |
| JS | `app/components/nav_new.js`(공용 네비게이션) | 예 |
| API | Google Apps Script `action=list/get/updateStatus/update` | 예(`create`만 Reservation Portal 전용) |
| Sheets | `종합검진_예약대장`(SSOT) | 예 |
| 인라인 로직 | `const AA = {...}`(Legacy 전용, 다른 화면과 공유 없음) | 아니오(Legacy 고유) |

### 3-2. 삭제 영향도

**핵심 결론**: 공유 JS/CSS 8개 파일은 **전부 Reservation Portal(`reservation_v3_new.html`, 현재 서비스 중)도 그대로 사용한다.** Legacy Portal의 HTML 파일 자체를 제거해도 이 공유 의존성 8개는 절대 함께 제거할 수 없다 — Reservation Portal이 즉시 깨진다. **실제로 "Legacy 전용"이라 안전하게 정리 가능한 부분은 `admin_reservations_v2_new.html` 파일 자체(그 안의 인라인 `<style>`과 `const AA = {...}` 로직)뿐이며, 그 외 8개 의존 파일은 전부 존치해야 한다.**

이 발견은 Stage 4(§4 "Legacy 제거 가능 여부 검토")의 리스크를 크게 낮춘다 — 제거 대상 표면적이 생각보다 훨씬 좁다(파일 1개 + 그 파일만의 인라인 코드).

---

## 4. Migration 단계

| 단계 | 내용 | 현재 상태 |
|---|---|---|
| **Stage 1** 현행 유지 | Legacy/Admin Portal 병존, 기능·코드 무변경 | **현재 여기(Sprint5 Commit5-3.3 시점)** |
| **Stage 2** Admin Portal 우선 사용 | 운영 안내/문서상으로 "승인·거절은 Admin Portal에서" 권고, Legacy는 그 외 필요한 경우(CSV 다운로드, 메모 편집 등)만 사용 권고. **코드 변경 없이 운영 정책만으로 가능** | 미착수 — Sprint6 후보(§9) |
| **Stage 3** Legacy 읽기 전용 | Legacy의 `#statusSel`(상태 변경) 및 `dNote`(메모 저장) 쓰기 경로를 비활성화하고 조회/CSV 다운로드만 남긴다 — 우회 경로(§2-6) 자체를 코드로 차단하는 단계. **가장 중요한 단계**: §7 High Risk를 실제로 해소하는 지점 | 미착수 — Sprint6 이후 별도 PM 승인 필요 |
| **Stage 4** Legacy 제거 가능 여부 검토 | Stage 3 이후 일정 기간(운영 접근 로그로 실사용 0건 확인) 지나면 파일 제거 검토. §3-2에 따라 공유 의존 파일은 제거 대상에서 제외 | 미착수, **실제 제거는 이번 Commit은 물론 향후에도 반드시 별도 PM 승인 필요** |

각 Stage 전환은 그 자체로 별도 Commit/PM 승인 대상이며, 이번 Commit5-3.3은 이 표를 설계했을 뿐 어떤 Stage도 착수하지 않는다.

---

## 5. Reservation Portal 영향도(코드 수정 없이 분석만)

### 5-1. FastAPI 연계 가능성

현재 **불가능**하다 — `src/services/sheets_write_service.py`를 코드로 확인한 결과 `_WRITE_ACTIONS = ("updateStatus",)` 단 하나만 지원하며, GAS의 `action=create`를 FastAPI가 대리 호출하는 기능 자체가 없다. Reservation Portal을 FastAPI 경유로 전환하려면 **Backend에 신규 write 경로(예: `sheets_write_service.create_reservation()` + 신규 FastAPI 엔드포인트)를 먼저 추가해야 하며, 이는 Portal만의 문제가 아니라 명백한 Backend 변경 사항이다**(이번 Commit 범위 밖, 코드 수정 없음).

### 5-2. GAS 유지 필요성

**무조건 유지해야 한다.** ADR-013(Reservation SSOT = Google Sheets)에 따라 예약 원장의 원천은 Sheets이며, FastAPI가 쓰기를 대리하든 안 하든 GAS `sheets_api_v3_final.gs`는 Sheets 접근의 유일한 통로로 계속 필요하다. "GAS 유지 여부"는 선택지가 아니라 이미 확정된 아키텍처다.

### 5-3. Migration 필요 조건

1. Backend에 `create` write 경로 신설(§5-1) — 별도 Sprint 필요
2. 신규 예약 생성 시점에도 Policy 검증(휴진일/의료진/검사실 등)을 적용할지 여부에 대한 PM 정책 결정 — 현재는 승인 시점에만 적용됨(Sprint4 Commit5-2), 생성 시점 적용은 완전히 새로운 범위
3. `reservation_v3_new.html`의 실제 코드 변경(현재 `CMC_SheetsServiceV2.create()` 직접 호출 → FastAPI 호출로 교체)

세 조건 모두 이번 Sprint5 범위 밖이며, Reservation Portal은 **Sprint5 대상이 아님을 재확인**한다.

---

## 6. 기술부채(TD)

| ID | 내용 | 현재 상태 | 제안 |
|---|---|---|---|
| **TD-S5-01**(필수) | `admin_portal_new.html`의 `_extractDetailMessage()`가 Sprint5 Commit5-3.2에서 `parseApiError()`로 대체된 후 **호출부가 완전히 사라져 미사용 상태**(코드 검사로 재확인 — 정의만 남고 참조 0건) | 미사용, 삭제되지 않음 | 삭제 여부는 **차기 Sprint에서 검토**(이번 Commit은 분석·기록만, 코드 삭제 금지) |
| TD-S5-02(신규) | Legacy 통계 카드가 실제 Sheets 데이터가 아닌 `localStorage` 샘플 데이터를 표시(§2-7) | 기존부터 존재, 이번에 처음 문서화 | Stage 3(§4)에서 통계 카드 자체를 제거하거나 Sheets 기반으로 교체하는 방안을 함께 검토 |
| TD-S5-03(신규) | `nav_new.js`의 공용 네비게이션이 `admin_reservations_v2_new.html`(Legacy 자기 자신)이나 `admin_portal_new.html`/`reservation_v3_new.html`(현재 서비스 중인 화면)이 아닌 더 오래된 v1 화면들만 가리킴(§2-5) | 기존부터 존재 | 네비게이션 링크 갱신은 Stage 2(§4) 착수 시 함께 검토 |
| TD-S5-04(기존 등록분 재확인) | Legacy 승인 우회 경로(`ARCHITECTURE.md` §7 항목4) — Sprint4 Commit5-2 Policy 검증까지 전부 우회 | 기존 등록, 이번 조사로 범위 재확인(Policy Layer 전체 포함) | Stage 3(§4)에서 해소 |

---

## 7. Migration Checklist(운영자 확인용)

- [ ] Legacy 접근 차단 여부 — Stage 3 착수 전, 실제 접근 로그(서버/프록시 로그)로 최근 N개월 실사용 여부 확인
- [ ] Admin Portal 기능 동일성 — Legacy가 제공하는 CSV 다운로드·메모 편집 기능을 Admin Portal이 아직 제공하지 않음(§2-3 표) → Stage 3 이전에 이 기능들의 이관 필요 여부를 PM이 결정
- [ ] QA 완료 여부 — Stage 3(쓰기 경로 비활성화) 적용 시 실제 브라우저 QA로 조회/CSV 기능이 그대로 동작하는지 확인
- [ ] 사용자(운영자) 공지 필요 여부 — Legacy를 실제로 북마크해 쓰는 직원이 있다면 Stage 2/3 전환 전 사전 공지 필요
- [ ] Rollback 계획 — Stage 3에서 쓰기 UI를 비활성화할 경우, 원본 파일을 보존(`_v2` 접미사 원칙 재확인)하고 되돌릴 수 있는 방식(예: 기능 플래그가 아닌 파일 자체 백업)으로 적용
- [ ] 공유 의존 파일(§3-1의 8개) 무변경 확인 — Stage 4 검토 시 Reservation Portal 회귀 여부 반드시 재확인

---

## 8. Risk

| 등급 | 내용 | 대응 방안 |
|---|---|---|
| **High** | Legacy 우회 경로로 Slot 정원/Policy 검증을 건너뛴 예약확정이 계속 발생 가능(§2-6, §6 TD-S5-04) | Stage 3에서 쓰기 경로 비활성화가 유일한 근본 해결책. 그 전까지는 운영 정책(Stage 2, "승인은 Admin Portal에서만")으로 완화만 가능 |
| **Medium** | Legacy의 실사용 여부를 코드 조사만으로는 확정할 수 없음(§2-5) — 실제 쓰는 직원이 있는데 갑자기 막으면 업무 차질 | Stage 3 착수 전 반드시 실제 접근 로그 확인(Checklist 1번), 사전 공지 |
| Medium | 통계 카드 데이터 소스 불일치(§2-7, TD-S5-02)가 운영자에게 잘못된 정보를 줄 수 있음 | Stage 2~3 사이에 통계 카드만 우선 수정하거나 안내 문구 추가하는 것도 고려 가능(단, 이번 Commit 범위 아님) |
| Low | 공유 의존 파일(§3-1) 8개를 실수로 함께 삭제하면 Reservation Portal 회귀 | Stage 4 체크리스트에 "공유 파일 무삭제 확인"을 명시적으로 포함(§7 마지막 항목) |
| Low | `nav_new.js` 링크가 이미 오래된 화면을 가리켜 혼란을 줄 수 있음(TD-S5-03) | 급하지 않음, Stage 2에서 함께 정리 |

---

## 9. Sprint6 준비사항(목록만, 구현 없음)

1. Legacy 실제 접근 로그 확인(운영 인프라 담당과 협의 필요, 코드 작업 아님)
2. Stage 2("Admin Portal 우선 사용") 운영 정책 문서화 — 코드 변경 없이 가능하므로 Sprint6 초반 후보
3. Admin Portal에 CSV 다운로드/메모 편집 기능 이관 여부 PM 결정(§7 Checklist 2번 선행)
4. Stage 3(Legacy 쓰기 경로 비활성화) Implementation Plan 작성 — 별도 Design Freeze 단계 필요(코드 변경 전 반드시 PM 승인)
5. TD-S5-01(`_extractDetailMessage()` 삭제 여부) 결정
6. TD-S5-02(통계 카드 데이터 소스) 처리 방안 결정
7. Reservation Portal → FastAPI 연계는 Sprint6 범위에 포함하지 않음을 권고(§5에서 확인한 대로 Backend 신규 기능이 선행되어야 하는 별도 규모의 과제)

---

## 완료 조건 준수 확인

이 문서 작성 중 어떤 코드 파일도 수정하지 않았다(Read/Grep만 수행). Legacy Portal, Reservation Portal, Admin Portal, Backend, Google Sheets, Apps Script 전부 무변경. Commit/Push/Deploy 없음.
