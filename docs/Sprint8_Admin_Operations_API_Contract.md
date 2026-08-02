# Sprint8 Admin Operations API Contract

> **상태**: 설계 계약 초안(Draft). 코드 구현 없음, 상태 전이 세부규칙·RBAC 세부확정 없음(후속 문서로 위임), DEFERRED 8건 미확정 유지, PoC·부하검증 결과 반영 없음. Commit 없음.
> **작성일**: 2026-08-02(Sprint8 Commit8-3a STEP 3-C)
> **기준선**: `main`/`origin/main` = `76b4ddecc0489493d16f626d6798298d4fa98280`
> **목적**: 관리자 브라우저가 예약 상태변경 업무를 수행하는 API의 설계 계약을 정의한다. 실제 엔드포인트 구현이 아니라 계약 초안이며, 상태 전이 상세 규칙은 State Transition Matrix, 권한 상세는 RBAC Permission Matrix가 별도로 확정한다.

---

## 1. 문서 목적

`ADR-016`(관리자 업무 전환 규칙)과 `ADR-017`(FastAPI Proxy·HMAC 전송보안 계약), `Sprint8_Security_Architecture_Design.md`(상위 보안 아키텍처)에서 확정된 원칙을 바탕으로, 관리자가 호출하는 Admin Operations API의 계약(Operation ID·Route·요청/응답 구조·인증/인가 요구사항)을 정의한다.

## 2. 범위와 비범위

**범위**: 관리자 예약 조회·상태변경(승인/거절/일정변경/취소/검진완료/메모저장) API의 계약 초안.

**비범위**:
- 상태 전이 상세 규칙(허용 이전상태, 허용 시점 등) — **State Transition Matrix**(후속 문서)
- 역할별 상세 권한 매트릭스 — **RBAC Permission Matrix**(후속 문서)
- 실제 코드 구현 — Commit8-3b/8-3d
- GAS 소스 수정 — 이 문서에서 수행하지 않음
- Google Sheets 스키마 변경 — 대상 없음

## 3. 상위 설계 및 추적성

| 출처 | 문서 | 역할 |
|---|---|---|
| ADR-016 | `ADR-016_Legacy_Stage3_PhaseB_Transition_Design_Draft.md` | 관리자 3개 전이 업무 규칙(Proposed) |
| ADR-017 | `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` | HMAC·Nonce·Idempotency·응답계약(Accepted with Conditions) |
| 상위 아키텍처 | `docs/Sprint8_Security_Architecture_Design.md` | 신뢰경계·인증·RBAC·감사로그 원칙(§7-15 인용) |
| 실행계획 | `docs/Sprint8_Security_and_Pilot_Readiness_Execution_Plan.md` | D6~D9/D11/D27(원래 Commit8-3/8-4 정의, 별도 ID 체계) |
| STEP3-B 인터페이스 | Security Architecture Design §22 표 | 이 문서가 준수해야 할 입력자료·불변조건 |

