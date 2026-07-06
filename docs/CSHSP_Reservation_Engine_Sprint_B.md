# CSHSP Reservation Engine — Sprint B 산출 문서

> **프로젝트:** Cheonan Medical Center AI Health Screening Concierge Platform (CSHSP)
> **Sprint:** B — Reservation Engine 구현
> **작성일:** 2026-07-02
> **위치:** `99_임시보관_정리대기/CMC_Platform_new/src/reservation/`

---

## 1. Sprint B 목적

Sprint A Core Data Layer(20 Entity JSON + Loader/Validator) 위에 실제 병원 운영 가능한 **예약 판단 엔진**을 구현한다.

핵심 원칙 준수:
- AI는 예약을 직접 확정하지 않는다 — 신청은 항상 `PENDING_APPROVAL`로 생성되고, `reservation:approve` 권한을 가진 직원 승인 후에만 `CONFIRMED`
- 모든 예약 신청·승인·변경·취소·거절은 Engine을 통과하며 `audit_logs.json`에 append-only 기록
- Sprint A의 `core_data_loader` / `data_validator` 재사용 (검증 완료)
- 의료 판단 기능 없음

## 2. Reservation Engine 구조

```
src/reservation/
├── reservation_engine.py            ★ 엔진 본체 (신청·승인·취소·거절·변경·노쇼·완료)
├── state_machine.py                 상태 전이표 + InvalidTransitionError
├── slot_generator.py                영업일 기반 Slot 생성 (주말·휴진일 차단)
├── alternative_slot_recommender.py  대체시간 추천 (최대 5개)
├── reservation_audit.py             감사로그 기록 (append-only)
└── json_store.py                    엔벨로프 보존 JSON 읽기/쓰기 + 채번 헬퍼

의존 방향: engine → (state_machine, audit, recommender, json_store) → core_data_loader(Sprint A)
```

### 주요 함수

| 함수 | 역할 |
|------|------|
| `validate_slot(slotId, patientId, date, ...)` | 예약 가능 판정 → AVAILABLE/FULL/WAITING/DUPLICATED/HOLD/BLOCKED/INVALID |
| `create_reservation_request(...)` | 예약 신청 → PENDING_APPROVAL 생성 + Slot HOLD (allow_waiting 시 WAITING 접수) |
| `approve_reservation(id, approver)` | 직원 승인 → CONFIRMED + Slot 점유 확정 + Notification 큐 적재 |
| `cancel_reservation(id, actor, reason)` | 취소 → CANCELLED + Slot AVAILABLE 복구 |
| `reject_reservation(id, actor, reason)` | 직원 거절 → REJECTED + Slot 복구 |
| `change_reservation(id, newSlot, ...)` | 확정 예약 변경 → CHANGED → PENDING_APPROVAL 재승인 대기 |
| `mark_no_show(id, actor)` / `complete_reservation(id, actor)` | 노쇼(CONFIRMED에서만) / 검진 완료 처리 |
| `generate_slots(start, end, ...)` | Slot 일괄 생성 (주말·HOLIDAY 제외, 기존 Slot 보존) |
| `recommend_alternative_slots(date, ...)` | 대체 Slot 최대 5개 추천 |

## 3. State Machine

```
REQUESTED ──────→ PENDING_APPROVAL ──→ CONFIRMED ──→ COMPLETED
    │                    │                 │
    ├→ CANCELLED         ├→ CANCELLED      ├→ CANCELLED
    └→ REJECTED          └→ REJECTED       ├→ NO_SHOW   ← CONFIRMED에서만
                                           └→ CHANGED ──→ PENDING_APPROVAL

WAITING → PENDING_APPROVAL / CANCELLED / REJECTED   (Sprint B 확장: 대기예약 승격·정리)
종결 상태(전이 불가): COMPLETED, CANCELLED, NO_SHOW, REJECTED
```

- 잘못된 전이는 `InvalidTransitionError`로 차단되고, 차단 사실 자체가 `INVALID_TRANSITION` 이벤트로 감사기록된다.
- `WAITING` 전이는 스펙 외 확장이다. 대기예약을 승격(PENDING_APPROVAL)하거나 정리(CANCELLED/REJECTED)할 경로가 필요해 추가했다.

