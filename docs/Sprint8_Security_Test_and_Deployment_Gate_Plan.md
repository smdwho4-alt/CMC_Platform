# Sprint8 Security Test and Deployment Gate Plan

> **상태**: 설계 계획 초안(Draft). 테스트는 실행하지 않았다. 정책·PoC·부하검증 미확정 사항은 그대로 미확정 유지한다. 승인권자·담당부서는 임의 지정하지 않는다. Commit 없음.
> **작성일**: 2026-08-18(Sprint8 Commit8-3a STEP 3-E-A)
> **기준선**: `main`/`origin/main` = `c360e22066802847e6b25456f26d79c890d5e946`

---

## 1. 문서 목적

Commit8-3a에서 확정된 4개 설계문서(ADR-017, Security Architecture Design, Admin Operations API Contract, State Transition Matrix, RBAC Permission Matrix)의 보안 요구사항을 **검증 가능한 테스트**와 **배포 Gate**로 연결한다. 이 문서는 새로운 보안 요구사항을 발명하지 않으며, 선행 문서가 이미 확정한 내용만 테스트 관점으로 재구성한다. 실제 테스트 코드 작성이나 실행은 포함하지 않는다.

## 2. 적용 범위와 제외 범위

**적용 범위**: 관리자 브라우저-FastAPI-GAS-Google Sheets 경로의 인증·인가·HMAC 전송보안·상태전이·Idempotency·감사로그·Slot 정합성에 대한 테스트 계획, 그리고 Commit8-3b/8-3d 구현부터 운영 배포까지의 Gate(G0~G9) 정의.