Decision ID(companion#1~10, STEP1§24-1~6, DR-B-01~05, D6~D9/D11/D27)는 원문 그대로 인용하며 병합·재번호화하지 않는다.

## 4. 용어와 표기 규칙

- `CURRENTLY CONFIRMED`: 저장소 코드로 확인된 현재 구현 사실
- `PROPOSED`: ADR/이전 STEP에서 제안되었으나 미구현
- `NOT IMPLEMENTED`: 저장소에서 확인되지 않음(구현 없음)
- `DEFERRED`: 정책 결정 필요, 이 문서에서 확정하지 않음
- `REQUIRES POC`: DR-B-01 PoC 3건 완료 필요
- `REQUIRES LOAD TEST`: DR-B-02 부하검증 완료 필요

## 5. AS-IS 관리자 상태변경 호출 경로

**현재 구현 확인**(코드 근거, `src/api/routes_admin_portal.py` 재확인):

| 실제 경로 | Method | 함수 | 권한 |
|---|---|---|---|
| `/api/admin-portal/health` | GET | `health` | 없음(PII 없음, 조회전용) |
| `/api/admin-portal/reservations` | GET | `list_reservations` | `reservation:view` |
| `/api/admin-portal/reservations/{reservation_no}` | GET | `get_reservation` | `reservation:view` |
| `/api/admin/dashboard` | GET | `dashboard` | `dashboard:view` |
| `/api/admin/statistics` | GET | `statistics` | `statistics:view` |
| `/api/admin/consultations` | GET | (목록) | `crm:manage`/`crm:log`/`audit:view` |
| `/api/admin/consultations/{id}/status` | POST | (상태변경) | `crm:manage` |
| `/api/admin/reservations/{reservation_no}/approve` | POST | `approve_reservation` | `reservation:approve` + CSRF |
| `/api/admin/reservations/{reservation_no}/reject` | POST | `reject_reservation` | `reservation:approve` + CSRF |

권한 검사는 `_build_require_permission(data_dir, *perms)`(`src/api/routes_admin_portal.py` L67)로 구현됨(**CURRENTLY CONFIRMED**). 승인/거절 외 예약변경/취소/검진완료/메모저장에 대응하는 Sheets 기준 엔드포인트는 **NOT IMPLEMENTED**(Legacy Portal이 GAS를 직접 호출, Security Architecture Design §4/§9 재확인).

`request_id`/`correlation_id` 개념은 `src/auth/auth_service.py`의 로그인 흐름 인자로만 **CURRENTLY CONFIRMED**되며, Admin Operations API 응답 필드로는 **NOT IMPLEMENTED**. Idempotency Key 저장 로직, Rate Limit 미들웨어는 저장소 전체에서 **NOT IMPLEMENTED**(grep 재확인, 매치 0건).

## 6. TO-BE Admin Operations API 호출 경로

```
관리자 브라우저 → FastAPI(세션+CSRF+RBAC) → Admin Operations Service
  → [상태변경만] HMAC 서명(ADR-017 §12) → GAS(서명검증) → Google Sheets
  → [조회만] 기존 sheets_readonly_service 경유(HMAC 미적용, ADR-017 §18)
```
이 흐름은 §7에서 제안하는 신규 Operation(§16-19)에도 동일하게 적용된다(**PROPOSED**, 미구현).

## 7. 시스템·구성요소별 책임 경계

| 구성요소 | 책임 | 비책임 |
|---|---|---|
| FastAPI Route | 세션/CSRF/RBAC 검증, 요청 스키마 검증, Operation→GAS action 매핑 고정 | 상태전이 규칙 정의(State Transition Matrix 참조), Sheets 직접 접근 |
| FastAPI Service(`sheets_write_service.py` 확장 예정) | HMAC 서명 생성(**PROPOSED**), Nonce/Idempotency 관리(**PROPOSED**) | GAS 코드 |
| GAS(`sheets_api_v3_final.gs`) | 서명 검증(**PROPOSED**), Sheets 쓰기, LockService 임계구역 | 호출자 신원 판단(FastAPI가 이미 검증했다는 전제) |
| Google Sheets | SSOT(ADR-013) | 없음 |

## 8. 공통 API 계약 원칙

- 모든 상태변경 Operation은 §23(GAS 서명 요청 계약)을 따른다.
- 클라이언트가 GAS action, 열 번호, 시트명, 임의 필드 목록을 지정할 수 없다(서버측 화이트리스트 고정, ADR-017 원칙 재확인).
- 조회 Operation은 HMAC 미적용, FastAPI 세션+RBAC만으로 보호(ADR-017 §18, DR-B-05 확정 재인용).
- HTTP 200과 업무 성공을 분리 판정한다(GAS가 항상 200을 반환한다고 공식 보장되지 않음, Security Architecture Design §11 재인용).

## 9. 인증 계약

- 관리자: FastAPI 세션(HttpOnly/Secure/SameSite=Lax, Sprint8 Commit8-2 **CURRENTLY CONFIRMED**).
- 서버간(FastAPI→GAS): HMAC-SHA256(**PROPOSED**, ADR-017 §12, `Utilities.computeHmacSha256Signature` GAS 공식 지원 확인됨).
- 공개 예약(`create`): 인증 없음(의도된 설계, 이 문서 대상 아님).

## 10. 인가 및 RBAC 계약

기존 역할 5종(`ROLE-DIRECTOR`/`ROLE-ADMIN`/`ROLE-STAFF`/`ROLE-CRM`/`ROLE-AI-AGENT`, `data/roles.json` **CURRENTLY CONFIRMED**, PII 없음). 상세 역할×Operation 매핑은 **RBAC Permission Matrix(후속 문서)로 위임**한다. 이 문서는 각 Operation의 필요 권한 "문자열"만 표기하며 담당 부서 배정(STEP1§24-3, DEFERRED)은 확정하지 않는다.

## 11. 공통 요청 헤더

GAS는 커스텀 HTTP 헤더를 지원하지 않는다(공식 확인, ADR-017 §3/§10 재인용). 따라서 서명 관련 필드는 **요청 본문 또는 쿼리스트링**으로 전달한다(§23). FastAPI 자체 요청(브라우저→FastAPI 구간)은 기존 세션 쿠키+CSRF 헤더(Commit8-2 기존 패턴)를 그대로 사용한다.

## 12. 공통 요청 본문 규칙

- JSON, UTF-8, 알 수 없는 필드 거부(`extra` forbid 원칙, ADR-017 §11 재인용)
- Operation별 필수/선택 필드는 §15-19 각 계약에서 정의
- 관리자 전용 필드(상태/비용/결과 등)는 공개 API 스키마에 애초에 정의하지 않음(수검자 create와 명확히 분리)

## 13. 공통 응답 구조

ADR-017 §12 정의를 그대로 인용(**PROPOSED**, 미구현):

| 필드 | 형식 | 정상 | 오류 |
|---|---|---|---|
| `protocolVersion` | 문자열 | 포함 | 포함 |
| `requestId` | UUID | 포함 | 포함 |
| `operation` | Operation ID | 포함 | 포함 |
| `ok` | boolean | true | false |
| `code` | 문자열 | "OK" | 오류코드(§14) |
| `message` | 문자열 | - | 일반화된 메시지만 |
| `retryable` | boolean | - | 포함 |
| `data` | 객체(마스킹됨) | 포함 | - |
| `serverTimestamp` | Unix seconds | 포함 | 포함 |

## 14. 오류 응답과 오류 코드 체계

ADR-017 §12의 19개 오류코드 범주를 그대로 인용(**PROPOSED**): `AUTH_FAILED`/`UNKNOWN_KEY_ID`/`SIGNATURE_MISMATCH`/`TIMESTAMP_EXPIRED`/`TIMESTAMP_FUTURE`/`NONCE_REPLAYED`/`NONCE_STORE_FAILED`/`IDEMPOTENCY_CONFLICT`/`IDEMPOTENCY_IN_PROGRESS`/`VALIDATION_FAILED`/`PERMISSION_DENIED`/`NOT_FOUND`/`INVALID_TRANSITION`/`LOCK_TIMEOUT`/`QUOTA_EXCEEDED`/`SERVER_ERROR`/`PARTIAL_FAILURE`/`RECONCILIATION_REQUIRED`/`PROTOCOL_VERSION_MISMATCH`. 현재 구현된 오류 응답(`routes_admin_portal.py`의 `HTTPException(403/404/409/502/503,...)`)은 **CURRENTLY CONFIRMED**이나 위 코드 체계와는 아직 통합되지 않았다(**PROPOSED** 통합).

## 15. 예약 상태 조회 계약

| 항목 | 값 |
|---|---|
| Operation ID | OP-RSV-LIST / OP-RSV-DETAIL |
| 현재 구현 여부 | **CURRENTLY CONFIRMED**(`GET /api/admin-portal/reservations`, `/{reservation_no}`) |
| 목표 HTTP Method | GET(변경 없음) |
| 목표 Path | 현행 유지(변경 없음) |
| 호출 주체 | 관리자 브라우저(FastAPI 경유) |
| 필요 인증 | FastAPI 세션(**CURRENTLY CONFIRMED**) |
| 필요 Permission | `reservation:view`(**CURRENTLY CONFIRMED**) |
| Query Parameter | `status`/`dateFrom`/`dateTo`/`search`/`sortBy`/`sortDir`/`page`/`pageSize`(**CURRENTLY CONFIRMED**) |
| 성공 HTTP Status | 200 |
| 성공 응답 | 마스킹된 예약 목록/상세(**CURRENTLY CONFIRMED**, `pii_mask.build_masked_reservation`) |
| 오류 HTTP Status | 503(미설정)/502(오류)/404(대상없음) |
| 감사 이벤트 | **NOT IMPLEMENTED**(조회 자체의 감사 여부 미확인) |
| 멱등성 | 해당없음(GET, 부작용 없음) |
| GAS 호출 여부 | 예(`sheets_readonly_service`, 서버간, **CURRENTLY CONFIRMED**) |
| 개인정보 포함 여부 | 마스킹된 형태만(**CURRENTLY CONFIRMED**) |
| DEFERRED 항목 | 없음 |
| 구현 예정 Commit | 해당없음(이미 구현됨, 변경 불필요) |

## 16. 예약변경(일정변경) 계약

| 항목 | 값 |
|---|---|
| Operation ID | OP-RSV-RESCHEDULE |
| 현재 구현 여부 | **NOT IMPLEMENTED**(Sheets 기준 대응 없음, Legacy Portal은 상태 라벨만 변경) |
| 목표 HTTP Method | POST(**PROPOSED**) |
| 목표 Path | `/api/admin/reservations/{reservation_no}/reschedule`(**PROPOSED**, 미확정) |
| 호출 주체 | 관리자 브라우저(FastAPI 경유, **PROPOSED**) |
| 필요 인증 | FastAPI 세션 + HMAC(GAS 구간, **PROPOSED**) |
| 필요 Permission | `reservation:change`(기존 `data/roles.json` 정의 재사용 제안, ROLE-STAFF에 이미 존재하나 현재 어떤 라우트도 검사하지 않음 — **CURRENTLY CONFIRMED as 미사용 정의**) |
| Request Body | 신규 희망일/희망시간(**PROPOSED** 필드) |
| 필수 입력값 | 미확정(허용 시점/횟수/당일여부, **DEFERRED** — companion#1/#2/#3, STEP1§24-1) |
| 허용 상태 | State Transition Matrix 확정 필요(**DEFERRED**) |
| 목표 상태 | 미확정(RESCHEDULED 별도상태 여부 자체가 DEFERRED, STEP1§24-1) |
| 상태 전이 규칙 참조 | **후속 State Transition Matrix 확정 후 이 계약을 갱신**(이번 문서에서 발명하지 않음) |
| 감사 이벤트 | `RESERVATION_RESCHEDULED`(**PROPOSED** 이벤트명, 미구현) |
| 멱등성 적용 | 예(Idempotency Key, **REQUIRES LOAD TEST** — DR-B-02) |
| GAS 호출 여부 | 예(`update` action 재사용 제안, 신규 action 아님) |
| Slot 영향 | 미확정(재배정 알고리즘, **DEFERRED** — companion#7/D11) |
| DEFERRED 항목 | companion#1/#2/#3, STEP1§24-1, companion#7(재배정) |
| 구현 예정 Commit | Commit8-3d |

## 17. 예약취소 계약

| 항목 | 값 |
|---|---|
| Operation ID | OP-RSV-CANCEL |
| 현재 구현 여부 | **NOT IMPLEMENTED**(Sheets 기준) |
| 목표 HTTP Method | POST(**PROPOSED**) |
| 목표 Path | `/api/admin/reservations/{reservation_no}/cancel`(**PROPOSED**, 미확정) |
| 필요 Permission | `reservation:cancel`(`data/roles.json`에 이미 정의, 미사용 — **CURRENTLY CONFIRMED as 미사용 정의**) |
| Request Body | `reason`(취소사유, **필수** — ADR-017 §21 확정) |
| 허용 상태 | State Transition Matrix 확정 필요 |
| 목표 상태 | `예약취소` |
| 감사 이벤트 | `RESERVATION_CANCELLED`(**PROPOSED**) |
| 멱등성 적용 | 예(**REQUIRES LOAD TEST**) |
| GAS 호출 여부 | 예(`updateStatus` action 재사용) |
| Slot 영향 | **Slot 반환 원칙 확정(ADR-017 §22), 세부규칙(즉시/유예) DEFERRED**(companion#7/D11) — `reservedCount` 결함 수정은 Commit8-3d |
| DEFERRED 항목 | companion#7 세부규칙 |
| 구현 예정 Commit | Commit8-3d |

## 18. 검진완료 처리 계약

| 항목 | 값 |
|---|---|
| Operation ID | OP-RSV-COMPLETE |
| 현재 구현 여부 | **NOT IMPLEMENTED** |
| 목표 HTTP Method | POST(**PROPOSED**) |
| 목표 Path | `/api/admin/reservations/{reservation_no}/complete`(**PROPOSED**) |
| 필요 Permission | `reservation:complete`(**신설 제안, 저장소에 존재하지 않음** — ADR-017 §20, STEP1§24-2) |
| 허용 상태 | `예약확정`만(선행상태 제한, ADR-017 §21 확정 원칙) — 상세는 State Transition Matrix |
| 목표 상태 | `검진완료`(취소·복원 불가, ADR-017 §21 확정) |
| 감사 이벤트 | `RESERVATION_COMPLETED`(**PROPOSED**) |
| 멱등성 적용 | 예(**REQUIRES LOAD TEST**) |
| GAS 호출 여부 | 예(`updateStatus` action 재사용, 기존 검진종료 타임스탬프 부수효과 코드 존재 — **CURRENTLY CONFIRMED**, GAS `_actionUpdateStatus` L409-411) |
| DEFERRED 항목 | 담당부서(STEP1§24-3) |
| 구현 예정 Commit | Commit8-3d |

## 19. 관리자 메모 처리 계약

| 항목 | 값 |
|---|---|
| Operation ID | OP-RSV-NOTE |
| 현재 구현 여부 | **NOT IMPLEMENTED**(Sheets 기준 서버 경유 없음, Legacy Portal이 GAS `update` 직접 호출) |
| 목표 HTTP Method | POST(**PROPOSED**) |
| 목표 Path | `/api/admin/reservations/{reservation_no}/note`(**PROPOSED**) |
| 필요 Permission | `reservation:note`(**신설 제안**, ADR-017 §20) |
| Request Body | `note`만(화이트리스트 고정, Legacy Portal의 기존 `_buildNotePayload(note){return{note}}` 패턴과 동일 원칙 재사용) |
| 목표 상태 | 상태 불변(메모저장은 상태전이와 분리, ADR-017 §14/§23 원칙 재인용) |
| 감사 이벤트 | `RESERVATION_NOTE_UPDATED`(**PROPOSED**) |
| GAS 호출 여부 | 예(`update` action 재사용, `note` 필드만) |
| 개인정보 포함 여부 | 메모 내용에 PII 포함 가능성 있어 감사로그는 요약만(Security Architecture Design §14 재인용) |
| 구현 예정 Commit | Commit8-3d |

## 20. 상태 전이 검증 계약

- 현재 확인된 상태값 6종(**CURRENTLY CONFIRMED**, GAS `<option>` 및 코드): `예약접수/예약확정/검진완료/일정변경/예약취소/거절`.
- ADR-016/017의 확정 불변조건: 취소사유 필수, 검진완료 종결(취소·복원 불가), 상태전이는 서버측 검증 필수(GAS `_actionUpdateStatus`는 현재 검증 없음 — **CURRENTLY CONFIRMED as 미검증**, ADR-016 companion §5-1 항목4).
- **이 문서는 API가 State Transition Matrix를 참조해야 한다는 계약만 기록**하며, 상세 허용 전이표는 후속 문서에서 확정한다(작성 원칙 준수, 새로 발명하지 않음).
- 허용되지 않은 전이는 `INVALID_TRANSITION`으로 거부한다(§14 오류코드 재인용).

## 21. 멱등성 및 중복 요청 방지

ADR-017 §14(Idempotency 5상태·TTL: `IN_PROGRESS` 60초/`SUCCEEDED` 900초/`FAILED_RETRYABLE` 300초/`FAILED_FINAL` 900초/`UNKNOWN` 48시간)를 그대로 인용(**PROPOSED**, **REQUIRES LOAD TEST** — DR-B-02). 현재 저장소에 Idempotency 저장 로직은 **NOT IMPLEMENTED**(grep 재확인).

## 22. 동시성·버전 충돌 처리

- GAS `LockService.getScriptLock()`으로 쓰기 자체는 직렬화되나(**CURRENTLY CONFIRMED**, 기존 `_actionCreate`/`_actionUpdateStatus`), "다른 사용자가 이미 다른 상태로 바꿨다"는 낙관적 잠금(compare-and-swap)은 **NOT IMPLEMENTED**(ADR-016 companion §6 재확인).
- Stale update 탐지(버전 필드 등)는 이 문서에서 신규 설계하지 않으며 **Open Question**(§34)으로 남긴다.

## 23. GAS 서명 요청 계약

ADR-017 §12 Canonical String을 그대로 인용(**PROPOSED**):
```
CMC-HMAC-SHA256
1
POST
<operation>
<timestamp>
<nonce>
<idempotencyKey>
<payloadHash>
```
GAS는 커스텀 헤더를 지원하지 않으므로 서명 필드는 본문/쿼리스트링으로 전달한다(§11 재인용). `Utilities.computeHmacSha256Signature()`가 GAS에서 공식 지원됨을 재확인(ADR-017 §10 출처 인용).

## 24. 입력값 검증 및 정규화

- 알 수 없는 필드 거부(§12)
- Operation별 필수 필드만 GAS 전달(§16-19)
- 상세 자료형·길이·정규식 규칙은 이 문서에서 확정하지 않으며 구현 단계(Commit8-3b/8-3d)의 Pydantic 스키마로 위임(**Open Question**, §34)

## 25. 감사로그 계약

- 저장 위치: `data_dir / "audit_logs.json"`(append-only, **CURRENTLY CONFIRMED**)
- 함수: `src/reservation/reservation_audit.py::append_audit()`(**CURRENTLY CONFIRMED**, 재사용 대상, 신규 구현 아님)
- 신규 이벤트 타입(`RESERVATION_RESCHEDULED`/`RESERVATION_CANCELLED`/`RESERVATION_COMPLETED`/`RESERVATION_NOTE_UPDATED`/`NONCE_ISSUED`/`NONCE_REPLAYED`/`HMAC_VERIFICATION_FAILED` 등)은 **PROPOSED**, Commit8-3b/8-3d에서 구현
- Secret·서명 원문·PII 원문 미기록(ADR-017 §19 원칙 재인용)

## 26. 개인정보·Secret·민감정보 보호

- 조회 응답은 `pii_mask.build_masked_reservation()`으로 마스킹(**CURRENTLY CONFIRMED**)
- Secret은 FastAPI 환경변수 + GAS `PropertiesService`(**PROPOSED**, ADR-017 §13/§9)
- 이 문서의 모든 JSON 예시는 가상값만 사용(§10 지시 준수, 실제 예시는 §31 요약표에서 최소한으로 제공)

## 27. Rate Limit 및 남용 방지 원칙

Rate Limit 구체값은 **DEFERRED**(STEP1§24-4, 실측 트래픽 데이터 부재). 현재 저장소에 Rate Limit 미들웨어는 **NOT IMPLEMENTED**(grep 재확인, 매치 0건). GAS 자체 쿼터(동시실행 1,000/스크립트, 공식 확인)를 초과하지 않도록 FastAPI 계층 통제를 목표로 하나 구체 임계치는 확정하지 않는다.

## 28. Timeout·재시도·부분 실패 처리

ADR-017 §16(재시도 최대 3회, 지수 백오프+Jitter)과 STEP2-B §14(30개 장애시나리오)를 인용(**PROPOSED**). 불확실 성공 상태(`UNKNOWN`/`RECONCILIATION_REQUIRED`)는 자동 재시도 금지, 운영자 수동 확인 필수(Security Architecture Design §23 재인용).

## 29. Slot 반환 및 부수효과 처리

취소 시 Slot `reservedCount` 반환을 원칙으로 채택(ADR-017 §22 확정)하되, **즉시반환/유예/재배정 세부규칙은 DEFERRED**(companion#7, D11 관련성만 표시, 병합 안 함). `reservedCount` 정합성 결함(현재 미반환, ADR-016 companion §15 Risk#3 Critical) 수정은 **이 문서에서 다루지 않으며 Commit8-3d 범위**로 명확히 유지한다.

## 30. 관측성 및 요청 추적

`requestId`는 ADR-017 §12 응답계약 필드로 **PROPOSED**(§13 인용). 현재 `request_id` 개념은 `auth_service.py` 로그인 흐름에만 존재(§5 재확인, Admin Operations API 응답에는 미구현). Correlation ID를 이용한 FastAPI-GAS 간 요청 추적 연계는 **NOT IMPLEMENTED**, 이 문서에서 신규 설계하지 않고 **Open Question**(§34)으로 남긴다.

## 31. API별 계약 요약표

| Operation ID | 목적 | 현재구현 | Method | 상태전이참조 | 멱등성 | GAS action | DEFERRED |
|---|---|---|---|---|---|---|---|
| OP-RSV-LIST | 목록조회 | CURRENTLY CONFIRMED | GET | 해당없음 | 해당없음 | list | 없음 |
| OP-RSV-DETAIL | 상세조회 | CURRENTLY CONFIRMED | GET | 해당없음 | 해당없음 | get | 없음 |
| OP-RSV-APPROVE | 승인 | CURRENTLY CONFIRMED | POST | 기존 구현(예약접수→예약확정) | 아니오(현재) | updateStatus | 없음 |
| OP-RSV-REJECT | 거절 | CURRENTLY CONFIRMED | POST | 기존 구현(예약접수→거절) | 아니오(현재) | updateStatus | 없음 |
| OP-RSV-RESCHEDULE | 일정변경 | NOT IMPLEMENTED | POST(PROPOSED) | Matrix 확정 필요 | REQUIRES LOAD TEST | update(제안) | companion#1/2/3, STEP1§24-1, companion#7 |
| OP-RSV-CANCEL | 취소 | NOT IMPLEMENTED | POST(PROPOSED) | Matrix 확정 필요 | REQUIRES LOAD TEST | updateStatus(제안) | companion#7 세부규칙 |
| OP-RSV-COMPLETE | 검진완료 | NOT IMPLEMENTED | POST(PROPOSED) | Matrix 확정 필요(선행상태=예약확정) | REQUIRES LOAD TEST | updateStatus(제안) | STEP1§24-3 |
| OP-RSV-NOTE | 메모저장 | NOT IMPLEMENTED | POST(PROPOSED) | 해당없음(상태불변) | REQUIRES LOAD TEST | update(제안) | 없음 |

가상 요청 예시(개인정보 미포함, 자리표시자만):
```json
{
  "operation": "OP-RSV-CANCEL",
  "payload": { "reservationNo": "20260101-0001", "reason": "SAMPLE_REASON" }
}
```

## 32. 보안 위협과 통제 매핑

Security Architecture Design §21 표를 그대로 인용하며 중복 재정의하지 않는다. 이 문서 고유 매핑만 추가:

| 위협 | 이 문서의 통제 |
|---|---|
| 클라이언트가 임의 필드로 관리자 필드 위조 | §12 화이트리스트 고정 원칙 |
| 상태전이 우회(임의 상태 지정) | §20 Matrix 참조 강제(이 문서는 규칙 미확정) |
| Slot 이중 반환 | §29 Idempotency 결합(REQUIRES LOAD TEST) |

## 33. DEFERRED·PoC·부하검증 의존사항

**DEFERRED(정책, ADR-017 §30 원문 인용)**: companion#1/#2/#3(변경 시점/횟수/당일), companion#7(Slot 세부규칙), STEP1§24-1(RESCHEDULED 상태), STEP1§24-3(담당부서). (companion#8/#10, STEP1§24-4는 이 문서의 Operation 계약과 직접 관련 없어 §31 요약에서 제외, Security Architecture Design §23에서 전체 8건 관리)

**REQUIRES POC(DR-B-01, ADR-017 §29 원문 인용)**: FastAPI SQLite UNIQUE 제약 원자성 실측, GAS CacheService eviction 시뮬레이션, 저장소 정합성 불일치 처리 검증.

**REQUIRES LOAD TEST(DR-B-02)**: Idempotency TTL 부하검증(§21).

## 34. Open Questions

- Stale update(낙관적 잠금) 탐지 방식 미정(§22)
- 입력값 상세 검증 규칙(정규식·길이 등)을 이 문서에서 정의할지 구현 단계 스키마로 위임할지(§24) — **구현 단계 위임으로 잠정 제안, 확정 아님**
- FastAPI-GAS 간 Correlation ID 연계 설계 여부(§30)
- §14 오류코드 체계를 기존 `routes_admin_portal.py`의 `HTTPException` 패턴과 어떻게 통합할지

## 35. 후속 문서와 구현 Commit 경계

| 후속 작업 | 이 문서가 제공하는 입력 | 경계 |
|---|---|---|
| State Transition Matrix | §20의 상태값 6종·불변조건, §16-19의 "허용 상태" 자리표시자 | 전이 상세 규칙은 그 문서가 확정 |
| RBAC Permission Matrix | §10·§16-19의 필요 Permission 문자열 후보 | 역할×Operation 매핑은 그 문서가 확정 |
| Commit8-3b | §13-14(응답계약)·§21(Idempotency)·§23(HMAC) 설계 | PoC(§33)·부하검증(§33) 선행 |
| Commit8-3d | §16-19 Operation 4종 실제 구현, §29 `reservedCount` 수정 | State/RBAC Matrix 확정 후 |

## 36. 완료 기준

36개 섹션 전부 작성, ADR-016/017/실행계획 추적성 명시, DEFERRED·PoC·부하검증 미확정 유지, 구현완료 오인 문구 없음, PII·Secret 미포함을 완료 기준으로 한다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 ADR-016·ADR-017·`Sprint8_Security_Architecture_Design.md`를 포함한 어떤 기존 파일도 수정하지 않았다. 코드 구현 없음. 상태전이·RBAC 상세 미확정. DEFERRED 8건 중 관련분 미확정 유지. PoC·부하검증 결과 추정 없음. 실제 Secret·서명·Nonce·운영 URL·개인정보 미포함. Git add/commit/push 없음.
