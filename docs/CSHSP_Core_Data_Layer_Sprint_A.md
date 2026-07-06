# CSHSP Core Data Layer — Sprint A 산출 문서

> **프로젝트:** Cheonan Medical Center AI Health Screening Concierge Platform (CSHSP)
> **Sprint:** A — Core Data Layer 재정비 및 실제 운영 기반 구축
> **작성일:** 2026-07-02
> **위치:** `99_임시보관_정리대기/CMC_Platform_new/`

---

## 1. Sprint 목적

기존 CMC Platform(Phase 1~Sprint 2, 예약 UI + Google Sheets 연동 + Dashboard v3)의 구조를 보존하면서,
AI 예약비서·Reservation Engine·KPI Engine·병원장 Dashboard로 확장 가능한 **20개 Entity 기반 Core Data Layer**를 구축한다.

- 모든 데이터는 JSON 우선 설계 (향후 DB/REST API 이관 가능 구조)
- 예약은 AI가 임의 생성하지 않고 반드시 Reservation Engine을 통과 (권한 모델에 반영)
- 의료 판단·진단·처방·결과 해석 기능 제외 (Questionnaire는 응답 수집만)
- 직원 승인(PENDING_APPROVAL), 감사로그(append-only), 권한관리(Role) 전제

## 2. 현재 구조 분석 결과

| 항목 | 분석 결과 |
|------|----------|
| 프로젝트 위치 | `99_임시보관_정리대기/CMC_Platform_new` (Phase 1~Sprint 2 완료) |
| data 폴더 | 루트 `data/` **없음** → 신규 생성. `app/data/`에는 JS 상수(programs_data_new.js)와 샘플 생성기만 존재 |
| reservation.json | 없음 (별도 구프로젝트 `종합검진홈페이지_v2_new`에만 존재, 미연동) |
| business.json / statistics.json | 없음 (동일하게 구프로젝트에만 존재) |
| KPI/Dashboard | `dashboard_service_v2_new.js` (KPI 6종, 검사실 8종, AI 추천 규칙) — localStorage 기반 |
| 예약 코드 | `reservation_v2_new.html` + `sheets_api_v3_final.gs` (Apps Script + Sheets 연동) |
| 상태값 | 한글 5종(예약접수/예약확정/검진완료/일정변경/예약취소)만 존재 → 표준화 대상 |
| backend/src | 없음 → `src/core/` 신규 생성 |
| 문서 | README v1~v5, DEV-003 설계문서, STEP0-1/1.5 QA 문서 존재 (모두 보존) |

**기존 파일 삭제·수정 없음. 전부 신규 추가만 수행.**

## 3. 생성/수정 파일 목록

### 신규 생성 (26개)

| 구분 | 파일 |
|------|------|
| 데이터 (20) | `data/patients.json`, `data/reservations.json`, `data/programs.json`, `data/optional_tests.json`, `data/businesses.json`, `data/doctors.json`, `data/nurses.json`, `data/equipment.json`, `data/rooms.json`, `data/schedules.json`, `data/slots.json`, `data/consents.json`, `data/questionnaires.json`, `data/crm.json`, `data/dashboard.json`, `data/statistics.json`, `data/audit_logs.json`, `data/users.json`, `data/roles.json`, `data/notifications.json` |
| 코어 (2) | `src/core/core_data_loader.py`, `src/core/data_validator.py` |
| 테스트 (2) | `tests/run_sprint_a_tests.py`, `tests/sprint_a_test_result.csv` |
| 문서 (1) | `docs/CSHSP_Core_Data_Layer_Sprint_A.md` (본 문서) |

기존 파일 수정: **없음**

## 4. Entity 목록 (20개)

