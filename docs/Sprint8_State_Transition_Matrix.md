# Sprint8 State Transition Matrix

> **상태**: 설계 계약 초안(Draft). 상태 전이 상세 규칙은 대부분 DEFERRED(정책 미결정), CAS/Idempotency 구현 없음, PoC·부하검증 결과 미반영. Commit 없음.
> **작성일**: 2026-08-02(Sprint8 Commit8-3a STEP 3-D-A)
> **기준선**: `main`/`origin/main` = `650c899f662730a5578a8d1dd6d8897709b5fda0`

---

## 1. 문서 목적과 범위

관리자 Operations API(`docs/Sprint8_Admin_Operations_API_Contract.md`, 이하 API Contract) §16-20에서 후속 확정으로 위임한 예약 상태 전이 규칙을 상세화한다. 이 문서는 **코드로 확인된 AS-IS 사실**과 **정책 미결정 TO-BE 후보**를 명확히 분리하며, 정책 결정 자체는 수행하지 않는다.

## 2. 기준선 Commit

`650c899f662730a5578a8d1dd6d8897709b5fda0`(HEAD=main=origin/main).

## 3. 선행 문서 및 코드 근거

| 문서/코드 | 경로 | 역할 |
|---|---|---|
| ADR-016 | `ADR-016_Legacy_Stage3_PhaseB_Transition_Design_Draft.md` | 3개 전이 업무규칙(Proposed) |
| ADR-017 | `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` | 전송보안 계약(Accepted with Conditions) |
| Security Architecture Design | `docs/Sprint8_Security_Architecture_Design.md` §10 | 상위 상태전이 보호 원칙 |
| Admin Operations API Contract | `docs/Sprint8_Admin_Operations_API_Contract.md` §16-20 | Operation 계약, 이 문서의 직접 입력자료 |
| companion | `Legacy_Stage3_PhaseB_Design_v1.0.md` §5-1, §6 | AS-IS 전이 분석 원본 |
| GAS 운영본 | `app/apps_script/sheets_api_v3_final.gs` | `_actionUpdateStatus`/`_actionUpdate` 실제 로직 |
| Legacy UI | `app/pages/admin_reservations_v2_new.html` | `AA.saveStatus()` 호출부 |
| Sheets 어댑터 | `app/services/google_sheets_service_v2_new.js` | `CMC_SheetsServiceV2.updateStatus()` |
| 상태 상수 | `app/data/programs_data_new.js` L90 | `CMC.STATUS_LIST` |
| FastAPI 승인 흐름 | `src/api/routes_admin_portal.py` L699-789 | `_process_reservation_approval`, `approve_reservation`, `reject_reservation` |
| 로컬 JSON 엔진(별개 데이터플레인) | `src/api/api_server.py` L279-306 | `approve`/`reject`/`cancel`/`change`/`no-show`/`complete`(RSV- 접두, Sheets와 무관) |

## 4. 용어와 판정 라벨

`CURRENTLY CONFIRMED`(코드/승인문서로 확인) / `PROPOSED`(제안, 미구현) / `NOT IMPLEMENTED`(서버측 대응 없음) / `DEFERRED`(정책·PoC·부하검증 필요) / `NOT FOUND`(근거 미발견).

## 5. AS-IS 상태 저장 구조

Google Sheets `종합검진_예약대장` 시트의 `예약상태` 컬럼(`COL.예약상태`, GAS 상수 정의)에 문자열로 저장(**CURRENTLY CONFIRMED**, `sheets_api_v3_final.gs` L72). 이 문서는 이 Sheets 도메인의 상태만 다루며, `src/api/api_server.py`의 로컬 JSON `RSV-` 도메인 상태(별개 데이터플레인, ADR-013 SSOT 밖)는 범위 밖으로 명시한다.

## 6. 저장소에서 확인된 정확한 상태값 목록

**중대 불일치 발견(§34에서 상술)**: 두 개의 서로 다른 상태값 목록이 코드에 존재한다.