**제외 범위**:
- 실제 테스트 코드 작성·실행(이번 STEP은 계획서만)
- DR-B-01 PoC 3건, DR-B-02 부하검증의 실제 수행(계획만 기술, 결과 없음)
- 정책 미결정 사항(companion#1/#2/#3/#8/#10, STEP1§24-1/§24-3/§24-4)의 확정
- Commit8-3b/8-3d의 실제 코드 구현
- Legacy Portal 업무 규칙 자체(ADR-016 범위, 이 문서는 그 규칙이 안전하게 검증되는 방법만 다룸)
- Netlify/GAS/FastAPI 실제 배포, Production Publish

## 3. 기준선 Commit

`c360e22066802847e6b25456f26d79c890d5e946`(HEAD=main=origin/main, STEP3-D-P 완료 시점).

## 4. 선행 문서

| 문서 | 상태 | 이 문서와의 관계 |
|---|---|---|
| `ADR-016_Legacy_Stage3_PhaseB_Transition_Design_Draft.md` | Proposed | 3개 전이 업무규칙(RESCHEDULE/CANCEL/COMPLETE) 출처 |
| `ADR-017_FastAPI_Proxy_and_Signed_GAS_Operations.md` | Accepted with Conditions | HMAC/Nonce/Idempotency/오류코드/Gate C1~C6 출처 |
| `docs/Sprint8_Security_Architecture_Design.md` | Draft | 신뢰경계·위협통제매핑(§21) 출처 |
| `docs/Sprint8_Admin_Operations_API_Contract.md` | Draft | 8개 Operation 계약·오류코드 19종 출처 |
| `docs/Sprint8_State_Transition_Matrix.md` | Draft | 상태전이 Matrix, CMC.STATUS_LIST Gap 출처 |
| `docs/Sprint8_RBAC_Permission_Matrix.md` | Draft | 역할×Operation Permission 출처 |
| `docs/Sprint8_Admin_Authentication_Authorization_Design_and_Threat_Model.md` | Commit8-1 | Threat Model T01~T33, 기존 Test ID(AUTH/SESS/CSRF/AUTHZ/GASAUTH/AUDIT/REGR) 출처 |
| `docs/Sprint8_Commit8_2_Admin_Authentication_Implementation_Report.md` | Commit8-2 | 실제 구현 범위, 기존 검증 결과(FC-01/02, MOCKCSRF 1~16, AUTH-01~) 출처 |
| `Legacy_Stage3_PhaseB_Design_v1.0.md` | ADR-016 companion | Risk Register, Decision ID companion#1~10 출처 |
| `docs/Sprint8_Security_and_Pilot_Readiness_Execution_Plan.md` | Commit8-0 | D6~D9/D11/D27 출처(별도 ID체계, 병합 안 함) |

## 5. 코드 및 테스트 근거

| 파일 | 확인 내용 |
|---|---|
| `src/api/routes_admin_portal.py` | `_build_require_permission`(L67), APPROVE/REJECT 실제 구현(L699-789), L703 "GAS updateStatus는 compare-and-swap을 지원하지 않으므로" 주석(CAS 부재 명시적 인정), Slot Rollback(`_safe_rollback_slot`, L739-748) |
| `src/api/api_server.py` | 로컬 JSON 도메인 `need_perm`, `/api/reservations/{rid}/*`(미사용 경로, RSV- 접두) |
| `src/reservation/reservation_engine.py` | `_has_permission()`(L64-70), `reservation:cancel` 실제 시행(L449, 로컬 JSON 도메인 한정) |
| `src/reservation/reservation_audit.py` | `append_audit()`, `AUDIT_EVENTS` 화이트리스트(L18-32) — **재확인**: `RESERVATION_CANCELLED`/`RESERVATION_COMPLETED`는 이미 존재(Sprint B 로컬 JSON 도메인 목적). `RESERVATION_RESCHEDULED`/`RESERVATION_NOTE_UPDATED`/`NONCE_ISSUED`/`NONCE_REPLAYED`/`HMAC_VERIFICATION_FAILED`/`TIMESTAMP_EXPIRED`/`IDEMPOTENCY_CONFLICT`는 화이트리스트에 **없음**(신규 추가 필요, Commit8-3b/8-3d 대상) |
| `src/auth/service_hmac.py` | **신규 확인 사실**: HMAC 서명 유틸리티(`canonical_string`/`hash_body`/`sign_request`/`verify_signature`)가 이미 코드로 존재함(Commit8-2 산출물, GAS 미배선). **중요 불일치**: 이 파일의 Canonical String 순서(`method\naction\ntimestamp\nnonce\nbody_hash`)는 ADR-017 §12가 이후(Commit8-3a STEP2-B/D) 확정한 Canonical String(`CMC-HMAC-SHA256\n1\n<Method>\n<operation>\n<timestamp>\n<nonce>\n<idempotencyKey>\n<payloadHash>`, `protocolVersion`/`idempotencyKey` 필드 포함)과 **형식이 다르다** — `idempotencyKey` 필드가 이 유틸리티에 없다. 이 문서는 이 불일치를 §8에 Gap으로 기록하며 임의로 어느 한쪽을 수정하지 않는다 |
| `data/roles.json` | 5개 역할, 18개 Permission 문자열, `containsPII:false` |
| `app/apps_script/sheets_api_v3_final.gs` | `doGet`/`doPost` 인증·인가 코드 0건, `_actionUpdateStatus`(이전 상태 미검증), `LockService` 사용(직렬화만, CAS 아님) |
| `app/pages/admin_reservations_v2_new.html` | L63/L139 상태 드롭다운(6종), L220 `_buildNotePayload`, L372 `updateStatus` 호출 |
| `app/services/google_sheets_service_v2_new.js` | `CMC_SheetsServiceV2.updateStatus()` — GAS 직접 호출 |
| `app/data/programs_data_new.js` | L90 `CMC.STATUS_LIST`(5종, "거절" 누락 — State Transition Matrix §6/§34 기 확인 Gap) |
| `src/security/rate_limit.py` | `SlidingWindowRateLimiter`(프로세스 메모리 기반, AI 채팅용 `CSHSP_CHAT_RATE`) — **로그인/Admin Operations API에는 적용되지 않음**(재확인, import 경로가 `routes_agents.py`/`ai_metrics.py`뿐) |
| `tests/run_sprint8_commit8_2_admin_authentication_qa.py` + `tests/sprint8_commit8_2_admin_authentication_test_result.csv` | 62개 항목(AUTH/SESS/CSRF/AUTHZ 등), 전부 PASS(재확인, 파일 62줄 중 헤더 포함) |
| `tests/run_sprint8_commit8_2b_auth_hardening_verification_qa.py` + `tests/sprint8_commit8_2b_auth_hardening_verification_test_result.csv` | FC-01/02 등 Fail-Closed 검증 13항목, 전부 PASS(재확인) |
| `tests/run_sprint8_commit8_2c_mock_write_block_qa.py` + `tests/sprint8_commit8_2c_mock_write_block_test_result.csv` | Mock 차단 16개 시나리오(X-User-Id 위조, roleId 위조, GAS/SQLite 호출횟수 계측 포함), 전부 PASS(재확인) |
| `netlify.toml` | 빌드 설정(`publish="."`)과 보안 헤더만 확인, Git Push 반응형 CI 파이프라인 정의는 저장소 내 확인 불가(Threat Model §55 재확인, 이번 STEP에서 재검색해도 `.github/workflows/` 디렉터리 자체가 없음을 확인) |
| grep 재확인(`nonce`/`idempotenc`) | `src/` 전체에서 `src/auth/service_hmac.py` 1개 파일만 매치(docstring상 "Nonce 저장소는 Commit8-3 설계 대상"이라는 문구뿐, 저장 로직 없음) — Idempotency/Nonce 저장 로직 **NOT IMPLEMENTED** 재확인 |

## 6. 판정 라벨

문서 전반: `CURRENTLY CONFIRMED`/`PROPOSED`/`NOT IMPLEMENTED`/`DEFERRED`/`NOT FOUND`(선행 문서와 동일 정의 승계).

테스트 실행가능성 전용: `EXECUTABLE NOW`/`EXECUTABLE AFTER IMPLEMENTATION`/`REQUIRES POC`/`REQUIRES LOAD VALIDATION`/`REQUIRES POLICY DECISION`/`NOT APPLICABLE`.

## 7. 현재 보안 구현 요약

- **관리자 인증**: FastAPI 세션(Argon2id, SQLite, HttpOnly/Secure/SameSite=Lax) — **CURRENTLY CONFIRMED**(Commit8-2).
- **CSRF**: 세션 인증 상태변경 경로에만 적용, Mock 경로는 별도로 무조건 차단 — **CURRENTLY CONFIRMED**(Commit8-2c).
- **RBAC**: 기존 `has_perm`/`need_perm`/`_build_require_permission` 재사용, 신규 로직 없음 — **CURRENTLY CONFIRMED**.
- **X-User-Id Mock 격리**: `CSHSP_ENV`/`CSHSP_ALLOW_MOCK_AUTH` 이중 게이트, Fail-Closed — **CURRENTLY CONFIRMED**(FC-01/02 PASS).
- **HMAC**: 서명 유틸리티(`service_hmac.py`)만 존재, GAS 서명검증 미배선, ADR-017 최종 Canonical String과 형식 불일치(§5) — **PROPOSED 단계, 부분 코드 존재**.
- **Nonce/Idempotency/CAS**: 전부 **NOT IMPLEMENTED**(grep 재확인).
- **GAS 자체 인증**: 전무 — **CURRENTLY CONFIRMED as 부재**.
- **감사로그**: 기존 구조 재사용 가능하나 신규 이벤트 7종(§5) 미등록.

## 8. 주요 보안 Gap

1. GAS `doGet`/`doPost` 무인증(V1/V2/V4/V5, T13/T14) — Legacy Portal이 존속하는 한 잔존.
2. HMAC 미배선 + Canonical String 형식 불일치(`service_hmac.py` vs ADR-017 §12, §5 재확인 사실).
3. Nonce/Idempotency/CAS 전부 미구현.
4. `CMC.STATUS_LIST`(5종) vs Legacy 드롭다운(6종) 불일치 — 통계 집계에서 "거절" 누락 가능성(State Transition Matrix §6/§34 인용).
5. 신규 감사 이벤트 7종 미등록(§5).
6. `reservedCount` Slot 미반환 결함(ADR-016 companion §15 Risk#3 Critical, Commit8-3d 범위).
7. Rate Limit이 로그인·Admin Operations API에 미적용(§5 재확인).
8. Legacy Portal의 `approvalBlocked` UI 가드는 서버측 인가가 아님(우회 가능, RBAC Matrix §11 재인용).

## 9. 위협 및 통제 대상

Threat Model(`docs/Sprint8_Admin_Authentication_Authorization_Design_and_Threat_Model.md` §41) T01~T33과 Security Architecture Design §21 위협·통제·검증 매핑표를 그대로 인용하며 재정의하지 않는다. 이 문서가 신규로 연결하는 것은 각 위협의 **테스트 ID**(§13-26)와 **Gate**(§29-35)뿐이다. Critical 등급 중 T13/T14/T20/T21(Legacy 직접호출)은 Sprint8 범위에서 완전히 해결되지 않음을 재확인(Threat Model §42 재인용).

## 10. 테스트 계층과 환경

| 계층 | 목적 | 환경 |
|---|---|---|
| 단위(Unit) | 개별 함수(서명 계산, 상태전이 판정 등) | 로컬/CI, Mock 허용 |
| 통합(Integration) | FastAPI 라우트-서비스-GAS Fake Adapter 연계(`run_sprint8_commit8_2c_mock_write_block_qa.py`의 Fake Adapter 패턴 재사용 제안) | 로컬/CI, 실 네트워크 없음 |
| 보안(Security) | 인증/인가/HMAC/Replay/RBAC 우회 시도 | 로컬/CI 또는 Staging([확인 필요], Threat Model §44 재인용) |
| 성능/부하(Load) | Idempotency TTL, GAS CacheService eviction | **REQUIRES LOAD VALIDATION**, Staging 이상 권장 |
| 배포 후 Smoke | 실제 배포 환경에서 핵심 경로 확인 | Staging/운영, PM 승인 후 |

Staging 환경 자체의 존재 여부는 이 저장소 코드로 확인되지 않는다([확인 필요], Threat Model §44/§59 재인용) — 이 문서는 Staging 존재를 임의로 가정하지 않는다.

## 11. 테스트 데이터 원칙

모든 테스트는 합성(가상) 계정·예약 데이터만 사용한다(Commit8-2 검증 관행 재확인, §16 인용). 실제 수검자 개인정보, 실제 운영 URL, 실제 Secret은 어떤 테스트에도 사용하지 않는다. 테스트 데이터는 실제 스키마와 동일한 구조를 가지되 값은 전부 가상이어야 한다.

## 12. 개인정보·Secret 보호

- 테스트 로그·실패 메시지에 합성 데이터라도 실제와 혼동될 수 있는 값(실명 패턴, 실제 형식의 주민등록번호 등)을 사용하지 않는다.
- Secret은 테스트 전용 합성 문자열만 사용(`service_hmac.py` 기존 관행 재확인, §16 docstring 인용).
- 매 Commit 전 PII/Secret 정규식 검사 관행(세션 전체에서 이미 확립됨)을 이 문서가 정의하는 테스트에도 동일 적용.

## 13. 인증 테스트

Threat Model §46-A(AUTH-01~12)를 그대로 인용하며 재정의하지 않는다. 이 문서는 이미 §16(Commit8-2 검증 결과, §5 재확인 CSV)에서 대부분 **EXECUTABLE NOW이자 이미 PASS 확인됨**(재실행은 이번 STEP에서 하지 않음)으로 표시한다. 미실행 항목(AUTH-05/AUTH-12, "권장" 등급)은 §21 매트릭스에서 별도 상태로 표시.

## 14. 세션 테스트

Threat Model §46-B(SESS-01~11)를 그대로 인용. Cookie 속성(HttpOnly/Secure/SameSite) 확인은 응답 헤더 검사로 **EXECUTABLE NOW**, 세션 저장소 장애 시뮬레이션은 **EXECUTABLE AFTER IMPLEMENTATION**(현재 구현 완료 상태이므로 사실상 EXECUTABLE NOW이나 실제 장애 주입 도구 부재로 별도 확인 필요, §21 참조).

## 15. HMAC 서명 테스트

신규 정의(Test ID `HMAC-01~08`, §21 참조). `service_hmac.py`의 단위 함수(`sign_request`/`verify_signature`)는 **EXECUTABLE NOW**(로컬 함수 호출, GAS 불필요). GAS 서명검증 자체는 GAS 코드 미작성으로 **EXECUTABLE AFTER IMPLEMENTATION**(Commit8-3b). §5에서 발견한 Canonical String 형식 불일치는 HMAC-01(정상 서명 검증)이 어떤 형식을 기준으로 삼을지 **REQUIRES POLICY DECISION**(ADR-017 §12 최종형식 채택이 이미 확정이므로, 정확히는 `service_hmac.py`를 ADR-017 형식에 맞춰 갱신할지 여부의 구현 결정 — 이 문서는 결정하지 않음).

## 16. timestamp·nonce·replay 방지 테스트

신규 정의(Test ID `REPLAY-01~06`). Nonce 저장소(FastAPI SQLite 1차 + GAS CacheService 2차, ADR-017 §13)가 미구현이므로 전부 **EXECUTABLE AFTER IMPLEMENTATION**, 그중 저장소 동시성·eviction 관련 3건은 추가로 **REQUIRES POC**(DR-B-01 3건과 직접 대응, §40).

## 17. RBAC·Permission 테스트

Threat Model §46-D(AUTHZ-01~10, Admin Portal 경로 한정)를 인용하고, 이 문서는 **8개 Operation 전체**로 확장한다(신규 Test ID `RBAC-01~08`, Operation당 1개 이상, §21/§42 참조). LIST/DETAIL/APPROVE/REJECT는 **EXECUTABLE NOW**(구현 존재), RESCHEDULE/CANCEL/COMPLETE/NOTE는 권한 문자열 자체가 Sheets 도메인에 미시행이거나(RESCHEDULE/CANCEL) 저장소에 없음(COMPLETE/NOTE, RBAC Matrix §14 NOT FOUND 재인용)이므로 **EXECUTABLE AFTER IMPLEMENTATION**.

## 18. 직접 GAS 호출 차단 검증

신규 정의(Test ID `GASBYPASS-01~03`). 현재 GAS는 호출자를 구분하지 못하므로 이 테스트는 **Pass/Fail 판정용이 아니라 현황 기록용**(Threat Model GASAUTH-09와 동일 성격, 그대로 인용). HMAC 배선 완료 전까지는 항상 "차단 안 됨(위험 현존)"으로 기록되는 것이 정상이며, 이를 실패로 취급하지 않는다 — **EXECUTABLE NOW(현황 기록 목적), 판정 기준 자체는 REQUIRES POLICY DECISION 아님(이미 원칙 확정)**.

## 19. 상태 전이 허용·거부 테스트

신규 정의(Test ID `TRANS-01~06`). APPROVE/REJECT(예약접수→예약확정/거절)는 `assert_can_transition()`으로 이미 서버 검증되므로 **EXECUTABLE NOW**. RESCHEDULE/CANCEL/COMPLETE의 허용 from-state는 State Transition Matrix §11-19가 일부만 확정(COMPLETE의 선행상태=예약확정만 확정, RESCHEDULE는 **DEFERRED**)했으므로, COMPLETE 관련 전이 테스트는 **EXECUTABLE AFTER IMPLEMENTATION**, RESCHEDULE 관련은 **REQUIRES POLICY DECISION**(companion#1-3/STEP1§24-1 확정 전까지 허용 전이 자체를 정의할 수 없음). 잘못된 상태값 거부(TRANS-06)는 GAS가 현재 어떤 문자열이든 그대로 저장하므로(§5 L396 재확인) 도입 시 반드시 화이트리스트 검증이 필요함을 확인하는 **현황 기록용** 테스트다.

## 20. stale update·CAS 테스트

신규 정의(Test ID `CAS-01~03`). `routes_admin_portal.py` L703 주석이 CAS 부재를 코드로 직접 인정하고 있으므로(§5), 이 영역 전체가 **EXECUTABLE AFTER IMPLEMENTATION**이며 구현 설계 자체가 아직 없어 **REQUIRES POLICY DECISION** 요소도 포함한다(Admin Operations API Contract §22 Open Question 재인용 — 이 문서에서 CAS 방식을 새로 설계하지 않는다).

## 21. Idempotency 및 중복요청 테스트

신규 정의(Test ID `IDEM-01~05`). ADR-017 §14의 5상태 TTL을 그대로 인용하며 재정의하지 않는다. 저장 로직이 없으므로 전부 **EXECUTABLE AFTER IMPLEMENTATION**, TTL 수치 자체의 타당성 검증은 **REQUIRES LOAD VALIDATION**(DR-B-02).

## 22. 감사로그 테스트

Threat Model §46-F(AUDIT-01~07)를 인용. 기존 이벤트(`RESERVATION_APPROVED` 등)의 성공 기록은 **EXECUTABLE NOW**(승인 경로 한정). 신규 이벤트 7종(§5, `RESERVATION_RESCHEDULED`/`RESERVATION_NOTE_UPDATED`/`NONCE_ISSUED`/`NONCE_REPLAYED`/`HMAC_VERIFICATION_FAILED`/`TIMESTAMP_EXPIRED`/`IDEMPOTENCY_CONFLICT`)은 `AUDIT_EVENTS` 화이트리스트에 없어 **EXECUTABLE AFTER IMPLEMENTATION**(화이트리스트 추가가 선행되어야 `append_audit()` 호출 자체가 `ValueError` 없이 성공함, `reservation_audit.py` L55-56 재확인). Secret·PII 비노출 확인(AUDIT-04)은 기존 `_server_log()` PII-safe 원칙이 이미 있어 **EXECUTABLE NOW**(원칙 준수 여부 확인 관점).

## 23. 오류응답·정보노출 테스트

신규 정의(Test ID `ERR-01~04`). 현재 `api_server.py`가 `f"권한 없음: {perm} 필요 (현재 역할 ...)"`처럼 상세 정보를 그대로 반환하는 패턴이 있음(Threat Model §21 재인용) — 이는 ADR-017 §12/Security Architecture Design §16의 "일반화된 메시지만 노출" 원칙과 배치되므로 **EXECUTABLE NOW(AS-IS 확인용, 현재는 원칙 미준수 상태로 기록)**, 원칙 적용 후 재검증은 **EXECUTABLE AFTER IMPLEMENTATION**.

## 24. 입력값 검증 테스트

신규 정의(Test ID `INPUT-01~03`). 공개 예약(`create`)의 필드 화이트리스트는 기존 스키마로 **EXECUTABLE NOW**. 신규 Operation의 상세 검증규칙(정규식·길이 등)은 API Contract §24 Open Question(구현 단계 Pydantic 스키마 위임, 확정 아님)에 따라 **EXECUTABLE AFTER IMPLEMENTATION**.

## 25. Rate limit·timeout·retry 테스트

신규 정의(Test ID `RATE-01~04`). 기존 `SlidingWindowRateLimiter`는 로그인/Admin Operations API에 미적용(§5 재확인)이므로 로그인 Brute Force 방어(AUTH-05, Threat Model 재인용) 자체가 "권장(필수아님)"으로 남아있다. Rate Limit 구체값은 **REQUIRES POLICY DECISION**(STEP1§24-4, DEFERRED). Timeout(Admin Portal 8초, Commit5-3.2 기 확인)은 **EXECUTABLE NOW**(Admin Portal 경로 한정), Legacy/Reservation Portal은 Timeout 자체 없음(Threat Model T28 재인용, 이 문서에서 신규 대응 설계 안 함). 재시도(최대 3회)는 ADR-017 §16 확정값이나 구현 없음 — **EXECUTABLE AFTER IMPLEMENTATION**.

## 26. Slot 반환·재계산 검증

신규 정의(Test ID `SLOT-01~04`). GAS `_actionUpdateStatus`에 Slot 관련 코드가 전혀 없음을 재확인(State Transition Matrix §32 재인용) — 이 영역은 전부 **EXECUTABLE AFTER IMPLEMENTATION**이며, 세부규칙(즉시/유예/재배정) 자체가 **REQUIRES POLICY DECISION**(companion#7/D11, 병합하지 않고 관련성만 표시). 동시 요청 하에서의 Slot 경쟁 상태 테스트는 GAS `LockService` 직렬화는 이미 존재하므로(§5 재확인) 직렬화 자체의 **EXECUTABLE NOW** 확인과, CAS 부재로 인한 낙관적 잠금 실패 시나리오는 **EXECUTABLE AFTER IMPLEMENTATION**으로 분리한다.

## 27. 회귀테스트

Threat Model §46-G(REGR-01~10)를 인용하며, §5에서 재확인한 기존 3개 보안 테스트 스위트(`run_sprint8_commit8_2_admin_authentication_qa.py` 62항목, `..._2b_auth_hardening...` 13항목, `..._2c_mock_write_block...` 16항목, 전부 PASS)를 **REGR 그룹의 이미 존재하는 실행가능 자산**으로 명시한다 — **EXECUTABLE NOW**(재실행 자체는 이번 STEP에서 수행하지 않음, §37 준수). Commit8-3b/8-3d 구현 후에는 이 3개 스위트가 회귀 기준선으로 재사용되어야 한다(신규 스위트를 임의로 대체 설계하지 않음).

## 28. 정적분석·의존성·Secret 검사

- 매 Commit 전 PII/Secret 정규식 검사(세션 전체 기존 관행, 재확인) — **EXECUTABLE NOW**.
- 전용 자동 스캔 도구(SAST/의존성 스캐너)는 저장소에 존재 확인되지 않음(Threat Model T16 "자동 스캔 도구 도입 검토(향후)" 재인용) — **EXECUTABLE AFTER IMPLEMENTATION**(도구 도입 자체가 Decision Required 성격, 이 문서에서 도구를 지정하지 않음).
- `.github/workflows/` 디렉터리 부재 확인(§5) — CI 기반 자동 검사는 현재 **NOT IMPLEMENTED**.

## 29. 단위테스트 Gate (G3)

**Entry criteria**: Commit8-3b/8-3d 대상 함수(HMAC 서명/검증, Idempotency 상태전이 판정, RBAC 검사 등) 구현 완료.
**Required checks**: §15(HMAC)·§20(CAS)·§21(Idempotency) 단위 테스트 전항목 실행.
**Pass criteria**: 신규 단위 테스트 전항목 PASS, 기존 단위 테스트 회귀 없음.
**Evidence**: 신규 테스트 결과 CSV(아직 없음).
**Blocker**: 구현 자체가 없어 **NOT PASSED로 표시하지 않고 NOT STARTED로 표시**(테스트가 없는 상태를 실패로 오판하지 않음).
**Approval status**: DEFERRED(구현 착수 전).

## 30. 통합테스트 Gate (G4)

**Entry criteria**: G3 통과, FastAPI-GAS Fake Adapter(§10, 기존 `run_sprint8_commit8_2c_...` 패턴 재사용 제안) 준비.
**Required checks**: §16(Replay)·§17(RBAC 8-Operation)·§19(상태전이) 통합 시나리오.
**Pass criteria**: 8개 Operation 각각 최소 1개 이상 Positive+Negative 케이스 PASS.
**Blocker**: RESCHEDULE의 허용 전이 자체가 DEFERRED이므로 이 Operation은 G4를 구조적으로 통과할 수 없음(정책결정 선행 필요).
**Approval status**: DEFERRED.

## 31. 보안테스트 Gate (G5)

**Entry criteria**: G4 통과.
**Required checks**: §13-18(인증/세션/HMAC/Replay/RBAC/GAS직접호출), §22-23(감사로그/오류노출).
**Pass criteria**: Critical/High 등급 위협(Threat Model §41) 중 Sprint8 범위 내 항목(T01/T02/T03/T09) 전부 목표통제 확인, T13/T14/T20/T21은 "잔존 위험으로 문서화됨"이 Pass 조건(완전 해소가 조건이 아님 — Threat Model §42 재인용).
**Approval status**: DEFERRED.

## 32. 성능·부하 Gate (G6)

**Entry criteria**: G5 통과, DR-B-01 PoC 3건 완료.
**Required checks**: DR-B-02 부하검증(Idempotency TTL), GAS CacheService eviction 실측.
**Pass criteria**: **이 문서에서 정의하지 않음** — 실측 데이터 부재로 Pass 기준 자체가 REQUIRES LOAD VALIDATION 상태(ADR-017 §29 재인용).
**Blocker**: PoC/부하검증 미착수.
**Approval status**: DEFERRED(PM/개발팀).

## 33. 배포 전 Gate (G7)

**Entry criteria**: G6 통과.
**Required checks**: Commit8-3d 4개 Operation 완료조건(ADR-017 §26 재인용: 실제 일정변경/Slot반환포함/선행상태제한/메모저장 전부 구현·검증), `reservedCount` 결함 수정 확인.
**Pass criteria**: **이 문서에서 확정하지 않음** — 승인권자 자체가 DEFERRED(DR8-1-30 FastAPI Deploy 승인권자, §53 Threat Model 재인용).
**Approval status**: DEFERRED.

## 34. 배포 승인 Gate (G8)

**Entry criteria**: G7 통과.
**Required checks**: Netlify Auto Publishing 잠금 해제 여부, GAS 신규버전 배포 승인(D27/DR8-1-31), Rollback 독립성 위험(ADR-017 §27) 대응정책 수립 여부.
**Pass criteria**: PM 개별 승인(Git Push/Netlify Deploy/GAS Deploy/FastAPI Deploy 각각 독립 승인, ADR-017 §33/Threat Model §56 원칙 재인용 — 하나의 승인이 나머지를 포함하지 않음).
**Approval status**: DEFERRED.

## 35. 배포 후 Smoke Test Gate (G9)

**Entry criteria**: G8 통과 및 실제 제한적 배포 완료.
**Required checks**: §27(REGR) 전항목 + 8개 Operation 실사용 경로 확인 + 감사로그 실제 기록 확인.
**Pass criteria**: 이 문서에서 확정하지 않음 — 운영 전환 절차 자체가 별도 Runbook 대상(ADR-017 §28 재인용).
**Approval status**: DEFERRED.

## 36. Rollback 판단과 중단 기준

- 인증 관련 Rollback 시에도 **Mock 재활성화는 금지**(PM 승인사항, Commit8-2 보고서 §11/Threat Model §57 재인용) — 대신 서비스 중단을 택한다.
- GAS Rollback과 Netlify Allowlist Rollback은 서로 독립적 경로이며 한쪽만 되돌리면 다른 쪽 보호가 무력화될 수 있다는 위험이 이미 공식 인정되어 있다(ADR-017 §27 재인용) — 이 문서는 대응정책을 새로 수립하지 않는다.
- 중단 기준(어떤 테스트 실패가 배포 중단을 의미하는지)은 §29-35 각 Gate의 Pass criteria 미충족으로 정의되며, 별도 임계치를 이 문서에서 신설하지 않는다.

## 37. 증적과 결과 보존

기존 관행(CSV 결과 파일, `tests/sprint*_test_result.csv` 명명 규칙)을 재사용할 것을 제안한다(**PROPOSED**, 강제하지 않음). 보호 대상 파일(`ADR-015_Slot_Status_Policy_Draft.md`, `tests/sprint3_rbac_test_result.csv`)은 이 문서가 정의하는 어떤 테스트의 결과 저장 대상도 아니며, 앞으로도 그 두 파일과는 무관하게 신규 결과 파일이 별도로 생성되어야 한다.

## 38. 실패·예외 승인 처리

예외 승인으로 인증·인가·PII 보호 필수 Gate를 우회하는 절차는 이 문서에서 설계하지 않는다(작성 지침 §6 원칙 준수). 실패 시 기본 원칙은 "보안 우회보다 작업 중단"(Commit8-2 보고서 §10/Threat Model §38 기존 원칙 재인용)이며, 이 문서가 정의하는 모든 Gate에도 동일하게 적용된다.

## 39. 역할과 승인권자 결정 상태

전부 **DEFERRED**. DR8-1-27~31(Rollback/Push/Netlify/FastAPI/GAS Deploy 승인권자, Threat Model §53 재인용)과 STEP1§24-3(담당부서)이 결정되기 전까지 이 문서는 어떤 Gate의 승인권자도 임의 지정하지 않는다.

## 40. DR-B-01·DR-B-02 의존성

| ID | 내용 | 이 문서에서의 위치 | 의존 Gate |
|---|---|---|---|
| DR-B-01 | PoC 3건(SQLite UNIQUE 원자성/CacheService eviction 시뮬레이션/양쪽 저장소 정합성 불일치 처리) | §16(REPLAY), §21(IDEM) | G6 |
| DR-B-02 | Idempotency TTL 부하검증 | §21(IDEM) | G6 |

두 ID 모두 ADR-017 §29 원문 그대로 인용하며, 이 문서는 결과를 추정하지 않는다.

## 41. Commit8-3b·8-3d 구현 경계

| 구분 | 범위 | 이 문서와의 관계 |
|---|---|---|
| Commit8-3b | HMAC 실제 구현(`service_hmac.py` 확장 또는 재작성, §5 형식 불일치 해소 포함 여부는 그 Commit에서 결정), Nonce 이중구조, Idempotency 처리, Grace 기간, 재시도, 감사로그 신규 이벤트 연계, PoC 3건·부하검증 선행 | §15/§16/§21/§22/§29-32 Gate의 구현 대상 |
| Commit8-3d | RESCHEDULE/CANCEL/COMPLETE/NOTE 4개 Operation, `reservation:complete`/`reservation:note` 권한 구현, Slot 반환 세부규칙 확정 후 구현, `reservedCount` 결함 수정 | §17/§19/§26/§30-33 Gate의 구현 대상 |

이 문서는 두 Commit의 실제 코드를 작성하지 않으며 경계를 재확인만 한다(ADR-017 §31 이관표 재인용).

## 42. 추적성 Matrix

### 42-1. 핵심 테스트 Matrix

| Test ID | Security area | Scenario | Preconditions | Test method | Expected result | Evidence source | Current executability | Decision status | Required implementation |
|---|---|---|---|---|---|---|---|---|---|
| AUTH-07 | 인증 | 미인증 요청 거부 | 쿠키 없음 | 보호 API 직접 호출 | 401 | Threat Model §46-A | EXECUTABLE NOW(기 PASS) | 확정 | 없음(기 구현) |
| AUTH-11/SESS-04 | 세션 | 만료·위조 세션 거부 | 만료/위조 세션 쿠키 | 요청 | 401 | Threat Model §46-A/B | EXECUTABLE NOW(기 PASS) | 확정 | 없음 |
| AUTHZ-01 | 인가 | Permission 없는 요청 거부 | 권한 없는 역할 세션 | 승인/거절 API 호출 | 403 | Threat Model §46-D | EXECUTABLE NOW(기 PASS) | 확정 | 없음 |
| RBAC-00 | 인가 | UI 버튼 숨김 우회 요청 거부 | `approvalBlocked` 무시하고 직접 GAS/Legacy URL 호출 | 직접 HTTP 요청 | 현재는 **차단되지 않음**(Legacy 경로), Admin Portal 경로는 세션 필요 | RBAC Matrix §11 | EXECUTABLE NOW(현황기록용) | 확정(위험 잔존 사실 자체는 확정) | Legacy Phase B 전환(별도 Sprint) |
| HMAC-01 | HMAC | 유효 HMAC 요청 통과 | Secret 공유, 정상 서명 | `sign_request`+`verify_signature` 단위호출 | 검증 통과 | `service_hmac.py` | EXECUTABLE NOW(단위) / EXECUTABLE AFTER IMPLEMENTATION(GAS 연계) | REQUIRES POLICY DECISION(Canonical String 형식 확정, §15) | Commit8-3b |
| HMAC-02 | HMAC | 누락된 HMAC 거부 | 서명 필드 누락 요청 | GAS 서명검증 | `AUTH_FAILED` | ADR-017 §12 | EXECUTABLE AFTER IMPLEMENTATION | 확정(원칙만) | Commit8-3b(GAS코드) |
| HMAC-03 | HMAC | 변조된 HMAC 거부 | body 변조 후 기존 서명 재사용 | 상동 | `SIGNATURE_MISMATCH` | ADR-017 §12 | EXECUTABLE AFTER IMPLEMENTATION | 확정 | Commit8-3b |
| REPLAY-01 | timestamp | 오래된 timestamp 거부 | timestamp가 허용범위 초과 | 서명검증 | `TIMESTAMP_EXPIRED` | ADR-017 §12/§14 | EXECUTABLE AFTER IMPLEMENTATION | 확정(허용범위 원칙만, 구체 초값 재확인 필요) | Commit8-3b |
| REPLAY-02 | nonce | nonce 재사용·replay 거부 | 동일 nonce 재전송 | FastAPI SQLite+GAS Cache 이중검사 | `NONCE_REPLAYED` | ADR-017 §13 | EXECUTABLE AFTER IMPLEMENTATION | REQUIRES POC(DR-B-01) | Commit8-3b |
| REPLAY-03 | nonce | 저장소 간 정합성 불일치 처리 | FastAPI 신규판단, GAS Cache엔 이미 존재 | 극단 시나리오 재현 | ADR-017 §13 설계 원칙대로 처리 | ADR-017 §29 PoC#3 | REQUIRES POC | REQUIRES POC | Commit8-3b |
| RBAC-01 | RBAC | HMAC 통과 후 사용자 RBAC 별도 검사 | 유효 서명이나 세션 권한 부족 | HMAC 통과 + RBAC 거부 조합 | HMAC 성공해도 403 | RBAC Matrix §31(책임경계) | EXECUTABLE AFTER IMPLEMENTATION | 확정(원칙) | Commit8-3b+RBAC 연계 |
| GASBYPASS-01 | GAS 직접호출 | GAS 직접 action 호출 위험 확인 | Web App URL 보유 | 서명 없이 GAS 직접 POST | 현재 **성공함**(위험 현존) | Threat Model T14, RBAC Matrix §32 | EXECUTABLE NOW(현황기록용) | 확정(위험 잔존) | Commit8-3b(부분완화)+Legacy Phase B |
| RBAC-02 | 권한 | LIST 권한 검사 | 세션 있음/없음, 권한 있음/없음 | GET 호출 | 있음→200, 없음→403/401 | API Contract §15, RBAC Matrix §14 | EXECUTABLE NOW(기 구현) | 확정 | 없음 |
| RBAC-03 | 권한 | DETAIL 권한 검사 | 상동 | GET 호출 | 상동 | 상동 | EXECUTABLE NOW | 확정 | 없음 |
| RBAC-04 | 권한 | APPROVE 권한 검사 | 상동+CSRF | POST 호출 | 있음→200, 없음→403 | routes_admin_portal.py L689 | EXECUTABLE NOW(기 PASS) | 확정 | 없음 |
| RBAC-05 | 권한 | REJECT 권한 검사 | 상동 | POST 호출 | 상동 | 상동 | EXECUTABLE NOW(기 PASS) | 확정 | 없음 |
| RBAC-06 | 권한 | RESCHEDULE 권한 검사(Sheets 도메인) | `reservation:change` 보유 세션 | POST(제안 경로) 호출 | 목표: 있음→200, 없음→403 | RBAC Matrix §14/§84 | EXECUTABLE AFTER IMPLEMENTATION | REQUIRES POLICY DECISION(허용시점 등) | Commit8-3d |
| RBAC-07 | 권한 | CANCEL 권한 검사(Sheets 도메인) | `reservation:cancel` 보유 세션 | POST(제안 경로) 호출 | 목표: 있음→200, 없음→403 | RBAC Matrix §14 | EXECUTABLE AFTER IMPLEMENTATION | 부분확정(사유필수는 확정) | Commit8-3d |
| RBAC-08 | 권한 | COMPLETE/NOTE 후보 Permission 검사 | `reservation:complete`/`reservation:note` 신설 후 | POST(제안 경로) 호출 | 목표: 있음→200, 없음→403 | RBAC Matrix §14(NOT FOUND) | EXECUTABLE AFTER IMPLEMENTATION | REQUIRES POLICY DECISION(담당부서 STEP1§24-3) | Commit8-3d |
| TRANS-01 | 상태전이 | 허용 from-state 전이(APPROVE) | 예약접수 상태 | POST approve | 예약확정으로 전이 | `assert_can_transition` | EXECUTABLE NOW(기 PASS) | 확정 | 없음 |
| TRANS-02 | 상태전이 | 금지 from-state 전이 거부(APPROVE 재시도) | 이미 예약확정 상태 | POST approve 재시도 | 409 | 상동 | EXECUTABLE NOW(기 PASS) | 확정 | 없음 |
| TRANS-03 | 상태전이 | COMPLETE 선행상태 제한 | 예약확정 외 상태 | POST complete(제안) | 거부(`INVALID_TRANSITION`) | ADR-017 §21, State Matrix §11-19 | EXECUTABLE AFTER IMPLEMENTATION | 부분확정(선행상태만) | Commit8-3d |
| TRANS-04 | 상태전이 | RESCHEDULE 허용 전이 | 미정 | POST reschedule(제안) | 미정 | State Matrix §11-19(DEFERRED) | REQUIRES POLICY DECISION | REQUIRES POLICY DECISION | Commit8-3d(정책 후) |
| TRANS-05 | 상태전이 | 잘못된 상태값 거부 | 임의 문자열 상태값 전송 | GAS 직접/API 경유 | 현재 GAS는 **그대로 저장함**(위험) | State Matrix §26, sheets_api_v3_final.gs L396 | EXECUTABLE NOW(현황기록용) | 확정(위험 잔존) | Commit8-3b/8-3d(화이트리스트 검증) |
| TRANS-06 | 상태전이 | 검진완료 취소·복원 거부 | 검진완료 상태에서 취소/복원 시도 | POST cancel/reschedule(제안) | 거부 | ADR-017 §21 확정 | EXECUTABLE AFTER IMPLEMENTATION | 확정(원칙) | Commit8-3d |
| CAS-01 | CAS | stale update 탐지 | 두 관리자가 동시에 다른 상태로 변경 시도 | 동시 POST 2건 | 목표: 후행 요청 거부 또는 경고 | routes_admin_portal.py L703(CAS 부재 인정) | EXECUTABLE AFTER IMPLEMENTATION | REQUIRES POLICY DECISION(탐지방식 미정) | Commit8-3b/8-3d 설계 선행 |
| CAS-02 | CAS | CAS 충돌 처리 | 상동 | 상동 | 목표: 충돌코드 반환 | API Contract §22(Open Question) | REQUIRES POLICY DECISION | REQUIRES POLICY DECISION | 상동 |
| IDEM-01 | Idempotency | 중복요청·Idempotency 키 재사용 | 동일 idempotencyKey+동일 payload 재전송 | POST 2회 | 2번째는 캐시된 결과 반환(재실행 안함) | ADR-017 §14 | EXECUTABLE AFTER IMPLEMENTATION | REQUIRES LOAD VALIDATION(TTL) | Commit8-3b |
| IDEM-02 | Idempotency | 동일 키+다른 payload 거부 | 동일 idempotencyKey+다른 payload | POST 2회 | `IDEMPOTENCY_CONFLICT` | ADR-017 §14 | EXECUTABLE AFTER IMPLEMENTATION | 확정(원칙) | Commit8-3b |
| IDEM-03 | Idempotency | IN_PROGRESS 정체 판정 | 60초 초과 미응답 | 시간 경과 시뮬레이션 | UNKNOWN/RECONCILIATION_REQUIRED 전이 | ADR-017 §14 | REQUIRES LOAD VALIDATION | REQUIRES LOAD VALIDATION | Commit8-3b+부하검증 |
| SLOT-01 | 실패보존 | 실패 시 기존 상태 보존(APPROVE) | Sheets 쓰기 실패 유도 | Fake Adapter 오류 주입 | Slot Rollback, 상태 불변 | `_safe_rollback_slot` L739-748 | EXECUTABLE NOW(기 구현) | 확정 | 없음 |
| SLOT-02 | 실패보존 | 실패 시 기존 상태 보존(CANCEL/RESCHEDULE) | 상동(신규 Operation) | 상동 | 목표: 동일 원칙 | ADR-017 §23 재인용 | EXECUTABLE AFTER IMPLEMENTATION | 확정(원칙) | Commit8-3d |
| AUDIT-01 | 감사로그 | 성공 이벤트 기록(APPROVE/REJECT) | - | 승인/거절 실행 후 로그 확인 | 이벤트 기록됨 | `append_audit` 기존 호출 | EXECUTABLE NOW(기 구현) | 확정 | 없음 |
| AUDIT-02 | 감사로그 | 신규 이벤트 기록(RESCHEDULE 등) | AUDIT_EVENTS 확장 후 | 신규 Operation 실행 후 로그 확인 | 이벤트 기록됨 | §5(화이트리스트 미등록 재확인) | EXECUTABLE AFTER IMPLEMENTATION | 확정(원칙) | Commit8-3b/8-3d |
| AUDIT-03 | 감사로그 | 실패 이벤트 기록 | 서명실패/권한거부 등 | 실패 유도 후 로그 확인 | 실패 이벤트 기록됨 | Threat Model §46-F | EXECUTABLE AFTER IMPLEMENTATION(신규 이벤트) / EXECUTABLE NOW(기존 실패유형) | 확정 | 부분(Commit8-3b) |
| AUDIT-04 | 감사로그 | Secret·PII 비노출 확인 | - | 로그 파일 grep(원문 패턴) | 미검출 | `_server_log()` PII-safe 원칙 | EXECUTABLE NOW | 확정 | 없음 |
| ERR-01 | 오류응답 | 오류응답 내부정보 비노출(현행) | 권한거부 유도 | 응답 본문 확인 | 현재는 **상세정보 노출됨**(AS-IS) | Threat Model §21(`api_server.py` L177) | EXECUTABLE NOW(AS-IS 확인용) | 확정(현행 미준수 상태 기록) | 원칙 적용 후 재검증 필요 |
| ERR-02 | 오류응답 | 서명검증 실패 사유 통일 | HMAC 실패 다양한 사유 유도 | 응답코드 비교 | 전부 동일 `AUTH_FAILED`류 | ADR-017 §12(Oracle 방지) | EXECUTABLE AFTER IMPLEMENTATION | 확정(원칙) | Commit8-3b |
| INPUT-01 | 입력검증 | 알 수 없는 필드 거부 | 관리자 전용 필드 포함한 공개 create 요청 | POST create+extra필드 | 거부 또는 무시(extra forbid) | API Contract §12 | EXECUTABLE NOW(기존 스키마) | 확정 | 없음 |
| RATE-01 | Rate limit | 로그인 반복 실패 제한 | 틀린 자격증명 N회 | 반복 POST login | 목표: 임계치 후 잠금 | Threat Model AUTH-05(권장) | EXECUTABLE AFTER IMPLEMENTATION | REQUIRES POLICY DECISION(임계치) | DR8-1-12(Commit8-2 범위, 필수 아님) |
| RATE-02 | Timeout | Admin Portal GAS 호출 Timeout | GAS 응답 지연 시뮬레이션 | Fake Adapter 지연 주입 | 8초 후 Timeout 처리 | Commit5-3.2 기 확인 | EXECUTABLE NOW(기 구현) | 확정 | 없음 |
| RATE-03 | Retry | 재시도 정책(3회, 지수백오프) | 일시적 실패 유도 | 반복 실패 후 성공 시나리오 | 최대 3회 재시도 후 성공/최종실패 | ADR-017 §16 | EXECUTABLE AFTER IMPLEMENTATION | 확정(원칙) | Commit8-3b |
| REGR-01 | 회귀 | 기존 보안 스위트 재실행 | - | 3개 기존 CSV 스위트 재실행(§27) | 전부 PASS 유지 | §5(62+13+16항목, 기 PASS) | EXECUTABLE NOW | 확정 | 없음(재실행만 필요) |

### 42-2. Operation 추적성

| Operation | Authentication | Permission | State rule | Audit requirement | Negative tests | Current implementation | Blocking dependency | Deployment gate |
|---|---|---|---|---|---|---|---|---|
| LIST | FastAPI 세션(CURRENTLY CONFIRMED) | `reservation:view` | 해당없음 | NOT IMPLEMENTED(조회 자체 감사 미확인) | AUTH-07, AUTHZ-01 | CURRENTLY CONFIRMED | 없음 | G3-G9 전부 이미 충족(변경 불필요) |
| DETAIL | 상동 | `reservation:view` | 해당없음 | 상동 | 상동 | CURRENTLY CONFIRMED | 없음 | 상동 |
| APPROVE | FastAPI 세션+CSRF(CURRENTLY CONFIRMED) | `reservation:approve` | 예약접수→예약확정만(CURRENTLY CONFIRMED) | CURRENTLY CONFIRMED(`RESERVATION_APPROVED`) | TRANS-01/02, RBAC-04 | CURRENTLY CONFIRMED | 없음 | 상동 |
| REJECT | 상동 | `reservation:approve` | 예약접수→거절만(CURRENTLY CONFIRMED) | CURRENTLY CONFIRMED(`RESERVATION_REJECTED`) | RBAC-05 | CURRENTLY CONFIRMED | 없음 | 상동 |
| RESCHEDULE | 세션+HMAC(PROPOSED) | `reservation:change`(제안, RBAC-06) | DEFERRED(companion#1-3) | PROPOSED(`RESERVATION_RESCHEDULED`, 미등록) | RBAC-06, TRANS-04 | NOT IMPLEMENTED | companion#1/#2/#3, STEP1§24-1, companion#7 | G3-G9 전부 미도달(정책 선행) |
| CANCEL | 세션+HMAC(PROPOSED) | `reservation:cancel`(제안, RBAC-07) | 목표상태만 확정 | PROPOSED(`RESERVATION_CANCELLED`, AUDIT_EVENTS 기 존재하나 Sheets 도메인 미연결) | RBAC-07, SLOT-02 | NOT IMPLEMENTED | companion#7 세부규칙 | G3-G5는 도달 가능(사유필수 등 확정분), G6 이후 Slot규칙 확정 필요 |
| COMPLETE | 세션+HMAC(PROPOSED) | `reservation:complete`(신설, NOT FOUND) | 예약확정만(부분확정) | PROPOSED(`RESERVATION_COMPLETED`, AUDIT_EVENTS 기 존재하나 Sheets 도메인 미연결) | RBAC-08, TRANS-03/06 | NOT IMPLEMENTED | STEP1§24-3(담당부서), 권한 신설 승인 | G3-G4는 부분 도달 가능, G5부터 권한 신설 필요 |
| NOTE | 세션+HMAC(PROPOSED) | `reservation:note`(신설, NOT FOUND) | 상태 불변(확정) | PROPOSED(`RESERVATION_NOTE_UPDATED`, 미등록) | RBAC-08 | NOT IMPLEMENTED | 권한 신설 승인 | 상동 |

### 42-3. 배포 Gate 요약

| Gate | Entry criteria | Required checks | Pass criteria | Evidence | Blocker | Approval status | Next action |
|---|---|---|---|---|---|---|---|
| G0 | 없음(설계 착수) | 정책 확정 여부 확인 | 관련 DEFERRED 항목 해소 | ADR-016/017 | companion#1-10 일부, STEP1§24-* 일부 | DEFERRED | PM 정책결정 |
| G1 | G0 관련분 확정 | 코드 구현+리뷰 | 구현 완료, 리뷰 승인 | 없음(미착수) | 구현 자체 없음 | DEFERRED | Commit8-3b/8-3d 착수 승인 |
| G2 | G1 통과 | §28 정적/Secret/의존성 검사 | 검출 0건 | 없음 | 자동화 도구 부재 | DEFERRED | 도구 도입 검토(선택) |
| G3 | G1 통과 | §29 단위테스트 | 신규 단위 테스트 전항목 PASS | 없음 | 구현 없음 | DEFERRED | §29 참조 |
| G4 | G3 통과 | §30 통합테스트 | 8-Operation 각 1+ 케이스 PASS | 없음 | RESCHEDULE 정책 미확정 | DEFERRED | §30 참조 |
| G5 | G4 통과 | §31 보안테스트 | Critical/High Sprint8 범위 항목 통제 확인 | 없음 | HMAC/Nonce 미구현 | DEFERRED | §31 참조 |
| G6 | G5 통과 | §32 성능/부하 | REQUIRES LOAD VALIDATION 상태 | 없음 | PoC/부하검증 미착수 | DEFERRED | DR-B-01/02 착수 승인 |
| G7 | G6 통과 | §33 배포전 운영승인 | 미정(승인권자 DEFERRED) | 없음 | DR8-1-30 미확정 | DEFERRED | 승인권자 결정 |
| G8 | G7 통과 | §34 배포승인 | PM 개별승인(4종 독립) | 없음 | DR8-1-27~31 미확정 | DEFERRED | 승인권자 결정 |
| G9 | G8 통과+제한배포 | §35 Smoke Test | 미정 | 없음 | 배포 자체 미발생 | DEFERRED | Runbook 수립 |

## 43. 미결정 사항

companion#1/#2/#3/#8/#10, STEP1§24-1/§24-3/§24-4(정책), DR-B-01 PoC 3건/DR-B-02 부하검증(기술·성능), CAS 탐지 방식(§20), Rate Limit 임계치(§25), Slot 반환 세부규칙(§26), `service_hmac.py`와 ADR-017 Canonical String 형식 불일치 해소 방법(§5/§15), Gate G6~G9의 Pass criteria 구체값(§32-35), 승인권자·담당부서 전체(§39). 전부 이 문서에서 확정하지 않는다.

## 44. 후속 작업

- STEP3-E-B 이상(있다면): 이 문서의 PM 검토·승인.
- Commit8-3b 착수 전: DR-B-01 PoC 3건, DR-B-02 부하검증 승인 및 수행.
- Commit8-3d 착수 전: companion#1/#2/#3/#7, STEP1§24-1/§24-3 정책 확정.
- `service_hmac.py`와 ADR-017 §12 Canonical String 형식 불일치(§5) 해소 방향 결정 — Commit8-3b 설계 세부사항으로 제안(이 문서는 결정하지 않음).
- `AUDIT_EVENTS` 화이트리스트에 신규 7종 이벤트 추가 — Commit8-3b/8-3d 구현 항목.
- `CMC.STATUS_LIST` Gap(State Transition Matrix §34)의 수정 여부 별도 결정.

## 45. 결론

이 문서는 Commit8-3a에서 확정된 4개 설계문서의 보안 요구사항을 42개 신규/재사용 Test ID와 G0~G9 10단계 배포 Gate로 연결했다. 현재 **EXECUTABLE NOW**로 판정된 항목(인증/세션/기존 승인·거절 RBAC/일부 감사로그/기존 회귀 스위트 3종)은 이미 Commit8-2에서 구현·검증되어 있으며 이번 STEP에서 재실행하지 않았다. 나머지 대부분(HMAC 배선, Nonce/Idempotency/CAS, RESCHEDULE/CANCEL/COMPLETE/NOTE 4개 Operation)은 **EXECUTABLE AFTER IMPLEMENTATION**, **REQUIRES POC**, 또는 **REQUIRES POLICY DECISION** 상태로 남아 있으며, 이 문서 단독으로는 G3 이상의 Gate를 통과할 수 없다. 조사 과정에서 `src/auth/service_hmac.py`가 이미 존재하나 ADR-017 최종 Canonical String 형식과 다르다는 새로운 Gap을 발견했다(§5/§8). 배포 승인·Rollback 결정권자는 여전히 전부 DEFERRED이며, 이 문서는 어떤 정책도 임의로 확정하지 않았다.

---

**완료 조건 준수 확인**: 이 문서 작성 중 ADR-016·ADR-017·Security Architecture Design·Admin Operations API Contract·State Transition Matrix·RBAC Permission Matrix·Threat Model·Commit8-2 보고서를 포함한 어떤 기존 파일도 수정하지 않았다. 애플리케이션 코드·테스트 코드를 작성하지 않았다. 실제 테스트를 실행하지 않았다. Idempotency TTL·Nonce 저장방식·CAS 구조·Rate Limit 수치·Timeout/재시도 횟수·부하테스트 목표치·Slot 반환 세부규칙·신규 Permission 최종 확정·승인권자·담당부서·예외 승인 주체·배포/Rollback 최종 승인자를 확정하지 않았다. DR-B-01/DR-B-02가 필요한 사항은 DEFERRED로 유지했다. 보호 대상 파일(`ADR-015_Slot_Status_Policy_Draft.md`, `tests/sprint3_rbac_test_result.csv`)을 읽지 않았다. 실제 Secret·PII·운영 URL을 포함하지 않았다. Git add/commit/push, 테스트 실행, 정책결정, PoC, 부하검증, 구현, 배포를 수행하지 않았다.