| # | Entity | 파일 | PII | Dashboard 집계 | 샘플 |
|---|--------|------|-----|:---:|:---:|
| 1 | Patient | patients.json | ✅ | ✅ | 4건 |
| 2 | Reservation | reservations.json | ✅ | ✅ | 5건 |
| 3 | Program | programs.json | — | ✅ | 6건 |
| 4 | OptionalTest | optional_tests.json | — | ✅ | 6건 |
| 5 | Business | businesses.json | ✅ | ✅ | 3건 |
| 6 | Doctor | doctors.json | ✅ | ✅ | 3건 |
| 7 | Nurse | nurses.json | ✅ | ✅ | 3건 |
| 8 | Equipment | equipment.json | — | ✅ | 4건 |
| 9 | Room | rooms.json | — | ✅ | 8건 |
| 10 | Schedule | schedules.json | — | ✅ | 4건 |
| 11 | Slot | slots.json | — | ✅ | 6건 |
| 12 | Consent | consents.json | ✅ | — | 4건 |
| 13 | Questionnaire | questionnaires.json | ✅ | — | 2건 |
| 14 | CRM | crm.json | ✅ | ✅ | 3건 |
| 15 | Dashboard | dashboard.json | — | ✅ | 2건 |
| 16 | Statistics | statistics.json | — | ✅ | 2건 |
| 17 | AuditLog | audit_logs.json | ✅ | ✅ | 3건 |
| 18 | User | users.json | ✅ | — | 4건 |
| 19 | Role | roles.json | — | — | 5건 |
| 20 | Notification | notifications.json | ✅ | ✅ | 3건 |

모든 샘플은 QA 더미 데이터이며 실제 개인정보를 포함하지 않는다.

## 5. 주요 JSON 구조

### 공통 파일 래퍼 (전 Entity 동일)

```json
{
  "entity": "Reservation",
  "schemaVersion": "1.0.0",
  "generatedAt": "ISO 8601",
  "meta": { "containsPII": true, "dashboardAggregatable": true, "...": "표준/정책 메타" },
  "records": [ ... ]
}
```

### 공통 레코드 필드

`id`(Entity별 접두어: PT/RSV/PRG/OPT/BIZ/DOC/NUR/EQP/ROOM/SCH/SLOT/CST/QST/CRM/DSH/STA/AUD/USR/ROLE/NTF),
`status`, `createdAt`, `updatedAt` (ISO 8601, KST +09:00)

### Reservation (핵심)

```json
{
  "id": "RSV-20260702-0001",
  "patientId": "PT-2026-0001",
  "programId": "PRG-SMART",
  "businessId": "BIZ-0001",
  "reservationDate": "2026-07-08",
  "slotId": "SLOT-20260708-0900-A",
  "status": "CONFIRMED",
  "optionalTestIds": ["OPT-0002"],
  "sleepEndoscopy": true,
  "channel": "WEB | PHONE | VISIT | AI_ASSISTANT",
  "approvedBy": "USR-0002", "approvedAt": "...",
  "changeHistory": [{ "changedAt", "changedBy", "field", "before", "after", "reason" }],
  "createdAt": "...", "updatedAt": "..."
}
```

### Slot (Reservation Engine 전담 관리)

```json
{
  "id": "SLOT-20260708-0900-A",
  "date": "2026-07-08", "time": "09:00",
  "capacity": 6, "reservedCount": 6, "waitingCount": 1,
  "status": "FULL",
  "roomId": "ROOM-0001", "programRestriction": null
}
```

### Program

실제 2026년 브로셔 기준 6개 프로그램(BASIC 44/49만, SMART 77/82만, VIP 110/120만, PREMIUM 130/140만, YOUNG 20/25만, 온김에검진 8~28만)과
선택검사 그룹 구조(A/B/C selectCount)를 반영. OptionalTest의 수가 미등록 검사는 `price: null + priceRegistered: false`로 표기하고 금액을 추정하지 않는다.

### Statistics

KPI 사전의 필수 8항목 체계 반영: `totalExaminees`, `totalRevenue`, `byType`(공단/종합/특수/출장/채용),
`target`, `achievementRate`, `yoyGrowthRate`, `momGrowthRate`, `avgRevenuePerExaminee`(객단가).

## 6. 예약 상태값 표준

| 상태 | 의미 | 비고 |
|------|------|------|
| REQUESTED | 예약 신청 | 레거시 `예약접수` |
| PENDING_APPROVAL | 직원 승인 대기 | AI 접수 건 필수 경유 |
| CONFIRMED | 예약 확정 | 레거시 `예약확정` |
| CANCELLED | 예약 취소 | 레거시 `예약취소` |
| CHANGED | 예약 변경 | 레거시 `일정변경` |
| COMPLETED | 검진 완료 | 레거시 `검진완료` |
| NO_SHOW | 노쇼 | 신규 |
| WAITING | 대기예약 | 신규 (정원 마감 시) |
| REJECTED | 예약 불가 | 신규 |

레거시 한글 상태 → 표준 매핑은 `core_data_loader.LEGACY_STATUS_MAP` 및 `reservations.json meta.legacyStatusMap`에 정의.
기존 UI(한글 상태)는 이 매핑을 통해 하위 호환을 유지한다.

## 7. Slot 상태값 표준