| 출처 | 파일:라인 | 상태값 개수 | 목록 |
|---|---|---|---|
| Legacy Portal 실제 드롭다운 | `app/pages/admin_reservations_v2_new.html` L63, L139 | **6개** | 예약접수/예약확정/검진완료/일정변경/예약취소/**거절** |
| `CMC.STATUS_LIST` 상수 | `app/data/programs_data_new.js` L90 | **5개** | 예약접수/예약확정/검진완료/일정변경/예약취소(**거절 누락**) |

**CURRENTLY CONFIRMED 상태값(6종, Legacy 드롭다운 기준을 채택)**: `예약접수`/`예약확정`/`검진완료`/`일정변경`/`예약취소`/`거절`.

## 7. 상태값별 코드 위치와 사용 위치

| 상태값 | GAS 부수효과 | FastAPI 관련 코드 | 통계 집계 반영 여부 |
|---|---|---|---|
| 예약접수 | 없음(초기값) | `reservation_approval_states.py`의 시작상태 | O(STATUS_LIST 포함) |
| 예약확정 | `COL.예약확정일` 타임스탬프(status=='예약확정'일 때, GAS L398-401) | `approve_reservation` 목표상태 | O |
| 검진완료 | `COL.검진종료` 타임스탬프(GAS L409-411) | 없음(대응 엔드포인트 없음) | O |
| 일정변경 | 없음 | 없음 | O |
| 예약취소 | 없음(Slot 반환 코드 없음, §32) | 없음(Sheets 기준) | O |
| **거절** | 없음 | `reject_reservation` 목표상태 | **X(STATUS_LIST 누락, §34)** |

## 8. 현재 상태 전이 실행 경로

`admin_reservations_v2_new.html` L372 → `AA.saveStatus()`(코드상 함수명은 실제로 저장 로직이 상세모달 저장 핸들러에 인라인되어 있으며, `CMC_SheetsServiceV2.updateStatus(no, newStatus)` L372 직접 호출로 확인 — **CURRENTLY CONFIRMED**) → `google_sheets_service_v2_new.js::_liveUpdateStatus()` → `POST {action:'updateStatus', no, status}` → GAS `doPost` → `_actionUpdateStatus(no, status, confirmedAt)`.

## 9. 관리자 UI → Sheets/GAS의 현재 전이 경로

Legacy Portal은 GAS를 **직접 호출**(FastAPI 미경유, **CURRENTLY CONFIRMED**). Admin Portal(`admin_portal_new.html`)은 승인/거절만 FastAPI 경유(`routes_admin_portal.py::_process_reservation_approval` → `sheets_write.update_status()`).

## 10. FastAPI 관여 여부

| 전이 | FastAPI 관여 |
|---|---|
| 예약접수→예약확정(승인) | 예(**CURRENTLY CONFIRMED**, 세션+CSRF+RBAC+상태전이검증) |
| 예약접수→거절 | 예(**CURRENTLY CONFIRMED**, 상동) |
| 그 외 전부(일정변경/취소/완료, 임의 상태로의 전이) | **아니오**(Legacy Portal이 GAS 직접호출, 무인증) |

## 11-19. Operation별 상태 전이 Matrix

| Operation | Current implementation | From state | To state | State change | Preconditions | Side effects | Failure behavior | Evidence | Decision status |
|---|---|---|---|---|---|---|---|---|---|
| **LIST** | CURRENTLY CONFIRMED | 해당없음 | 해당없음 | 아니오 | 세션+`reservation:view` | 없음 | 503/502(오류) | `routes_admin_portal.py` L201 | 확정(변경불필요) |
| **DETAIL** | CURRENTLY CONFIRMED | 해당없음 | 해당없음 | 아니오 | 상동 | 없음 | 404(대상없음) | `routes_admin_portal.py` L236 | 확정 |
| **APPROVE** | CURRENTLY CONFIRMED | `예약접수`만 | `예약확정` | 예 | `reservation:approve`+CSRF, `assert_can_transition` | `COL.예약확정일` 타임스탬프, Slot 점유(`_reserve_slot_for_approval`) | 409(전이불가), 502(Sheets실패시 Slot Rollback) | `routes_admin_portal.py` L699-778, `reservation_approval_states.py` | 확정(변경불필요) |
| **REJECT** | CURRENTLY CONFIRMED | `예약접수`만 | `거절` | 예 | 상동+사유필수 | 없음 | 상동 | `routes_admin_portal.py` L780-789 | 확정 |
| **RESCHEDULE** | **NOT IMPLEMENTED** | **DEFERRED**(companion#1-3, STEP1§24-1) | **DEFERRED**(RESCHEDULED 별도상태 여부 자체 미정) | 미정(라벨만 vs 실제 일정변경, §34 Gap) | **DEFERRED** | **DEFERRED**(Slot 재배정, companion#7/D11) | **DEFERRED** | 없음(설계 계약만) | **DEFERRED** |
| **CANCEL** | **NOT IMPLEMENTED** | **DEFERRED**(정책) | `예약취소`(목표상태만 확정, ADR-017 §21) | 예(목표만 확정) | 취소사유 필수(**확정**, ADR-017 §21) | **Slot 반환 원칙 확정, 세부규칙 DEFERRED**(companion#7) | **DEFERRED** | ADR-017 §21-22 | 부분확정 |
| **COMPLETE** | **NOT IMPLEMENTED** | `예약확정`만(**확정**, ADR-017 §21 "선행상태 제한" 원칙) | `검진완료` | 예 | 선행상태=예약확정 | 없음(GAS 기존 타임스탬프 부수효과는 있으나 신규 API 경유 시 재검증 필요) | **DEFERRED**(오류코드 세부) | ADR-017 §21 | 부분확정 |
| **NOTE** | **NOT IMPLEMENTED** | 해당없음 | 해당없음 | **아니오**(상태 불변, ADR-017 §14/§23·API Contract §19 확정 — Legacy `_buildNotePayload(note){return{note}}` 패턴과 동일 원칙) | 없음 | 없음(단 메모 내용에 PII 가능성) | **DEFERRED** | `admin_reservations_v2_new.html` L220 | 확정(상태변경 없음 자체는 확정, 구현은 미정) |

## 20-22. From/To-state 후보 및 상태변경 없는 Operation

§11-19 표에 통합 기재. NOTE는 상태변경이 없는 유일한 쓰기 Operation으로 확인됨(§19).

## 23. 현재 구현 여부

§11-19 표의 "Current implementation" 열 참조. **8개 중 4개(LIST/DETAIL/APPROVE/REJECT)만 CURRENTLY CONFIRMED, 4개(RESCHEDULE/CANCEL/COMPLETE/NOTE)는 NOT IMPLEMENTED.**

## 24. 전이 전제조건

APPROVE/REJECT는 `reservation_approval_states.py::assert_can_transition()`으로 서버검증(**CURRENTLY CONFIRMED**). 나머지 4개는 전제조건 자체가 **DEFERRED**(정책) 또는 부분확정(§11-19).

## 25. 전이 후 불변조건

검진완료는 취소·복원 불가(**확정**, ADR-017 §21). 그 외 전이 후 불변조건은 **DEFERRED**.

## 26. 입력값 검증 위치

APPROVE/REJECT는 FastAPI(`reservation_approval_states.py`)에서 검증(**CURRENTLY CONFIRMED**). GAS `_actionUpdateStatus`는 입력값(상태 문자열)을 검증 없이 그대로 저장(**CURRENTLY CONFIRMED as 미검증**, `sheets_api_v3_final.gs` L396, `sheet.getRange(sheetRow, COL.예약상태).setValue(status)` — 이전 상태 비교나 허용값 검증 없이 임의 문자열 저장 가능).

## 27. 실패 시 상태 보존 원칙

APPROVE 실패 시 Slot Rollback(`_safe_rollback_slot`, **CURRENTLY CONFIRMED**, `routes_admin_portal.py` L739-748). 그 외 4개 신규 Operation의 실패 시 상태 보존 원칙은 API Contract §28(ADR-017 §23 재인용, 불확실 성공 상태는 자동재시도 금지)을 따르나 구현은 **NOT IMPLEMENTED**.

## 28. 중복 요청 처리 상태

Idempotency Key 개념(ADR-017 §14) 자체가 **PROPOSED**이며 현재 저장소에 구현 없음(**NOT IMPLEMENTED**, grep 재확인 0건). API Contract §21과 동일하게 유지.

## 29. stale update 및 동시성 위험

GAS `LockService.getScriptLock()`으로 쓰기는 직렬화되나(**CURRENTLY CONFIRMED**), "다른 사용자가 이미 다른 상태로 바꿨다"를 탐지하는 낙관적 잠금은 없다. **코드 주석으로 직접 확인**: `src/api/routes_admin_portal.py` L703 "GAS updateStatus는 compare-and-swap을 지원하지 않으므로"(**CURRENTLY CONFIRMED as 명시적 한계 인정**).

## 30. CAS/버전 비교 지원 여부

**NOT IMPLEMENTED**(§29 코드주석 근거). API Contract §22 Open Question("Stale update 탐지 방식")과 동일 미해결 상태 유지 — 이 문서에서 새로 확정하지 않는다.

## 31. 감사로그 요구사항

기존 재사용 대상: `src/reservation/reservation_audit.py::append_audit()` → `data_dir/"audit_logs.json"`(**CURRENTLY CONFIRMED**). APPROVE/REJECT는 이미 감사기록(**CURRENTLY CONFIRMED**, `audit.append_audit(...)` 호출 확인). 신규 4개 Operation의 이벤트명(`RESERVATION_RESCHEDULED` 등)은 API Contract §25와 동일하게 **PROPOSED**.

## 32. Slot 반환·재계산 부수효과

GAS `_actionUpdateStatus`에 Slot 관련 코드가 전혀 없음을 재확인(**CURRENTLY CONFIRMED as 부재**, 전체 함수 재검토). 취소 시 Slot 반환은 원칙만 확정(ADR-017 §22), 세부규칙(즉시/유예/재배정)은 **DEFERRED**(companion#7/D11, 관련성만 표시, 병합 안 함). `reservedCount` 정합성 결함 수정은 **Commit8-3d 범위**로 이 문서에서도 명확히 유지한다.

## 33. 개인정보·오류응답 제한

조회 응답은 마스킹(**CURRENTLY CONFIRMED**, `pii_mask.build_masked_reservation`). 상태변경 응답의 오류 메시지는 일반화 원칙(API Contract §14 재인용, 구현은 부분적).

## 34. 코드와 문서 불일치

1. **`CMC.STATUS_LIST`(5개, "거절" 누락) vs Legacy Portal 실제 드롭다운(6개, "거절" 포함)**(§6 신규 발견) — `CMC.STATUS_LIST`를 사용하는 통계/KPI 집계 코드(예: `dashboard_sheets_service_new.js::statusCounts()`)는 "거절" 상태의 예약을 상태별 카운트에서 누락시킬 가능성이 있음. 이 문서는 이를 정정하지 않고 **Gap으로만 기록**한다.
2. **"예약변경"은 실제 일정을 변경하지 않는다**(ADR-016 companion §5-1 항목1, 이번 조사로 재확인 — Legacy 상세모달의 희망일시는 `<span>` 읽기전용). API Contract가 이를 "RESCHEDULE"로 명명한 것은 **목표(TO-BE) 명칭이며 현재(AS-IS) 동작과 다름**을 재확인, 중대한 AS-IS Gap으로 유지.
3. ADR-016 companion이 "GAS 쓰기 액션에 인증·인가가 전혀 없다"고 기술한 내용은 이번 재조사(§9, §26)로도 동일하게 재확인됨(불일치 아님, 일치 확인).

## 35. 미결정 사항

RESCHEDULE의 from/to-state 전체, CANCEL/RESCHEDULE의 Slot 세부규칙, COMPLETE의 상세 오류코드, stale update 탐지 방식(§30) — 전부 DEFERRED 또는 Open Question으로 유지.

## 36. 후속 구현 및 테스트 Gate 입력사항

Commit8-3d 착수 전 확정 필요: companion#1/#2/#3(변경시점/횟수/당일), STEP1§24-1(RESCHEDULED 상태), companion#7(Slot 세부규칙). Security Test and Deployment Gate Plan(STEP3-E)은 §34의 두 코드 불일치를 회귀 테스트 항목 후보로 참조 가능(이 문서는 그 채택 여부를 확정하지 않음).

## 37. 추적성 표

| ID | 출처 | 이 문서 반영 위치 | 최종상태 |
|---|---|---|---|
| companion#1/#2/#3 | companion §16 | §11-19(RESCHEDULE), §35 | DEFERRED |
| companion#7 | companion §16 | §11-19(CANCEL/RESCHEDULE), §32 | 부분확정(원칙만) |
| D11 | 실행계획 §Decision | §32(관련성만 표시) | DEFERRED(companion#7과 별개 ID 유지) |
| STEP1§24-1 | 세션(STEP1) | §11-19(RESCHEDULE), §35 | DEFERRED |
| DR-B-01/02 | 세션(STEP2-B/C) | §28(Idempotency 미구현 확인) | 변경 없음(ADR-017과 동일) |

## 38. 결론

8개 Operation 중 4개(LIST/DETAIL/APPROVE/REJECT)는 현재 구현되어 안전하게 확인되었고, 4개(RESCHEDULE/CANCEL/COMPLETE/NOTE)는 미구현이며 상당수 세부규칙이 정책 결정을 기다리고 있다. 이번 조사에서 `CMC.STATUS_LIST` 누락이라는 새로운 코드 Gap을 발견했다(§34). 상태 전이 규칙의 완전한 확정은 이 문서 단독으로 불가능하며, companion#1/#2/#3/#7·STEP1§24-1의 PM 정책결정을 필요로 한다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 어떤 기존 파일도 수정하지 않았다. 상태값·전이 규칙을 새로 발명하지 않았다(코드에서 확인된 값만 사용). CAS/Idempotency를 구현된 것으로 표현하지 않았다. DEFERRED 항목을 확정하지 않았다. 실제 Secret·PII·운영 URL 미포함. Git add/commit/push 없음.
