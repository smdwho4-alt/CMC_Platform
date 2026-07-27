# ADR-015 (Draft/Proposed): Slot 상태 정책을 공식 확정한다

> **상태**: 🔲 **Proposed(제안 단계)** — PM 승인 없이 Accepted로 확정하지 않는다(PM 명시 지시, Sprint 4 Commit 3A). `DECISIONS.md` 원본은 이번 단계에서 수정하지 않았다.
> **작성일**: 2026-07-28
> **범위**: Slot(`data/slots.json`) 상태값과 승인 시 Slot 검증 정책만 다룬다. 예약(Reservation) 승인/거절 상태 전이는 `ADR-014`의 범위이며 이 문서는 그와 겹치지 않는다.

---

## 배경

Sprint 4 Commit 3(Reservation Slot Integration)에서 예약 승인 시 Slot을 조회·점유하는 기능을 처음 도입했다. PM 조건부 승인(Commit 3A, Hardening)에서 "승인 가능한 Slot 상태를 명시적으로 제한하라"는 지시에 따라 Repository의 실제 Slot 상태값을 재조사했고, 그 결과를 이 ADR 초안으로 정리한다.

## 결정(제안)

### Slot 상태값(Repository 실제 조사 결과)

`reservation_engine.py`/`slot_generator.py`를 코드로 확인한 결과, 실제로 쓰이는 Slot 상태값은 다음 5가지다 — `docs/CSHSP_Core_Data_Layer_Sprint_A.md` §7과 일치.

| 상태 | 의미 |
|---|---|
| `AVAILABLE` | 예약 가능(정상) |
| `FULL` | 정원 마감 |
| `WAITING` | 대기예약 접수 중 |
| `HOLD` | 임시 보류(승인 대기 중인 로컬 JSON 예약이 점유) |
| `BLOCKED` | 차단(휴진일·장비점검 등) |

`OPEN`, `CLOSED`는 Repository에 실존하지 않는다 — PM이 예시로 제시했던 명칭이나, 조사 결과 이 프로젝트의 정상 상태명은 `OPEN`이 아니라 `AVAILABLE`이다.

### 승인(예약확정) 시 허용 상태

**`AVAILABLE`만 승인 가능하다.** 그 외 전부 차단하며, 오류 코드는 다음과 같이 확정한다(Sprint 4 Commit 3A, `src/api/routes_admin_portal.py::_SLOT_STATUS_ERROR_CODES`에 이미 구현됨).

| 상태/조건 | 코드 |
|---|---|
| Slot 자체가 없음(date+time 불일치) | `SLOT_NOT_AVAILABLE` |
| `FULL`(상태값 또는 `reservedCount>=capacity`) | `SLOT_FULL` |
| `BLOCKED` | `SLOT_BLOCKED` |
| `HOLD` | `SLOT_ON_HOLD` |
| `CLOSED`(현재 미실존, 정책 대비 매핑만 준비) | `SLOT_NOT_AVAILABLE` |
| `WAITING`, 그 외 알 수 없는 값, 빈 문자열, `null` | `SLOT_INVALID_STATE` |

### WAITING을 허용 목록에 넣지 않은 이유(제안 판단, PM 재확인 필요)

`WAITING`은 Repository에 실존하는 정상 상태값이지만(대기예약 접수 중), 이번 Commit 3A 범위(대기예약 기능 자체는 명시적으로 제외)에서는 이 상태의 Slot에 대한 승인 처리를 정의하지 않았다. "정원이 남아 있어도 허용 상태가 아니면 점유하지 않는다"는 안전 우선 원칙에 따라 `WAITING`을 허용 목록에 넣지 않고 `SLOT_INVALID_STATE`로 차단하는 쪽을 택했다 — 이는 이번 Commit 3A에서 처음 내려진 판단이며, 대기예약 기능이 정식으로 Sheets 승인 흐름에 통합되는 시점(후속 Commit)에 재검토가 필요하다.

### 검증 순서

Slot 조회 → **존재 확인** → **상태 확인** → **Capacity 확인** → **중복 점유 확인** → 점유. 상태 확인이 Capacity 확인보다 먼저 수행된다(PM 안전 우선 원칙 — 정원이 남아 있어도 상태가 허용 범위가 아니면 점유하지 않음).

### 중복 점유 방지

Slot에 `sheetsReservationNos`(예약번호 배열) 필드를 추가해, 동일 예약번호가 같은 Slot 또는 다른 Slot에 이미 점유 기록으로 남아 있으면 `SLOT_RESERVATION_CONFLICT`로 차단한다. Sheets와 Slot 데이터가 불일치하는 상황(Slot에는 점유 흔적이 있으나 Sheets는 아직 예약접수)을 자동으로 정정하지 않는다 — 운영자 확인을 요구한다.

## 대안 검토

- **`OPEN`을 새 상태로 도입**(PM 원안 예시): 기각 — Repository에 이미 `AVAILABLE`이 동일 의미로 존재해 상태값 두 개가 같은 뜻을 갖게 되는 중복을 피했다.
- **WAITING을 허용 상태에 포함**: 보류 — 대기예약 승인 정책 자체가 아직 정의되지 않아, 정의 없이 허용하면 의도치 않은 승인이 발생할 수 있다고 판단했다. 이 ADR이 Accepted로 승격될 때 PM이 재검토할 사항으로 남긴다.

## PM 확인 필요 사항

1. `WAITING` 상태를 계속 차단(`SLOT_INVALID_STATE`)할지, 아니면 별도 코드/정책을 부여할지.
2. 이 ADR을 Accepted로 승격할지, 혹은 Phase 2/3(장비별·검진유형별 정원) 설계가 나온 뒤 함께 확정할지.

## 상태

Proposed. PM 승인 전까지 Accepted로 표기하지 않는다.