| 상태 | 의미 |
|------|------|
| AVAILABLE | 예약 가능 |
| FULL | 정원 마감 |
| WAITING | 대기예약 접수 중 |
| DUPLICATED | 중복예약 감지 (Engine 처리 대상) |
| HOLD | 임시 보류 (단체예약 협의 등, `holdUntil` 필드) |
| BLOCKED | 차단 (휴진일·장비점검, Schedule과 연동) |

## 8. 향후 Reservation Engine 연계 방식 (Sprint B)

```
[AI 예약비서 / 웹 / 전화접수]
        │  reservation:request 권한만 보유
        ▼
Reservation Engine (Sprint B)
  ① Slot 조회 (slots.json) — AVAILABLE 여부
  ② 중복예약 검사 (patientId + date) → DUPLICATED 처리
  ③ 자원 검증: doctors/nurses/rooms/equipment + schedules (BLOCKED·HOLIDAY 차단)
  ④ 정원 검사 → 마감 시 WAITING 전환 + 대체시간 추천
  ⑤ 예약 생성 status=PENDING_APPROVAL
  ⑥ 직원 승인(reservation:approve) → CONFIRMED
  ⑦ 전 단계 audit_logs.json append + notifications.json 발송 큐
```

- Engine의 입출력은 본 Sprint의 loader/validator를 그대로 재사용
- Slot 생성·상태전이는 Engine 전담 (수동 편집 금지 원칙을 slots.json meta에 명시)
- 상태 전이 규칙(허용 전이표)은 Sprint B에서 Engine 내부에 구현

## 9. Dashboard 연계 방식

- `dashboard.json`: 일 단위 운영 스냅샷 (기존 Dashboard v3 KPI 6종 + noShow 확장)
- `statistics.json`: 월/분기/연 단위 실적 (KPI 사전 8항목 체계) → 병원장 Dashboard·실적보고 재사용
- `core_data_loader.summary()`: Entity별 건수 헬스체크 제공
- 기존 `dashboard_service_v2_new.js`(localStorage)는 유지하고, 차기 Sprint에서 본 data 폴더(또는 이를 이관한 API)를 데이터 소스로 전환
- `meta.dashboardAggregatable` 플래그로 집계 대상 Entity를 KPI Engine이 자동 식별 가능

## 10. 리스크 및 보완 필요사항

1. **이중 데이터 소스**: 기존 UI는 localStorage/Sheets, 신규 레이어는 JSON 파일 — Sprint B~C에서 단일 소스(API)로 통합 필요
2. **선택검사 수가 미등록**: optional_tests.json 전 항목 `priceRegistered: false` — 수가표 확보 후 일괄 등록 필요
3. **동시성**: JSON 파일 기반은 동시 쓰기에 취약 — Engine 구현 시 잠금 또는 DB 이관 전 단일 쓰기 경로 보장 필요
4. **개인정보**: 현재는 더미지만 실데이터 투입 시 암호화·접근통제·보존기한 정책 필요 (PII 플래그는 준비됨)
5. **상태 전이 검증 부재**: validator는 상태값 유효성만 검사 — 전이 규칙(예: COMPLETED→CONFIRMED 금지)은 Sprint B에서 구현
6. **공휴일 데이터**: schedules.json에 샘플 1건만 존재 — 연간 공휴일 자동 로드 필요
7. **레거시 한글 상태 병존**: 기존 화면 개편 전까지 LEGACY_STATUS_MAP 경유 필수

## 11. 다음 Sprint 제안 (Sprint B: Reservation Engine)

| 우선순위 | 작업 | 기반 |
|:---:|------|------|
| 1 | `src/engine/reservation_engine.py` — 예약 신청→승인 파이프라인 | loader/validator 재사용 |
| 2 | Slot 자동 생성기 (영업일 × 시간대 × 정원, 공휴일 차단) | schedules.json |
| 3 | 중복예약 차단 + DUPLICATED 처리 | patientId+date 검사 |
| 4 | 자원(의사/간호사/검사실/장비) 일정 검증 | 4개 Entity + schedules |
| 5 | 대체시간 추천 (같은 주 AVAILABLE 슬롯 탐색) | slots.json |
| 6 | 승인 워크플로 + 감사로그 자동 기록 | roles/audit_logs |
| 7 | 상태 전이표(State Machine) 구현 및 validator 확장 | 본 문서 §6 |

---

*CSHSP Sprint A | 2026-07-02 | 천안의료원 건강검진센터*
