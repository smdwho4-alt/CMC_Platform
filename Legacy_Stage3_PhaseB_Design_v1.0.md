# Legacy Stage3 Phase B Design v1.0

> **상태**: 설계 문서(Design Only). 코드 변경 없음, API 추가 없음, Legacy 기능 차단 없음, Business Rule 확정 없음, Commit 없음(문서만), Push/Deploy 없음.
> **기준선(Baseline)**: `7f7d915` — `docs: add operation readiness assessment` (Sprint7 Commit7-2)
> **작성일**: 2026-07-29
> **목적**: Legacy Portal이 담당 중인 예약변경/예약취소/검진완료 3개 전이를 Admin Portal/FastAPI 기반으로 안전하게 전환하기 위한 Phase B 설계를 확정한다.

---

## 목차

1. [목적](#1-목적)
2. [범위 및 제외 범위](#2-범위-및-제외-범위)
3. [근거 문서와 코드](#3-근거-문서와-코드)
4. [AS-IS 흐름](#4-as-is-흐름)
5. [전이별 상세 분석](#5-전이별-상세-분석)
6. [상태 전이 규칙](#6-상태-전이-규칙)
7. [영향도 분석](#7-영향도-분석)
8. [설계 대안 비교](#8-설계-대안-비교)
9. [권고 TO-BE 구조](#9-권고-to-be-구조)
10. [오류 Contract 초안](#10-오류-contract-초안)
11. [권한 설계](#11-권한-설계)
12. [테스트 전략](#12-테스트-전략)
13. [Migration Plan](#13-migration-plan)
14. [Rollback Strategy](#14-rollback-strategy)
15. [Risk Register](#15-risk-register)
16. [Decision Required](#16-decision-required)
17. [다음 Commit 제안](#17-다음-commit-제안)

---

## 1. 목적

Legacy Portal(`admin_reservations_v2_new.html`)이 전담하는 예약변경(일정변경)·예약취소·검진완료 3개 전이를, 향후 Admin Portal/FastAPI 기반으로 안전하게 전환하기 위한 Blueprint를 확정한다. 이번 Commit은 **설계만** 수행하며, Phase B의 실제 구현(B-1 이후)은 각 단계별 별도 PM 승인 이후 착수한다.

## 2. 범위 및 제외 범위

**범위**: 3개 전이의 AS-IS 분석, 상태 전이 규칙 분석(불명확한 규칙은 UNDEFINED로 명시), 영향도 분석 7개 영역, TO-BE 설계 대안 비교, 오류 Contract 초안, 권한 설계, 테스트 전략, 단계적 Migration Plan, Rollback Strategy, Risk Register, Decision Required 목록, ADR 초안.

**제외 범위**: 코드 구현, FastAPI 엔드포인트 추가, Legacy 기능 차단, Business Rule 확정(전부 Decision Required로 등록), Admin Portal 화면 변경, Google Sheets/Apps Script 코드 변경.

## 3. 근거 문서와 코드

이번 설계는 아래 파일을 실제로 열어 확인한 내용에만 근거한다(추측 없음).

- `src/api/reservation_approval_states.py`
- `src/api/routes_admin_portal.py`
- `app/pages/admin_portal_new.html`, `app/pages/admin_reservations_v2_new.html`
- `app/services/google_sheets_service_v2_new.js`
- `app/apps_script/sheets_api_v3_final.gs`(`_actionUpdateStatus`/`_actionUpdate`, `COL` 스키마)
- `data/roles.json`
- `Sprint5_Commit5_3_3_Legacy_Migration_Preparation_v1.0.md`, `Sprint6_Design_Freeze_v1.0.md`, `Sprint6_Closeout_Report_v1.0.md`, `Sprint7_Design_Freeze_v1.0.md`, `Operation_Readiness_Assessment_v1.0.md`
- `ARCHITECTURE.md`, `PROJECT_STATUS.md`, `ROADMAP.md`

---

## 4. AS-IS 흐름

3개 전이 전부 **동일한 하나의 코드 경로**를 공유한다(코드 확인).

```
Legacy Portal(admin_reservations_v2_new.html)
    ↓ 상세 모달에서 #statusSel 드롭다운 선택("일정변경"/"예약취소"/"검진완료")
    ↓
AA.saveStatus()
    ↓ statusChanged 감지, approvalBlocked 체크("예약확정"만 해당 — 이 3개 전이는 해당 없음, Commit6-1 가드 통과)
    ↓
CMC_SheetsServiceV2.updateStatus(no, newStatus)
    ↓
_liveUpdateStatus() → POST {action:'updateStatus', no, status}
    ↓
Apps Script Web App(doPost)
    ↓
sheets_api_v3_final.gs :: _actionUpdateStatus(no, status, confirmedAt)
    ↓ LockService 획득(10초 대기, 실패 시 503)
    ↓ 예약번호로 행 탐색
    ↓ COL.예약상태 셀에 status 문자열 그대로 저장(이전 상태 검증 없음 — §6 참조)
    ↓ status별 부수효과: '검진완료'→COL.검진종료에 타임스탬프. '일정변경'/'예약취소'는 부수효과 없음
    ↓
Google Sheets '종합검진_예약대장'
```

**FastAPI는 이 흐름 어디에도 관여하지 않는다.** `routes_admin_portal.py`에는 이 3개 전이에 대응하는 엔드포인트가 없다(코드 검색으로 재확인 — `approve`/`reject` 2개 엔드포인트만 존재).

---

## 5. 전이별 상세 분석

| 항목 | 예약변경(일정변경) | 예약취소 | 검진완료 |
|---|---|---|---|
| 시작 화면 | Legacy Portal 상세 모달 | Legacy Portal 상세 모달 | Legacy Portal 상세 모달 |
| 사용자 역할 | Legacy Portal 접근 가능한 누구나(코드상 화면 자체에 역할 검사 없음 — Mock 인증조차 거치지 않음, §7-⑥) | 좌동 | 좌동 |
| 실행 함수 | `AA.saveStatus()` | `AA.saveStatus()` | `AA.saveStatus()` |
| 호출 서비스 | `CMC_SheetsServiceV2.updateStatus()` | 좌동 | 좌동 |
| Apps Script 호출 | `action=updateStatus` → `_actionUpdateStatus()` | 좌동 | 좌동 |
| 변경되는 컬럼 | `COL.예약상태`뿐 — **`COL.희망검진일`/`COL.희망시간`은 변경되지 않는다**(코드 확인, §5-1 핵심 발견) | `COL.예약상태`뿐 | `COL.예약상태` + `COL.검진종료`(자동 타임스탬프) |
| 현재 상태 → 목표 상태 | 임의 상태 → "일정변경"(전이 검증 없음, §6) | 임의 상태 → "예약취소"(전이 검증 없음) | 임의 상태 → "검진완료"(전이 검증 없음) |
| 사유/메모 처리 | 전용 필드 없음 — 범용 `특이사항`(`COL.특이사항`) 필드를 별도 `action=update` 호출로 저장 가능하나 필수 아님, 사유와 일반 메모가 구조적으로 구분되지 않음 | 좌동(취소 사유 전용 필드 없음) | 좌동(완료 메모 전용 필드 없음) |
| 사용자 확인 절차 | 없음(드롭다운 선택 + "상태 저장" 버튼 클릭뿐, 확인창 없음) | 좌동 | 좌동 |
| 성공 응답 | `{ok:true, data:{...}, message:'상태 변경 완료'}` | 좌동 | 좌동 |
| 실패 응답 | `{ok:false, error:'...'}`(GAS 오류 문자열) | 좌동 | 좌동 |
| 오류 표시 방식 | Legacy 자체 `toast()`(Admin Portal의 `parseApiError()`/`showToast()`와 별개 구현) | 좌동 | 좌동 |
| 감사 추적 가능 여부 | **불가능** — `audit_logs.json`에 이 3개 전이 관련 기록 0건(코드 검색으로 재확인, Legacy/Sheets Service/GAS 어디에도 audit 관련 코드 없음) | 불가능 | 불가능 |
| 관련 권한 검사 여부 | **없음** — GAS `doPost`는 `action`만 보고 분기할 뿐 인증·인가 로직이 전혀 없다(코드 확인). Legacy Portal 화면 자체도 Mock 인증(X-User-Id)을 거치지 않는다 | 없음 | 없음 |
| 전용 테스트 존재 여부 | 없음(Commit6-1 가드 테스트에서 "무영향 확인"용으로 간접 커버된 것이 전부) | 없음(좌동) | 없음(좌동) |

### 5-1. 이번 설계에서 새로 발견한 핵심 사실

1. **"예약변경"은 현재 실제로는 날짜/시간을 변경하지 않는다.** Legacy Portal의 상세 모달에서 희망일시(`dDate`)는 `<span>`(읽기 전용 표시)이며 편집 가능한 입력 필드가 아니다(코드 확인). "일정변경" 선택 후 저장하면 상태 라벨만 "일정변경"으로 바뀔 뿐, `희망검진일`/`희망시간` 컬럼은 그대로 남는다. 다만 GAS `_actionUpdate()`(범용 필드 수정 액션)는 `wishDate`/`wishTime` 매핑을 이미 갖고 있어(코드 확인), **재사용 가능한 하위 구성요소는 이미 존재**하고 프론트엔드 UI만 없는 상태다.
2. **GAS 쓰기 액션에는 인증·인가가 전혀 없다.** `doPost()`는 `action` 문자열만으로 분기하며, `_actionUpdateStatus`/`_actionUpdate` 어디에도 호출자 신원 확인이 없다(코드 확인, `google_sheets_service_v2_new.js`의 기존 주석도 "Web App URL이 노출되면 누구나 데이터에 접근 가능"이라고 이미 명시). **Sprint6 Commit6-1의 "예약확정" 차단 가드는 브라우저 JS(`saveStatus()`)에만 존재하는 클라이언트측 가드다** — Web App URL을 알고 직접 HTTP 요청을 보내면 이 가드를 완전히 우회해 Slot/Policy 검증 없이 어떤 상태로도(예약확정 포함) 쓸 수 있다. TD-S5-04는 "일반적인 화면 조작 경로"만 부분 해소했을 뿐, 근본적인 서버측 강제는 여전히 없다.
3. **취소 시 Slot이 반환되지 않는다.** `_actionUpdateStatus()`에는 Slot 관련 코드가 전혀 없다(코드 확인). 예약확정 상태였던 예약이 Legacy를 통해 "예약취소"로 바뀌어도, 승인 시점에 `_reserve_slot_for_approval()`이 점유한 로컬 JSON Slot(`reservedCount`)은 **영구히 점유된 채로 남는다** — FastAPI의 Slot 해제 로직(`engine._release_slot()`)은 Rollback 경로에서만 호출되며 Legacy의 취소 경로와는 완전히 분리돼 있다.
4. **상태 전이 검증이 전혀 없다.** `_actionUpdateStatus()`는 이전 상태를 조회하지도 비교하지도 않고 새 상태 문자열을 그대로 저장한다(코드 확인). "검진완료"에서 "예약접수"로 되돌리는 것도 코드상 아무 제약 없이 가능하다.

---

## 6. 상태 전이 규칙

| 질문 | 답변 |
|---|---|
| 허용 가능한 이전 상태(각 전이별) | **UNDEFINED BUSINESS RULE** — 코드(`_actionUpdateStatus`)에 전이 검증이 없고, 문서(`reservation_approval_states.py`)는 "예약접수→예약확정/거절"만 정의하며 나머지는 "Legacy가 전담한다"고만 적혀 있을 뿐 구체적 규칙은 없다 |
| 허용 가능한 다음 상태 | UNDEFINED BUSINESS RULE(위와 동일 근거) |
| 중복 실행 가능성 | **가능**(IMPLEMENTATION-DEPENDENT BEHAVIOR) — 동일 상태로 재저장 시 `statusChanged = newStatus !== cached.status`가 false가 되어 프론트엔드에서는 호출 자체가 스킵되지만, GAS 자체는 동일 값 재저장을 막지 않는다(직접 호출 시) |
| 동일 상태 저장 가능성 | 위와 동일 |
| 잘못된 역방향 전이 가능성 | **가능**(코드로 확인, §5-1 항목4) — GAS/프론트 어디서도 막지 않는다 |
| 동시 수정 충돌 가능성 | LockService(10초)로 GAS 쓰기 자체는 직렬화되나, "다른 사용자가 이미 다른 상태로 바꿨다"는 낙관적 잠금(compare-and-swap)은 없다 — 마지막에 쓴 값이 그냥 덮어씀(코드 확인, `updateStatus`가 이전 값을 읽어 비교하지 않음) |
| 예약일 변경 시 Slot 영향 | **UNDEFINED** — 애초에 예약일이 실제로 변경되지 않으므로(§5-1 항목1) 현재는 해당 없음. Phase B에서 실제 재배정 기능을 만들 경우 Slot 재배정 규칙 자체를 새로 설계해야 함 |
| 취소 시 Slot 반환 여부 | **현재 미반환**(코드로 확인, §5-1 항목3) — Phase B 최우선 결함 |
| 검진완료 후 재변경 가능성 | **가능**(코드상 막을 방법 없음, §5-1 항목4) — 운영상 바람직한지는 Decision Required(§16) |
| 메모/취소 사유 필수 여부 | **UNDEFINED** — 현재 Legacy UI에서 사유 입력은 선택(옵션)이며 필수 검증 없음 |
| 운영자 권한 요구사항 | **없음**(코드로 확인, §5-1 항목2) — `roles.json`에 `reservation:change`/`reservation:cancel` 권한 문자열은 정의돼 있으나(ROLE-STAFF) 이 3개 전이 중 어느 것도 이 권한을 검사하지 않는다. "검진완료" 전용 권한 문자열은 애초에 존재하지 않는다 |

**의사결정 필요사항으로 등록**: 위 UNDEFINED 항목 전부 §16에서 별도 목록으로 재정리한다.

---

## 7. 영향도 분석

### ① Admin Portal
- 화면 확장 필요 — 현재 승인/거절 2개 버튼만 존재(`예약접수` 상태에서만 노출). 3개 전이를 추가하려면 상태별로 다른 버튼 세트가 필요(예: `예약확정` 상태에서 "취소"/"검진완료" 버튼, 날짜 임박 시 "일정변경" 버튼 등) — 상태별 버튼 활성화 로직 신설 필요
- 확인창: 현재 승인/거절 모두 확인창 없이 즉시 실행(거절만 사유 입력 Dialog 존재) — 취소·완료는 되돌리기 어려운 동작이므로 확인창 필요성 검토 대상(Decision Required)
- 사유 입력: 거절 Dialog(`rejectModal`) 패턴 재사용 가능(취소 사유 등에 동일 UI 재사용 가능, 신규 컴포넌트 불필요)
- 결과 메시지: 기존 `showToast()`/`parseApiError()` 그대로 재사용 가능

### ② FastAPI
- 신규 Endpoint 필요 여부: **필요**(현재 대응 엔드포인트 없음, §4)
- 기존 승인/거절 Endpoint 확장 가능 여부: 부분 가능 — `_process_reservation_approval()`의 구조(read→validate→write→audit)는 재사용 가능한 패턴이나, `reservation_approval_states.py::SHEETS_APPROVAL_TRANSITIONS`가 "예약접수" 시작 상태 하나만 다루므로 확장이 필요
- 별도 Transition Service 필요 여부: §8에서 대안별로 비교
- Policy Layer/Execution Layer 분리: Sprint4 Commit5-2A에서 확립된 원칙(validate_slot()=Policy, 기존 상태/Capacity 검사=Execution) 재사용 가능 — 단, 취소/완료는 애초에 Slot 점유를 새로 만드는 것이 아니라 기존 점유를 해제/확정하는 것이라 Policy Layer 적용 범위가 승인 때와 다름
- 오류 Contract: §10에서 설계
- 감사 로그: `reservation_audit.py::append_audit()` 기존 함수 그대로 재사용 가능(신규 감사 시스템 불필요)

### ③ Legacy Portal
- Phase B 전환 기간 중 유지 기능: 조회/CSV 다운로드/메모 편집(위험 없음, §5-1에서 감사 대상 아니었던 것과 동일 이유로 계속 유지 가능) — 3개 전이 자체는 대체 경로 검증 전까지 그대로 유지(핵심 원칙 2)
- 단계별 Read-only 전환 가능성: 가능 — Commit6-1의 `approvalBlocked` 패턴을 다른 전이에도 동일하게 적용 가능(코드 구조상 재사용 용이)
- 우회 경로 차단 시점: §13 Migration Plan에서 단계별 정의
- 롤백 시 복구 방법: §14에서 상세

### ④ Google Sheets
- 기존 컬럼 재사용 가능 여부: **대부분 가능** — `예약상태`/`검진종료`(완료)/`희망검진일`·`희망시간`(변경, `_actionUpdate`로 이미 지원)/`특이사항`(사유, 범용 재사용) 전부 기존 컬럼으로 충분
- 추가 컬럼 필요 여부: **취소일시 전용 컬럼 없음**(현재 `예약확정일`처럼 "취소일시"를 자동 기록하는 컬럼이 없음) — 신규 컬럼 여부는 Decision Required
- 상태값 표준화: 현재 상태 문자열이 6종(예약접수/예약확정/검진완료/일정변경/예약취소/거절)으로 이미 고정되어 있고 변경 계획 없음(Business Rule 변경 금지 원칙 준수)
- 변경 이력 저장 방식: 없음(현재 상태값 덮어쓰기만, 이전 값 보존 안 됨) — Google Sheets 자체의 버전 기록(파일 히스토리)에 암묵적으로 의존 중
- 개인정보 영향: 없음(기존 컬럼 재사용만 검토, 신규 PII 컬럼 없음)

### ⑤ Apps Script
- 기존 `updateStatus` 재사용 가능 여부: **가능**(신규 action 불필요, 기존 액션 그대로 FastAPI가 대리 호출하면 됨 — Sprint4 Commit2가 이미 이 패턴을 확립함, `sheets_write_service.py`)
- FastAPI 경유 시 변경 필요 여부: GAS 코드 자체는 무수정 가능(FastAPI가 기존 `action=updateStatus`/`update`를 그대로 호출) — **단, 인증/인가는 여전히 GAS 쪽에는 없으므로, "FastAPI를 경유하지 않고 GAS를 직접 호출하는" 우회는 Phase B 이후에도 구조적으로 남는다**(§5-1 항목2, Risk Register에 등록)
- 동시성/원자성 위험: LockService로 단일 쓰기는 보호되나, "Slot 해제 + Sheets 쓰기"처럼 여러 단계가 필요한 취소 처리는 Sprint4 Commit3의 Rollback 패턴(Slot 점유→Sheets 쓰기, 실패 시 Slot 롤백)을 참고해 순서를 설계해야 함

### ⑥ 권한
- `reservation:change`/`reservation:cancel`: `roles.json`에 이미 정의(ROLE-STAFF) — **재사용 가능, 새 권한 문자열 불필요**
- `completion` 관련 권한: **존재하지 않음** — "검진완료"는 어떤 권한 문자열도 정의된 바 없음, 신규 권한 필요 여부는 Decision Required
- 실제 Enforcement 여부: 현재 0%(§5-1 항목2) — Phase B가 FastAPI 경유로 전환되면 기존 `_build_require_permission()` 패턴 재사용으로 즉시 Enforcement 가능
- 권한 추가 필요 여부: "검진완료" 권한만 신규 검토 대상, 나머지는 기존 재사용

### ⑦ 테스트
- Unit: `reservation_approval_states.py` 확장 시 상태기계 단위 테스트 필요(기존 Commit2 패턴 재사용)
- Integration: TestClient 기반 API 통합 테스트(기존 Commit2/3/3A/5-2 패턴 그대로 재사용 가능)
- Contract: `parseApiError()`가 신규 오류 코드를 올바르게 파싱하는지(Commit5-3.1 패턴 재사용)
- Browser QA: Admin Portal에 신규 버튼 추가 시 실제 QA 필요(Commit5-3.2 패턴 재사용) — 단 실제 운영 GAS URL 노출 문제(Commit6-1에서 이미 확인)로 오프라인 vm 시뮬레이션 방식 유지 권장
- Regression: 기존 6개 Backend 스위트 + Legacy Guard 스위트 전부 재실행 필요

---

## 8. 설계 대안 비교

### Option A — 기존 Admin 승인 API 패턴 확장(전이별 개별 Endpoint)

`POST /api/admin/reservations/{no}/change`, `/cancel`, `/complete` 3개 신규 엔드포인트를 approve/reject와 동일 패턴으로 추가.

| 기준 | 평가 |
|---|---|
| 장점 | 기존 코드(`_process_reservation_approval` 패턴) 그대로 복제 재사용 가능, 각 전이별 오류 코드·권한을 독립적으로 명확히 관리 가능 |
| 단점 | 엔드포인트 3개 추가로 `routes_admin_portal.py`가 커짐, 전이별 로직 중복 위험(공통 부분을 별도 함수로 추출해야 함) |
| 구현 난이도 | 낮음(기존 패턴 복제) |
| 회귀 위험 | 낮음(기존 approve/reject 코드를 건드리지 않고 옆에 추가) |
| 운영 적합성 | 높음(각 전이의 의미가 URL에 명확히 드러남) |
| 감사 가능성 | 높음(전이별로 별도 이벤트명 부여 용이 — RESERVATION_CHANGED/CANCELLED/COMPLETED) |
| 권한 적용 | 용이(엔드포인트별로 다른 권한 요구 가능) |
| 롤백 용이성 | 높음(엔드포인트 단위로 개별 비활성화 가능) |
| 향후 확장성 | 보통(전이 추가마다 엔드포인트 추가 필요) |

### Option B — 단일 Reservation Transition Endpoint

`POST /api/admin/reservations/{no}/transition` 하나로 `target_status`를 body로 받아 공통 처리.

| 기준 | 평가 |
|---|---|
| 장점 | 엔드포인트 1개로 통합, 신규 전이 추가 시 코드 재작성 최소화(설정/매핑만 추가) |
| 단점 | 전이별로 요구 권한·오류 코드·Policy가 다른데 단일 엔드포인트 안에서 분기 로직이 복잡해짐, URL만 봐서는 무슨 동작인지 불명확 |
| 구현 난이도 | 중간(범용 분기 로직 설계 필요) |
| 회귀 위험 | 중간(기존 approve/reject를 이 엔드포인트로 통합할지 여부에 따라 회귀 범위 달라짐 — 통합 시 위험 커짐) |
| 운영 적합성 | 낮음(로그·모니터링에서 어떤 전이인지 파라미터를 봐야 알 수 있음) |
| 감사 가능성 | 보통(단일 엔드포인트 안에서 target_status로 이벤트 구분 필요) |
| 권한 적용 | 복잡(엔드포인트 진입 후 target_status별로 다시 권한 분기해야 함) |
| 롤백 용이성 | 낮음(엔드포인트 하나에 여러 기능이 묶여 있어 부분 롤백 어려움) |
| 향후 확장성 | 높음(신규 전이는 매핑 테이블만 추가) |

### Option C — Legacy 화면만 Admin Portal로 이동(GAS 직접 호출 유지)

Admin Portal 안에 Legacy와 동일한 상태 드롭다운 UI를 추가하되, 백엔드는 계속 GAS를 직접 호출(FastAPI 미경유).

| 기준 | 평가 |
|---|---|
| 장점 | Backend/FastAPI 구조 변경 없음(Sprint7 원칙 9와 가장 잘 맞음), 구현 최소 |
| 단점 | **핵심 문제(§5-1 항목2 — GAS 자체에 인증/인가 없음, Slot 미반환)를 전혀 해결하지 못함** — 화면 위치만 옮길 뿐 우회 경로·감사 불가 문제가 그대로 남음 |
| 구현 난이도 | 낮음(UI 이식만) |
| 회귀 위험 | 낮음 |
| 운영 적합성 | 낮음(근본 문제 미해결) |
| 감사 가능성 | 여전히 불가(GAS 직접 호출은 감사 로그를 남기지 않음) |
| 권한 적용 | Admin Portal 진입 자체는 RBAC로 보호 가능하나, 실제 쓰기는 여전히 GAS 직접 호출이라 세밀한 전이별 권한 적용 불가 |
| 롤백 용이성 | 높음 |
| 향후 확장성 | 낮음(근본 구조가 그대로라 향후에도 같은 문제 반복) |

### 최종 권고안: **Option A(전이별 개별 Endpoint) 채택 권고**

**근거**: §5-1에서 발견한 핵심 문제(GAS 자체의 인증/인가 부재, Slot 미반환, 감사 불가)는 FastAPI를 경유해야만 해결된다 — Option C는 이 문제를 해결하지 못하므로 제외. Option B와 Option A 중에서는, 3개 전이가 서로 다른 권한·Policy·부수효과(취소는 Slot 반환, 완료는 타임스탬프, 변경은 재배정)를 가지므로 **단일 엔드포인트로 억지로 묶으면 오히려 Sprint4 Commit5-2A에서 확립한 "Policy Layer/Execution Layer 분리" 원칙과 "Business Rule을 Portal에 넣지 않는다"는 원칙을 지키기 어려워진다.** Option A는 기존 approve/reject 패턴을 그대로 복제하는 것이라 **재사용 원칙에도 가장 부합**하고, 롤백도 전이 단위로 독립적으로 가능해 §14 Rollback Strategy와도 가장 잘 맞는다. 최종 결정은 PM 승인 필요(이 문서는 권고까지만).

---

## 9. 권고 TO-BE 구조

```
Admin Portal(신규 버튼: 취소/완료/변경 — 상태별 노출)
    ↓
FastAPI (POST /api/admin/reservations/{no}/cancel | /complete | /change)
    ↓
Transition Validation(reservation_approval_states.py 확장 — 전이별 허용 상태 정의)
    ↓
Authorization(_build_require_permission() 재사용 — reservation:cancel/change, completion은 신규 권한 검토)
    ↓
Execution
    ├─ 취소: engine._release_slot() 재사용(Slot 반환, §5-1 항목3 해결)
    ├─ 완료: Slot 변경 없음(단순 상태 전이 + 타임스탬프)
    └─ 변경: Slot 재배정 로직 신규 설계 필요(Decision Required, §16)
    ↓
sheets_write_service.py 확장(기존 updateStatus/update action 재사용, GAS 무수정)
    ↓
Audit(reservation_audit.py::append_audit() 재사용 — RESERVATION_CANCELLED/COMPLETED/CHANGED 신규 이벤트명만 추가)
    ↓
Normalized Response({code, message} 형식, 기존 계약 재사용)
    ↓
Portal Error Contract(parseApiError() — 신규 코드만 §10 기준으로 추가 인식)
```

이 구조는 기존 승인/거절 파이프라인(Sprint4 Commit2~5-2)의 구조를 그대로 복제하며, 신규 Layer·신규 Repository·신규 Policy Engine을 만들지 않는다(핵심 원칙 준수).

---

## 10. 오류 Contract 초안

기존 `parseApiError()`(Commit5-3.1) 및 `{code, message}` 계약을 그대로 따른다. 아래는 **설계안 제안**이며 최종 코드 문자열·HTTP Status는 PM 확정 필요(Business Rule 확정 금지 원칙에 따라 이 문서는 제안만 한다).

| 후보 코드 | HTTP Status(안) | 발생 조건(안) | 사용자 표시 메시지(안) | 재시도 가능 여부 | 운영자 조치 |
|---|---|---|---|---|---|
| `RESERVATION_TRANSITION_NOT_ALLOWED` | 409 | 현재 상태에서 허용되지 않는 전이 시도(예: 이미 취소된 예약을 다시 취소) — 기존 `INVALID_STATUS_TRANSITION`/`RESERVATION_CHANGE_NOT_ALLOWED`/`RESERVATION_CANCEL_NOT_ALLOWED`를 하나로 통합 제안(§6에서 전이 규칙 자체가 UNDEFINED이므로 세분화된 코드를 지금 확정하는 것은 시기상조) | "현재 상태에서는 이 작업을 할 수 없습니다." | 아니오 | 예약 상태 재확인 |
| `RESERVATION_ALREADY_COMPLETED` | 409 | 이미 검진완료 상태인 예약에 재요청 | "이미 검진이 완료된 예약입니다." | 아니오 | — |
| `RESERVATION_ALREADY_CANCELLED` | 409 | 이미 취소된 예약에 재요청 | "이미 취소된 예약입니다." | 아니오 | — |
| `RESERVATION_TRANSITION_CONFLICT` | 409 | 동시 수정 충돌(다른 사용자가 먼저 처리) — 기존 승인 409(A형, 문자열)와 동일 성격, 코드화 필요 여부는 Decision Required | "다른 사용자가 이미 처리했습니다." | 예(재조회 후 재시도) | — |
| `RESERVATION_REASON_REQUIRED` | 422 | 취소 사유 필수화 결정 시(§16 Decision Required) | "취소 사유를 입력해 주세요." | 예 | — |
| `SLOT_REASSIGNMENT_FAILED` | 500 | 일정변경 시 신규 Slot 재배정 실패 | "일정 변경 처리 중 오류가 발생했습니다. 관리자에게 문의해 주세요." | 예 | Slot 데이터 직접 확인(Commit3A의 `SLOT_ROLLBACK_FAILED` 패턴과 유사) |
| `RESERVATION_TRANSITION_FAILED` | 500 | 그 외 예외(범용 Fallback, Commit5-2의 `SLOT_POLICY_VALIDATION_FAILED` 패턴과 동일 철학) | "처리 중 오류가 발생했습니다. 관리자에게 문의해 주세요." | 예 | 서버 로그 확인 |

`reason_category`/`reason_detail`은 Commit5-3.1에서 이미 설계된 필드를 그대로 사용(값 목록은 이 설계에서 확정하지 않음 — Decision Required).

---

## 11. 권한 설계

| 전이 | 권한 문자열(안) | 근거 |
|---|---|---|
| 예약변경 | `reservation:change`(기존 재사용) | `roles.json` ROLE-STAFF에 이미 정의, 신규 문자열 불필요 |
| 예약취소 | `reservation:cancel`(기존 재사용) | 좌동 |
| 검진완료 | **신규 검토 필요**(예: `reservation:complete`) | 현재 어떤 권한 문자열도 존재하지 않음(§7-⑥) — 기존 `reservation:approve`를 재사용할지, 신규를 만들지는 Decision Required |

새 권한 모델(역할 구조 자체 변경)은 제안하지 않는다 — 기존 `roles.json`/`_build_require_permission()` 패턴 재사용을 전제로 한다.

---

## 12. 테스트 전략

- **Unit**: `reservation_approval_states.py` 확장분(신규 전이 규칙)에 대한 순수 함수 단위 테스트 — 기존 `assert_can_transition()` 테스트 패턴 재사용
- **Integration**: TestClient + 샌드박스 + Sheets/Slot monkeypatch(Commit2/3/3A/5-2 패턴 그대로 재사용) — 성공/실패/권한없음/전이불가 케이스
- **Contract**: `parseApiError()`가 §10의 신규 코드를 올바르게 파싱하는지(Commit5-3.1의 Node vm 오프라인 테스트 패턴 재사용)
- **Browser QA**: Admin Portal 신규 버튼의 실제 클릭 흐름 — 단, 운영 GAS URL이 Legacy Portal에 하드코딩되어 있던 것과 달리 Admin Portal은 `?api=` 파라미터로 안전하게 격리 가능(Commit5-3.2에서 이미 사용한 방식) 하므로 실브라우저 QA 가능
- **Regression**: 기존 Backend 6개 스위트 + Legacy Guard(Commit6-1) + TD Cleanup(Commit6-2) 스위트 전부 재실행 — 이 설계가 실제 구현되기 전까지는 코드 변경이 없으므로 이번 Commit에서는 실행하지 않고(§테스트 및 검증 원칙), Phase B-1 구현 시점에 정식 재실행

---

## 13. Migration Plan

| Phase | 목표 | 변경 대상 | 선행조건 | 테스트 | 운영 검증 | 롤백 조건 | PM Gate | Push/Deploy Gate |
|---|---|---|---|---|---|---|---|---|
| **B-0** | 설계 확정 | 문서만(본 문서 + ADR-016) | 없음 | 없음 | 없음 | 해당 없음 | **이번 Commit** | Push/Deploy 없음 |
| **B-1** | 공통 Transition Contract·검증 계층 구현 | `reservation_approval_states.py` 확장(전이 규칙 정의), `sheets_write_service.py` 확장(재사용) | §16 Decision Required 전이 규칙 확정 | Unit+Integration | 없음(아직 UI 연결 전) | Git revert만으로 충분(신규 코드 추가뿐, 기존 코드 무수정 예상) | 별도 Commit 승인 | 금지 |
| **B-2** | 예약취소 전환 | FastAPI `/cancel` 엔드포인트, Slot 반환 로직(§5-1 항목3 해결) | B-1 완료 | Integration+Contract | 실 운영 데이터로 별도 검증 없이 사후 모니터링 | Endpoint 비활성화(Legacy 취소 재활성화) | 별도 Commit 승인 | 금지 |
| **B-3** | 예약변경 전환 | FastAPI `/change` 엔드포인트, Slot 재배정 로직(신규 설계 필요) | B-2 안정화, Slot 재배정 규칙 확정(§16) | Integration+Contract | 좌동 | 좌동 | 별도 Commit 승인 | 금지 |
| **B-4** | 검진완료 전환 | FastAPI `/complete` 엔드포인트 | B-3 안정화, 완료 권한 확정(§16) | Integration+Contract | 좌동 | 좌동 | 별도 Commit 승인 | 금지 |
| **B-5** | Legacy 쓰기 차단 | `admin_reservations_v2_new.html`의 3개 전이 write 경로 차단(Commit6-1 패턴 재사용) | B-2~B-4 전부 운영 안정화 확인 | Legacy Guard 확장 테스트 | 최소 1~2주 병행 운영 후 결정(Decision Required) | Legacy 쓰기 재활성화(client-side 가드 제거) | 별도 Commit 승인 | 금지 |
| **B-6** | 운영 안정화 후 제거 검토 | Legacy 파일 자체 제거 여부 검토(Migration Preparation Stage 4와 동일 성격) | 실제 접근 로그로 미사용 확인 | 없음(제거 여부 판단용 관찰 기간) | 장기 모니터링 | 파일 보존 상태 유지로 언제든 복구 가능 | 별도 Commit 승인, **가장 신중하게 접근** | 금지 |

각 Phase는 **개별 PM 승인 후에만 착수**하며, 이번 Commit7-3은 B-0(설계)만 완료한다.

---

## 14. Rollback Strategy

| 항목 | 분석 |
|---|---|
| 기능 플래그 가능 여부 | 가능 — B-2~B-4는 FastAPI 엔드포인트 추가이므로 라우터 자체를 비활성화하거나 Admin Portal 버튼을 숨기는 방식으로 즉시 롤백 가능(신규 엔드포인트이므로 기존 기능 삭제 없이 "끄기"만 하면 됨) |
| Admin 버튼 비활성화 | B-2~B-4 각각의 Admin Portal 버튼을 개별적으로 숨길 수 있음(Commit6-1 패턴처럼 클라이언트 조건 분기로 간단히 처리 가능) |
| Legacy 쓰기 재활성화 | B-5(Legacy 차단) 롤백 시, Commit6-1과 동일한 방식으로 클라이언트측 가드만 제거하면 즉시 복구(Sheets/GAS 쪽은 원래 무제한이었으므로 되돌릴 것도 없음) |
| 데이터 정합성 확인 | **B-2(취소, Slot 반환) 롤백 시 주의 필요** — 이미 반환된 Slot을 다시 점유해야 하는데, 그 사이 다른 예약이 그 Slot을 점유했을 수 있음(경쟁 상태). 롤백 절차에 "Slot 재점유 실패 시 수동 확인" 단계 필수 |
| 중복 처리 방지 | FastAPI 경유 시 Audit 로그로 "언제 어떤 경로로 처리됐는지" 구분 가능(감사 가능성 확보가 Phase B의 핵심 이점이기도 함) — Legacy로 롤백한 이후에는 다시 감사 불가 상태로 돌아간다는 점을 운영자에게 명확히 공지해야 함 |
| Rollback 전후 상태 비교 | Sheets 자체 버전 기록(암묵적 백업)과 `audit_logs.json`을 대조해 확인 가능 — 단, 전용 도구는 없음(신규 필요 시 별도 Commit) |
| 운영 공지 | 각 Phase 전환/롤백 시 운영자(간호사·행정 담당) 대상 공지 필요 — 상세 절차는 Commit7-4(운영 매뉴얼) 범위 |
| 감사 기록 보존 | 롤백해도 이미 생성된 Audit 로그는 append-only라 삭제되지 않음(기존 설계 원칙 유지) |

**⚠️ High Risk로 표시**: B-2(취소) 롤백 시 Slot 경쟁 상태로 인한 이중 점유/데이터 불일치 가능성 — Phase B-2 구현 설계 단계에서 반드시 재검토 필요.

---

## 15. Risk Register

| # | 위험 | 위험도 | 발생 가능성 | 영향 | 탐지 방법 | 예방 조치 | 대응 조치 | 잔여 위험 |
|---|---|---|---|---|---|---|---|---|
| 1 | Legacy 우회 경로 잔존(GAS 직접 호출, 인증 없음) | **Critical** | 중(URL 유출 시) | Slot/Policy 전체 우회, 감사 불가 | 없음(현재 탐지 수단 자체가 없음) | Web App 배포 시 "액세스 권한" 조직 내 한정(운영 조치, 코드 아님) | 침해 발생 시 GAS 재배포로 URL 변경 | Phase B 완료 후에도 GAS 자체 인증 부재는 구조적으로 남음(별도 과제) |
| 2 | 잘못된 상태 전이(역방향 등) | High | 중(현재 검증 없음) | 데이터 정합성 훼손 | 없음(현재) | Phase B-1에서 전이 규칙 정의 | 수동 데이터 정정 | B-1 이후 크게 감소 예상(단, 실측은 구현 후) |
| 3 | 취소 후 Slot 미반환 | **Critical** | 높음(모든 취소에서 발생, 코드로 확인된 현재 동작) | Slot 정원 왜곡 누적 | 없음(현재) | Phase B-2 최우선 처리 | 수동 Slot 데이터 정정(스크립트 필요, 이번 설계 범위 아님) | B-2 완료 전까지 계속 발생 |
| 4 | 변경 시 이중 예약 | Medium | 낮음(현재 실제 날짜변경 기능이 없어 발생 자체가 구조적으로 불가능, §5-1 항목1) | Slot 이중 점유 | 해당 없음(현재) | B-3 설계 시 Slot 재배정을 원자적 트랜잭션으로 설계 | — | B-3 구현 전까지는 위험 자체가 존재하지 않음(기능 부재) |
| 5 | 완료 후 상태 복원(역행) | Medium | 낮음(운영상 드묾) | 통계·감사 데이터 혼란 | 없음(현재) | Decision Required(§16)로 허용 여부 결정 | 수동 확인 | 정책 결정 후 재평가 |
| 6 | 권한 우회 | High | 높음(현재 권한 검사 자체가 없음, 코드로 확인) | 미승인 사용자의 상태 변경 | 없음(현재) | B-1~B-4에서 `_build_require_permission()` 적용 | — | Phase B 완료 시 크게 감소 |
| 7 | 동시 수정 충돌 | Medium | 낮음(LockService로 완화되나 CAS 없음) | 마지막 쓰기가 이전 변경을 덮어씀 | 없음(현재) | B-1에서 read-validate-write 패턴 도입(Commit2와 동일) | — | 완전 제거는 어려움(Sheets API의 근본 한계, Sprint4 Commit2 설계 문서에서 이미 인정된 사항) |
| 8 | 감사 로그 부재 | High | 확정적(현재 100% 없음, 코드로 확인) | 사후 추적 불가 | 없음(현재) | Phase B 전환으로 자동 해결 | — | Legacy 경로가 남아있는 한(B-5 전까지) 그 경로의 처리는 계속 감사 불가 |
| 9 | 운영자 혼선(Admin/Legacy 두 화면 병행) | Medium | 중간(B-1~B-4 기간 중 두 경로 공존) | 어느 화면에서 처리해야 하는지 혼란 | 운영자 문의 빈도로 간접 탐지 | Phase 전환마다 명확한 운영 공지(Commit7-4 매뉴얼 연계) | — | B-5 이전까지 구조적으로 존재 |
| 10 | Rollback 중 데이터 불일치 | High | 낮음(Rollback이 자주 발생하지 않기를 기대) | Slot 경쟁 상태(§14) | 수동 대조만 가능(전용 도구 없음) | §14 절차 수립 | 수동 확인·정정 | B-2 Rollback 절차 구현 전까지 상존 |

---

## 16. Decision Required

| # | 항목 | 의사결정 주체 | 결정 필요 시점 | 미결정 시 영향 | 임시 기본값 사용 가능 여부 |
|---|---|---|---|---|---|
| 1 | 예약변경 허용 시점(검진일 며칠 전까지 등) | PM/병원 운영팀 | B-3 착수 전 | B-3 설계 불가(Slot 재배정 조건 자체를 정의할 수 없음) | **불가**(승인 없이 임시값 확정 금지, 핵심 원칙) |
| 2 | 예약변경 가능 횟수 제한 여부 | PM/병원 운영팀 | B-3 착수 전 | 좌동 | 불가 |
| 3 | 당일 변경 허용 여부 | PM/병원 운영팀 | B-3 착수 전 | 좌동 | 불가 |
| 4 | 취소 사유 필수 여부 | PM | B-2 착수 전 | `RESERVATION_REASON_REQUIRED`(§10) 코드 실사용 여부 미정 | 불가 |
| 5 | 검진완료 취소/복원 가능 여부 | PM/병원 운영팀 | B-4 착수 전 | Risk #5 대응 방향 미정 | 불가 |
| 6 | 완료 처리 권한(신규 `reservation:complete` 신설 여부) | PM | B-4 착수 전 | §11 권한 설계 확정 불가 | 불가 |
| 7 | Slot 반환/재배정 규칙(취소 시 즉시 반환 vs 유예, 변경 시 재배정 알고리즘) | PM/병원 운영팀 | B-2(반환)/B-3(재배정) 착수 전 | Risk #3/#4 대응 설계 불가 | 불가 |
| 8 | 변경 이력 보존 기간 | PM/병원 개인정보보호 책임자 | B-1 착수 전(Sheets 컬럼 설계에 영향) | §7-④ "신규 컬럼 필요 여부" 확정 불가 | 불가 |
| 9 | 감사 로그 저장 위치(기존 `audit_logs.json` 재사용 vs 별도) | PM | B-1 착수 전 | §9 TO-BE 구조의 Audit 단계 확정 불가 | **재사용을 기본 제안으로 명시하나, 확정은 PM 승인 필요**(재사용 원칙상 재사용이 합리적이라는 "제안"이지 "확정"은 아님) |
| 10 | 운영자 실인증 방식 | PM/병원 전산 담당 | Sprint7 범위 밖(별도 Sprint) | Risk #1/#6이 근본적으로 남음 | 불가(Sprint7 원칙상 이번 Sprint에서 다루지 않음) |

**임시 기본값은 어느 것도 이번 문서에서 확정하지 않았다**(핵심 원칙 준수).

---

## 17. 다음 Commit 제안

- **Commit7-4**(계획대로 진행 권장): 운영 매뉴얼 갱신 시 이번 설계에서 발견한 Legacy 3개 전이의 무감사·무인증 상태(§5-1)를 "알려진 운영 리스크"로 반드시 명시.
- **Phase B-1 착수는 별도 Commit**으로, §16 Decision Required 중 최소 항목8·9(Sheets 컬럼/감사 위치)가 결정된 이후 제안한다 — 이번 Commit7-3에서는 착수하지 않는다.
- ADR-016(본 설계와 함께 작성)의 Open Decisions를 PM이 검토해 우선순위를 정한 뒤 다음 단계를 진행할 것을 권고한다.

---

## 완료 조건 준수 확인

이 문서 작성 중 어떤 코드 파일도 수정하지 않았다(Read/Grep만 수행). API 추가 없음, Legacy 기능 차단 없음, Business Rule 확정 없음(전부 Decision Required로 등록). Commit(문서 커밋 제외)/Push/Deploy 없음.