## 4. Slot 검증 로직 (판정 순서)

| 순서 | 검증 | 판정 |
|:---:|------|------|
| 1 | 날짜 형식 / Slot 존재 / Slot-날짜 일치 / 프로그램 제한 | INVALID |
| 2 | 공휴일·병원 휴진일 (schedules HOLIDAY+BLOCKED) | BLOCKED |
| 3 | Slot 자체 상태 BLOCKED / HOLD | BLOCKED / HOLD |
| 4 | 동일 환자 동일일자 활성 예약(REQUESTED/PENDING/CONFIRMED/WAITING/CHANGED) | DUPLICATED |
| 5 | 근무 가능 의사 / 간호사 (workDays + 당일 BLOCKED 일정 제외) | BLOCKED |
| 6 | 검사실 ACTIVE + 운영시간(08:00~17:00) + 검사실 장비 ACTIVE | BLOCKED |
| 7 | 정원 (reservedCount ≥ capacity 또는 상태 FULL) | FULL |
| 8 | 이상 없음 | AVAILABLE (또는 WAITING/DUPLICATED 상태 승계) |

## 5. 예약 신청 흐름

```
create_reservation_request(patientId, programId, date, time, slotId, channel, requestedBy)
  ① 신청자 권한 확인 (USR- 계정이면 reservation:request 또는 approve 필요, 수검자 본인 채널은 허용)
  ② 환자·프로그램 존재 확인
  ③ validate_slot() — 불가 시 사유 + 대체 Slot 최대 5개 반환
  ④ DUPLICATED → DUPLICATED_REJECTED 감사기록 후 거부
  ⑤ 예약번호 채번: YYYYMMDD-0001 (당일 순번, 기존 id 충돌 방지)
  ⑥ 예약 생성 status=PENDING_APPROVAL, Slot → HOLD
  ⑦ 감사기록: RESERVATION_REQUESTED + SLOT_HELD
  * FULL Slot + allow_waiting=True → status=WAITING 대기예약 접수 (Slot → WAITING, waitingCount+1)
```

## 6. 직원 승인 흐름

```
approve_reservation(reservationId, approverUserId)
  ① 권한 확인: reservation:approve (AI 계정 ROLE-AI-AGENT는 불가 → EnginePermissionError)
  ② 상태 확인: PENDING_APPROVAL → CONFIRMED (State Machine)
  ③ 예약 갱신: approvedBy / approvedAt 기록
  ④ Slot 점유 확정: reservedCount+1 → 정원 도달 시 FULL(+SLOT_FULL 감사기록), 미달 시 AVAILABLE 복귀
  ⑤ 감사기록: RESERVATION_APPROVED
  ⑥ Notification 생성 준비: notifications.json에 RSV_CONFIRMED PENDING 적재
```

> **스펙 5-4 구현 노트**: "Slot 상태를 FULL로 변경"은 정원 기반으로 구현했다.
> Sprint A의 Slot 정원 모델(capacity 6)에서 승인 1건마다 무조건 FULL 처리하면 잔여 5석이 사장되므로,
> 정원 도달 시에만 FULL로 전환한다 (정원 1 Slot에서는 스펙 그대로 승인 즉시 FULL — 테스트 검증됨).

## 7. 예약 취소 흐름

```
cancel_reservation(reservationId, actorUserId, reason)
  ① 취소 가능 상태 확인: REQUESTED / PENDING_APPROVAL / CONFIRMED / WAITING
  ② status → CANCELLED, cancelReason 기록
  ③ Slot 복구: CONFIRMED였다면 reservedCount-1, 상태 AVAILABLE 복구 (SLOT_RELEASED)
  ④ 감사기록: RESERVATION_CANCELLED
```

거절(reject_reservation)은 동일 구조로 REQUESTED/PENDING_APPROVAL → REJECTED,
변경(change_reservation)은 CONFIRMED → CHANGED → PENDING_APPROVAL로 재승인 대기 전환 + changeHistory 누적.

