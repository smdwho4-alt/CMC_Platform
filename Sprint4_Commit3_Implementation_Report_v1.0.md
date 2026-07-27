# Sprint 4 Commit 3 Implementation Report v1.0 — Reservation Slot Integration

> **작성일**: 2026-07-28
> **선행 문서**: `Sprint4_Commit3_Slot_Capacity_Design_v1.0.md`(Design Phase), `ADR-014_Reservation_State_Machine.md`

---

## 1. 수정 파일

| 파일 | 구분 | 내용 |
|---|---|---|
| `src/api/routes_admin_portal.py` | 수정 | `_reserve_slot_for_approval()`/`_rollback_slot_reservation()` 신규 헬퍼 추가, `_process_reservation_approval()`에 Slot 조회·점유·Rollback 단계 삽입(승인 경로만) |
| `app/pages/admin_portal_new.html` | 수정 | `_extractDetailMessage()` 헬퍼 추가, 승인 409 처리에 SLOT_NOT_AVAILABLE/SLOT_FULL 분기 추가 |
| `tests/run_sprint4_commit2_approval_qa.py` | 수정(회귀 대응) | Commit 3로 인해 승인이 Slot 매칭을 요구하게 되면서 깨진 기존 픽스처에 매칭용 Slot과 wishDate/wishTime 추가 |
| `tests/run_sprint4_commit3_slot_integration_qa.py` | 신규 | Commit 3 전용 테스트 스위트(49건) |
| `Sprint4_Commit3_Implementation_Report_v1.0.md` | 신규 | 본 문서 |

**변경하지 않은 파일**(재사용 확인): `src/reservation/reservation_engine.py`, `src/reservation/slot_generator.py`, `src/reservation/alternative_slot_recommender.py`, `src/api/file_lock.py`, `app/apps_script/sheets_api_v3_final.gs`, `src/api/api_server.py`.

## 2. 재사용한 코드

| 재사용 대상 | 재사용 방식 |
|---|---|
| `reservation_engine.py::_update_slot()` | Slot 점유(정원 증가/상태 전환)를 그대로 호출. 신규 Slot 갱신 로직을 작성하지 않았다. |
| `reservation_engine.py::_release_slot()` | Sheets 쓰기 실패 시 Rollback에 그대로 호출 — 정원 복구와 `SLOT_RELEASED` Audit 기록을 이 함수가 이미 수행하므로 별도 구현이 필요 없었다. |
| `file_lock.py::DataLock` | Slot 조회→Capacity 검사→점유 구간 전체를 감싸 동시성을 보호(Sprint 3 CRM이 이미 쓰던 것과 동일 컨텍스트 매니저). |
| `reservation_audit.py::append_audit()` | Commit 2와 동일하게 재사용, 신규 이벤트 타입 추가 없이 기존 `RESERVATION_APPROVED`/`SLOT_FULL`/`SLOT_RELEASED`(전부 Sprint B부터 등록되어 있던 이벤트) 그대로 사용. |
| `core_data_loader.load_entity("Slot", ...)` | Slot 목록 조회에 재사용, 신규 로더 없음. |
| `reservation:approve` 권한 문자열 | Commit 2와 동일 권한 재사용, 신규 권한 없음. |

`alternative_slot_recommender.py`, `Equipment.capacityPerHour`, `slot_generator.py`의 Slot **생성** 로직은 이번 Commit에서 호출하지 않았다(PM 금지 사항 — AI 추천/자동 재배정/장비별 Capacity 실사용은 Commit 4 이후).

## 3. Slot Workflow

PM이 요구한 정확한 순서로 구현했다(`_process_reservation_approval()` 내부, 승인(`예약확정`)일 때만 진입).

```
예약접수(상태 확인, Commit 2 기존 로직)
  → Slot 조회(date+time 매칭, 신규)
    → 없음 → 409 SLOT_NOT_AVAILABLE
    → 있음 → Capacity 검사
      → FULL(reservedCount >= capacity) → 409 SLOT_FULL
      → 여유 → Slot 점유(_update_slot 재사용)
        → Sheets 상태 변경(GAS updateStatus, Commit 2 기존 로직)
          → 실패 → Slot Rollback(_release_slot 재사용) → 502 SHEETS_WRITE_FAILED
          → 성공 → Audit 기록(RESERVATION_APPROVED, slotId 포함) → 200 응답
```

거절(`거절`) 경로는 이 Workflow에 들어가지 않는다 — Slot을 소비하지 않으므로 Commit 2 로직 그대로 유지(회귀 테스트로 확인).

## 4. Capacity 처리