## 8. 대체시간 추천 로직

- 후보: `AVAILABLE` + 정원 여유 + 프로그램 제한 충족 (+검사실 지정 시 동일 검사실)
- 정렬: ① 요청일과의 날짜 거리 ② 날짜 ③ 요청시간과의 시간 거리
- 최대 5개 반환. 신청 실패 응답(`alternatives`)에 자동 포함

## 9. 감사로그 구조

이벤트 12종 (표준 10 + 확장 2):
`RESERVATION_REQUESTED / APPROVED / CANCELLED / REJECTED / CHANGED`,
`SLOT_HELD / SLOT_RELEASED / SLOT_FULL`, `INVALID_TRANSITION`, `DUPLICATED_REJECTED`
(+확장: `RESERVATION_NO_SHOW`, `RESERVATION_COMPLETED`)

레코드: `{id: AUD-YYYYMMDD-0001, timestamp, actorUserId, actorRole(자동조회), action, entityType, entityId, before, after, channel, note}` — append-only, 기존 로그 수정 없음.

## 10. 테스트 결과

`tests/run_sprint_b_tests.py` — **38/38 PASS** (결과: `tests/sprint_b_test_result.csv`)

- 원본 `data/` 보호: `tests/sandbox_sprint_b/data` 사본에서 실행, 원본 불변 검증 포함
- 요구된 10개 시나리오 전부 포함: 정상 신청 / 직원 승인 / 취소 / 중복 차단 / FULL 차단 / BLOCKED 차단 / 잘못된 전이 차단 / CONFIRMED→NO_SHOW / 대체 5개 이하 추천 / 감사로그 확인
- 추가 검증: AI 계정 승인 차단, HOLD 판정, 거절, 변경 재승인, 대기예약 전환, 정원 1 Slot의 FULL 전환, Slot 생성기(영업일 40개·휴진일 0개·기존 보존), 표준 이벤트 10종 전수 발생, **Sprint A Validator로 최종 무결성 오류 0건**

## 11. 발견된 문제

1. **스펙 5-4 (승인 시 Slot 무조건 FULL)** — 정원 모델과 충돌 → 정원 기반으로 구현 (§6 노트). 운영 정책상 "슬롯당 1건" 원칙이면 capacity=1로 생성하면 스펙 동작과 동일
2. **동시성 없음** — JSON 파일 직접 쓰기라 동시 신청 시 race condition 가능. 단일 프로세스 전제
3. **HOLD 만료 없음** — 신청 후 승인/거절이 없으면 Slot이 HOLD로 남음. holdUntil 기반 자동 해제 배치 필요
4. **대기예약 승격 자동화 없음** — 취소로 자리가 나도 WAITING 예약 자동 승격 미구현 (수동 처리 전제)
5. **공휴일 데이터 수동 관리** — schedules.json에 등록된 HOLIDAY만 차단됨. 연간 공휴일 일괄 등록 도구 필요

## 12. Sprint C 제안 (Admin Console)

| 우선순위 | 작업 | 엔진 연계 |
|:---:|------|----------|
| 1 | 승인 대기함 (PENDING_APPROVAL 목록 + 승인/거절 버튼) | approve/reject_reservation |
| 2 | 예약 목록·상세·검색 (상태별 필터) | loader + state_machine.allowed_next로 가능 액션 표시 |
| 3 | Slot 관리 화면 (생성·차단·HOLD 해제) | slot_generator + _update_slot |
| 4 | 일정 관리 (휴진일·장비점검 등록 → Slot 자동 차단) | schedules.json |
| 5 | 감사로그 조회 (기간·행위자·이벤트 필터) | audit_logs.json |
| 6 | Dashboard 연계 (승인 대기 건수, 대기예약 현황 KPI 추가) | dashboard.json |
| 7 | HOLD 만료 자동 해제 + WAITING 자동 승격 배치 | 엔진 확장 |

---

*CSHSP Sprint B | 2026-07-02 | 천안의료원 건강검진센터*