- Slot을 수검자 예약의 `wishDate`+`wishTime`으로 조회(정확히 일치하는 첫 Slot 채택). 프로그램 제한(`programRestriction`) 매칭은 이번 Commit에 포함하지 않았다 — Sheets `program`이 이름 문자열이라 Program ID로의 역매핑이 필요한데, 이는 Commit 2에서 이미 "금지"로 확정된 범위(프로그램·사업장·담당자 역매핑 구현 금지)와 동일한 성격이라 포함하지 않았다.
- 정원 판정은 `reservedCount >= capacity` 단일 조건. `AVAILABLE`/`FULL` 두 상태만 실제로 갱신하며, 기존 Slot이 이미 `BLOCKED`/`HOLD` 상태인 경우를 별도로 차단하는 로직은 이번 Commit에 포함하지 않았다(PM이 제시한 문자열 그대로의 Workflow — "Slot 존재? / Capacity 검사"만 요구했으므로 그 이상으로 확장하지 않음. §12 기술부채에 기록).
- 검사(장비)별·검진유형별 정원 정책은 명시적으로 구현하지 않았다(PM 금지 사항).

## 5. Rollback 처리

`sheets_write.update_status()`가 `SheetsIntegrationError` 또는 `SheetsIntegrationNotConfigured`를 던지면, Slot이 이미 점유된 상태(`slot_id`가 not None)일 때만 `_rollback_slot_reservation()`을 호출한다 — `_release_slot(data_dir, slot_id, actor, was_confirmed=True, note=...)`을 그대로 호출해 정원을 원복하고 `SLOT_RELEASED` Audit을 남긴다. Rollback 후 원래 예외에 대응하는 HTTP 응답(503 또는 502)을 반환한다. 테스트로 "Sheets 실패 시 Slot이 정확히 0/AVAILABLE로 복구됨"과 "SLOT_RELEASED Audit이 기록됨"을 둘 다 확인했다.

## 6. Sheets 처리

- GAS를 무수정으로 유지했다 — 기존 `updateStatus` action만 재호출(Commit 2와 동일 호출 지점).
- **Slot 확보가 Sheets 쓰기보다 먼저 일어나도록 순서를 고정**했다(PM 절대 원칙). Slot 조회·점유가 실패하면(409) Sheets에는 애초에 쓰기 요청 자체가 가지 않는다.
- Sheets에 Slot 관련 정보(slotId 등)를 전송하지 않는다 — Sheets는 여전히 기존 29개 컬럼만 다룬다.

## 7. Audit 처리

- Sheets 쓰기 성공 후에만 `RESERVATION_APPROVED`를 기록하며(기존 정책 유지), 이번 Commit부터는 `after.slotId`를 추가로 포함해 어떤 Slot이 이 승인에 쓰였는지 추적 가능하게 했다.
- Slot 점유로 정원이 가득 찬 순간에는 `SLOT_FULL` Audit이(기존 `reservation_engine.py::approve_reservation()`이 쓰던 것과 동일 이벤트) 별도로 기록된다.
- Rollback 시에는 `_release_slot()` 내부에서 자동으로 `SLOT_RELEASED`가 기록된다(신규 로직 없음).
- Audit 자체가 실패하는 경우의 정책은 Commit 2에서 이미 조사·확정한 대로 **Best Effort**(보상 트랜잭션 없음)를 그대로 따른다 — 이번 Commit에서 다시 조사하지 않고 기존 결론을 재사용했다.

## 8. RBAC

신규 권한 문자열을 추가하지 않았다. Slot 조회·점유는 `reservation:approve` 승인 자체의 부수 효과로 취급했다 — Slot 전용 권한(`slot:manage` 등)을 별도로 요구하지 않는다(설계 문서 §9에서 이미 이 방향으로 제안했고 그대로 구현). 코드에 역할명을 하드코딩한 곳이 없음을 정적 검사로 재확인했다(`ROLE-`로 시작하는 문자열 비교가 Slot 통합 코드 블록에 없음).

## 9. 동시성

PM이 요구한 `Lock → Capacity 검사 → Slot 점유 → Unlock` 순서를 `with DataLock(data_dir):` 블록으로 정확히 구현했다. `DataLock.__exit__`이 예외 발생 시에도 항상 잠금을 해제하는 것을 소스로 확인했으므로(409를 그 블록 안에서 raise해도 잠금 누수가 없음), Capacity 초과로 인한 409를 블록 내부에서 바로 던지는 방식을 그대로 채택했다.

**한계(설계 문서 §11에서 이미 명시, 재확인)**: Slot 점유 자체는 `DataLock`으로 원자적이지만, Slot 점유(로컬 JSON)와 Sheets 상태 변경(GAS) 사이의 원자성은 이번 Commit으로도 완전히 보장되지 않는다 — 두 저장소에 걸친 트랜잭션이기 때문이다. 이 한계를 완화하기 위해 "Slot 먼저 확보, 실패 시 Rollback"이라는 순서를 PM이 지정했고 그대로 구현했지만, Rollback 자체가 실패하는 극단적 상황(예: Slot 파일 쓰기 중 프로세스 종료)까지 막지는 못한다 — 이는 기존 `reservation_engine.py`도 동일하게 갖고 있는 한계다.

## 10. 테스트

`tests/run_sprint4_commit3_slot_integration_qa.py` 신규 49건 전부 PASS. PM이 요구한 Backend 12개 항목(Slot 존재/없음/FULL/Available/Reserve/Rollback/Sheets실패/Audit/RBAC/409/502/동시 승인)과 Portal 5개 항목(예약확정/Slot FULL/Slot 없음/Toast/목록 재조회)을 모두 커버했다. 실브라우저 QA는 정적 페이지 로드 확인에 그치지 않고, `sheets_readonly_service`/`sheets_write_service`를 미리 monkeypatch한 실제 uvicorn 프로세스를 별도 launcher 스크립트로 띄워 브라우저→실서버 경로로 SLOT_FULL·SLOT_NOT_AVAILABLE·기존 409(이미 처리됨) 세 가지 토스트 문구가 실제로 구분되어 표시되는 것을 확인했다(정적 코드 검사가 아닌 실제 왕복 검증).

## 11. 회귀 결과

- Sprint A/B/D/E/F/H, Single Admin Portal Sprint 1~3 전체 스위트: 전부 PASS.
- **Sprint 4 Commit 2 자체 테스트 스위트가 최초 4건 FAIL했다** — Commit 3이 승인 시 Slot 매칭을 요구하도록 바꾸면서, Commit 2 테스트의 가짜 예약 픽스처에 `wishDate`/`wishTime`이 없어 항상 `SLOT_NOT_AVAILABLE`로 막혔기 때문이다(코드 결함이 아니라 Commit 3이 의도한 대로 동작을 바꾼 결과). `run_sprint4_commit2_approval_qa.py`에 넉넉한 정원(50)의 더미 Slot과 매칭 `wishDate`/`wishTime`을 추가해 68/68 PASS로 복구했다 — 이 테스트 파일 자체의 수정은 이번 Commit 3의 회귀 대응으로 포함했다.
- Commit 전 Sprint 3의 audit/ai_support/ux 세 스위트가 "커밋되지 않은 프로덕션 .py 변경 없음" 어서션에서 일시적으로 FAIL하는 것은 Commit 2/Commit 1에서도 반복 관찰된 것과 동일한 현상(아직 커밋 전이라 발생, 커밋 후 자동 해소)이며 진짜 회귀가 아니다.

## 12. 기술부채

1. **BLOCKED/HOLD 상태 Slot에 대한 명시적 차단 없음**(§4) — 이번 Workflow는 "존재 여부"와 "정원"만 검사한다. `BLOCKED`/`HOLD` 상태의 Slot이 매칭되면 정원 계산상 여유가 있으면 그대로 점유될 수 있다 — 설계 문서 §5가 제안한 Sheets 도메인 전용 Slot 상태(OPEN/FULL/CLOSED/BLOCKED)는 이번 Commit에서 채택하지 않고 기존 로컬 상태값을 그대로 썼기 때문에 생기는 갭이다.
2. **예약 변경/취소 시 Slot 미복구**(설계 문서 §12에서 이미 식별) — 이번 Commit은 승인 Workflow만 다루므로 여전히 남아 있는 공백이다.
3. **Slot-Sheets 간 비원자성**(§9) — Rollback으로 완화했으나 근본 해결은 아니다.
4. **admin_reservations_v2_new.html의 "거절" 옵션을 통한 Slot 우회**(Commit 2에서 이미 식별) — 그 화면에서 상태를 직접 바꾸면 이번 Slot Workflow를 거치지 않는다. 이번 Commit으로 새로 생긴 문제는 아니지만, Slot 정원 관점에서는 그 화면의 "예약확정" 선택도 마찬가지로 Slot을 소비하지 않고 우회한다는 점이 이번 Commit에서 새롭게 드러났다 — Commit 5(Legacy Admin 흡수)에서 재검토 필요.

## 13. 다음 Commit 영향

- **Commit 4(문진)**: 이번 Commit은 문진 참조 키 전환에 영향을 주지 않는다(별개 관심사).
- **Commit 5(Legacy Admin 흡수)**: `admin_reservations_v2_new.html`을 통한 Slot 우회(§12-4)를 이 시점에 반드시 재검토해야 한다 — 그 화면이 존치되는 한 Slot 정원 정책이 완전히 지켜지지 않는다.
- **후속 Commit 후보**: BLOCKED/HOLD 처리(§12-1), 예약 변경/취소 시 Slot 복구(§12-2), 장비별·검진유형별 Capacity(Phase 2/3, 설계 문서 §3)는 전부 이번 Commit 범위 밖으로 남아 있다.
