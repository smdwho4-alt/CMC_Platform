# Commit8-3b — 서명·nonce·idempotency 격리 통합 흐름(실험안) 현황

> **상태**: 이 문서가 다루는 통합 흐름(`src/idempotency/signed_gas_integration.py`)은
> **격리 개발·로컬 전용 실험안**이다. 합성 데이터·합성 키·로컬
> SQLite·Fake Secondary·Fake GAS만 사용했다. 운영 라우트·실제
> GAS/Sheets·CacheService에 연결되지 않았다. **OFFICIAL PHASE 1
> GATE = BLOCKED INPUT 유지.**
> **작성일**: 2026-10-03

---

## 1. 현재 구조

`signed_gas_integration.py`는 **접착(glue) 코드만** 제공한다 — 가드·
서명·nonce·idempotency 실행권/결과기록 로직은 기존 모듈
(`payload_schema_guard.py`, `request_payload_schemas.py`,
`signing_v2.py`, `signing_v2_guarded.py`, `nonce_store.py`,
`idempotency_store.py`, `gas_orchestration.py`)을 **재작성 없이 호출만
한다.**

### 처리 순서

```
1. raw JSON 검증 + operation별 스키마 검증(signing_v2_guarded)
2. payload 정규화 + fingerprint 계산(signing_v2.compute_payload_hash)
3. idempotency 실행권 획득(gas_orchestration.execute_with_idempotency
   -> idempotency_store.try_create)
4. 실행권 획득 시에만 nonce 발급 + v2 서명(prepare_dispatch 콜백 안)
5. Fake 수신부(FakeReceiver)에서 서명·timestamp·payloadHash 검증
   (gas_adapter 콜백 안, signing_v2.verify_v2)
6. 수신부 replay 차단 후 Fake 업무 실행
   (nonce_store.evaluate_and_register_nonce -> business_adapter)
7. 결과 기록 또는 UNKNOWN 처리(gas_orchestration이 담당,
   record_outcome/mark_unknown)
```

### nonce 저장소 — 발급측 감사 기록 vs 수신측 replay 차단(역할 구분)

이 통합은 **서로 물리적으로 분리된 두 개의 nonce 저장소**를 쓴다.
두 역할은 명확히 다르다:

| | 발급측(issuer) | 수신측(receiver) |
|---|---|---|
| 저장소 | `IssuerConfig.issuer_nonce_data_dir`(전용 SQLite) + 전용 `FakeSecondaryNonceStore` | `FakeReceiver`가 보유한 별도 SQLite + 별도 `FakeSecondaryNonceStore` |
| 역할 | **감사 기록(audit trail)** — "내가 이 nonce를 발급했다"는 자기 기록 | **replay 차단(보안 경계)** — "이 nonce를 실제로 처리해도 되는가"의 최종 판정 |
| 거절(DENY) 발생 가능성 | 정상 경로에서는 드묾(매번 새로 생성하는 랜덤 nonce가 우연히 겹쳐야 함) — **단, "구조적으로 불가능"하지는 않다.** 발급측도 수신측과 동일한 `evaluate_and_register_nonce()`를 재사용하므로 DENY 경로를 그대로 가지며, 실측으로 확인했다(§3-2 정정) | 있음(진짜 replay 또는 드문 Primary/Secondary 불일치 상황) |
| 유의미한 장애 모드 | DENY와 ERROR 둘 다(§3-2 정정) | DENY(Secondary가 먼저 거절)와 ERROR(일시 장애) 둘 다 |
| 실패 시 결과 | `prepare_dispatch` 실패(`NOT_SENT_PREP_FAILED`), **envelope 자체가 생성되지 않음** | `GasResponse(success=False, ...)`, idempotency 계층이 `FAILED_RETRYABLE`/`FAILED_FINAL`로 기록 |

두 저장소는 **절대 공유되지 않는다.** 이는 (a) 발급 때 자기 저장소에
등록한 nonce를 수신부가 "이미 본 nonce"로 오탐 거절하지 않고,
(b) 진짜 replay(탈취한 envelope를 발급측 idempotency 계층을 완전히
우회해 수신부에 직접 재전송하는 공격 포함)는 수신부가 독자적으로
차단하기 위함이다.

---

## 2. ADR과의 차이 — 임의 확정 아님, 실험안으로 보고

### 2-1. 양쪽 이중저장 구조 자체가 실험안

ADR-017 §13("Nonce 영속화 구조")이 확정한 것은 "FastAPI SQLite 1차
방어 + GAS CacheService 2차 방어"라는 **하나의 이중 판정**이며,
원문은 이를 "발급 측이 전송 전에 둘 다 확인"하는 단일 호출로
설명한다. **"발급측도 별도의 이중저장소를 갖고, 수신측도 별도의
독자적인 이중저장소를 갖는다"는 양쪽 구조 전체는 ADR-017이 확정한
것이 아니라, 이번 통합 흐름이 이 작업 지시(네임스페이스 분리·오탐
방지·진짜 replay 차단)를 만족시키기 위해 범위 안에서 새로 도입한
**실험안(experimental proposal)**이다. 운영 ADR 개정 없이 이 해석을
운영 계약으로 확정하지 않는다.

### 2-2. `FakeReceiver`의 SQLite는 실제 GAS 구현의 청사진이 아니다

`FakeReceiver`가 SQLite(Primary)를 쓰는 것은 **기존 `nonce_store.py`
함수를 재작성 없이 재사용하기 위한 테스트 편의**일 뿐이다. **실제
GAS Apps Script 런타임에는 로컬 파일시스템도 SQLite도 없다** — 이
사실만은 확실하다. **다만 "그러므로 쓸 수 있는 저장 수단은
`PropertiesService`/`CacheService`뿐이다"라고 단정하지 않는다** —
Apps Script에는 `JDBC` 서비스로 외부 DB(Cloud SQL 등)에 연결하는
방법도 있는 등, 이번 작업이 모든 대안을 전수 조사하지 않았기
때문이다. 확실한 것은 "로컬 SQLite 같은 파일시스템 기반 저장소는
없다"는 사실뿐이다. 따라서 이 실험안의 "Primary(SQLite)+Secondary"
구조를 실제 수신측이 그대로 가질 것처럼 표현하지 않는다.

### 2-3. 실제 운영 구조로 옮길 때 고려할 사항(목록, 미확정 — 결정된 방향 아님)

1. 수신측에서 SQLite Primary는 그대로 쓸 수 없다(위 사실 재확인).
   **`CacheService` 단독 구조는 하나의 미확정 후보안일 뿐**이며, 이
   작업이 그것을 운영 설계로 확정하지 않는다. 다른 대안(외부 DB
   연결, Sheets 자체를 저장소로 쓰는 방법 등)도 검토 대상이다.
2. `CacheService` 단독 구조를 채택한다면 **아래 항목이 운영 설계에서
   반드시 해결돼야 한다**(이 실험안은 해결하지 않았다):
   - **캐시 유실·조기 제거(eviction) 후 replay 차단 한계** —
     CacheService 항목이 TTL 만료나 1,000항목 LRU eviction으로
     사라진 뒤 같은 nonce가 재전송되면, "이미 본 nonce" 기록 자체가
     없어 replay가 통과할 수 있다. 안전한 TTL 값과 "유실 이후"
     정책을 정해야 한다.
   - **동시 요청의 원자성** — CacheService의 조회+기록이 진짜
     원자적(atomic)인지, `LockService` 같은 별도 잠금이 필요한지
     PoC#2가 이미 지적했고 아직 실측되지 않았다.
   - **저장소 장애 시 차단 방식** — CacheService 자체가 응답하지
     않거나 오류를 낼 때 fail-closed로 갈지 운영 설계가 정해야
     한다(이 실험안의 수신측은 ERROR를 `retryable=True`로 분류했지만
     잠정적 선택이다 — §2-4 재확인).
3. "발급측 감사 기록"을 운영에 유지할지 재검토 — 유지한다면
   `nonce_store.py`의 "Primary+Secondary 판정 함수"를 그대로 쓸
   필요 없이 더 단순한 로그 방식으로 충분할 수 있다.
4. 실제 GAS `doPost` 핸들러 코드 작성·배포,
   `Utilities.computeHmacSha256Signature` 기반 서명 검증 포팅
   (`tests/cross_validation/gas/`에서 이미 격리 검증한 로직 재사용
   가능), 실제 공유 Secret 프로비저닝 방법(PM 승인 필요) 확정.
5. 이 실험안을 ADR-017 §13 개정안으로 제출할지, 더 단순한 구조로
   축소할지 PM/아키텍처 결정 필요.

### 2-4. retryable 분류 — 확정 정책 아님, 동일 nonce 재사용과 신규 nonce 재시도 구분

`FakeReceiver.receive()`가 `NONCE_STORE_FAILED`에 `retryable=True`를
붙이는 것은 **이 실험안의 잠정적 선택일 뿐, 확정 운영 정책이
아니다.** 특히 이 `retryable=True`는 **"같은 nonce를 재사용해도
된다"는 뜻이 전혀 아니다**:

- **동일 nonce 재사용**: `NONCE_REPLAYED` 분기가 **Primary 레코드가
  남아 있는 한** 차단한다(`retryable=False`) — `retryable` 값과
  무관하게 같은 nonce는 Primary가 보존된 동안 통과하지 못한다. **이
  테스트가 Primary를 정리하는 로직을 전혀 두지 않았다는 이유만으로
  "영구" 차단을 주장하지 않는다** — 실제 운영에서의 보존 기간은
  배치 정리 정책(아래 참조)에 달려 있다.
- **신규 nonce를 쓰는 같은 작업(같은 idempotency key) 재시도**: 호출부가
  **새로운 `handle_request()` 호출**(새 HTTP 요청)을 만들면,
  `idempotency_store`가 `RETRY_ACCEPTED`를 허용해 `prepare_dispatch`가
  다시 실행되고 **새 nonce**가 발급된다. 이것만 나중에 성공할 수
  있다.
- **timeout 등 결과 불확실(`SENT_UNCERTAIN`/`UNKNOWN`) 상태**에서는
  위 "신규 nonce 재시도"조차 **원천적으로 일어나지 않는다** —
  idempotency 계층 자체가 재요청을 `NOT_SENT_BLOCKED`로 막아
  `prepare_dispatch()`(nonce 발급 지점)가 호출되지 않기 때문이다.
  "새 nonce를 쓰면 UNKNOWN 차단을 우회할 수 있지 않을까"라는 시도는
  코드 구조상 불가능함을 테스트로 확인했다(§3 재확인).

Primary 레코드의 실제 보존 기간은 `nonce_store.py` 모듈 docstring이
이미 Open Question으로 남긴 "FastAPI DB는 배치 작업(1시간 주기)으로
만료분 삭제" 정책에 달려 있으며, 이 실험안은 그 배치 정리를 구현하지
않았고(따라서 테스트 실행 동안은 사실상 무기한 보존) 운영 보존
정책도 확정하지 않는다.

**자동 재시도는 이 실험안 어디에도 추가하지 않았다** — 모든 "재시도"는
테스트가 `handle_request()`를 수동으로 다시 호출해 시뮬레이션한
것이며, `signed_gas_integration.py`나 `gas_orchestration.py` 내부에
재시도 루프가 없다(기존 원칙 그대로 유지).

---

## 3. 검증 결과

```
python3 -m unittest tests.test_idempotency_store tests.test_gas_orchestration tests.test_signing_v2 \
  tests.test_nonce_store tests.test_payload_schema_guard tests.test_request_payload_schemas \
  tests.test_signing_v2_guarded tests.test_signed_gas_integration
# Ran 130 tests ... OK (기존 112 + 통합 18)
```

### 3-1. 신규/보완된 통합테스트(총 18개, `tests/test_signed_gas_integration.py`)

| 분류 | 테스트 이름 | 핵심 확인 |
|---|---|---|
| 정상 요청 | `test_normal_request_business_executed_exactly_once` | 업무 실행 1회 |
| 네임스페이스 분리 | `test_normal_request_issuer_nonce_does_not_cause_receiver_false_rejection` | 발급 기록이 수신부 오탐 거절을 유발하지 않음 |
| 캐시 반환 | `test_identical_retry_returns_cached_no_extra_execution` | 재시도 0 증가 |
| 충돌 | `test_same_key_different_payload_conflict_zero_execution` | 충돌 시 0회 |
| 동시성 | `test_concurrent_identical_requests_business_executed_exactly_once` | 8스레드 중 정확히 1회 |
| 변조(4종) | `test_signature_tamper_zero_execution` / `test_keyid_tamper_zero_execution` / `test_payload_tamper_zero_execution` / `test_timestamp_tamper_zero_execution` | 전부 0회 |
| replay | `test_replay_of_same_envelope_blocked_at_receiver` | idempotency 계층 완전 우회 재전송도 차단, 0 증가 |
| Secondary ERROR(수신) | `test_receiver_secondary_error_zero_execution_primary_preserved` | 0회, Primary 보존, 재전송도 0 증가 |
| Secondary DENY(수신) | `test_receiver_secondary_deny_zero_execution_primary_preserved` | ERROR와 구분되는 DENY 경로, 0회, Primary 보존 |
| 준비 실패(발급 ERROR) | `test_prepare_dispatch_failure_zero_execution` | 0회, envelope 자체 미생성(재전송 검증 대상 아님을 명시) |
| **Secondary DENY(발급측, 신규 — 정정)** | `test_issuer_secondary_deny_zero_execution_primary_preserved` | `nonce_store.generate_nonce()`를 고정값으로 패치해 발급측 DENY를 실제로 재현 — 0회, 발급측 Primary 보존 |
| 동일/신규 nonce 구분 | `test_retry_after_nonce_store_failed_uses_new_nonce_and_succeeds` | 실패한 nonce는 (Primary 보존 기간 동안) 거절, 재시도는 다른 신규 nonce로 성공 |
| timeout·UNKNOWN | `test_timeout_after_business_execution_marks_unknown_and_blocks_retry` | 재요청 시 `gas_called=False`(새 nonce조차 미발급) 확인 |
| 이중 기록 실패 + TTL | `test_double_record_failure_then_ttl_elapses_blocks_re_execution` | TTL 전후 재요청 모두 0 증가 |
| 기존 회귀 스모크 | `test_existing_modules_unchanged_regression_smoke` | 기존 모듈 API 불변 확인 |

### 3-2. 정정 — 발급측 DENY는 구조적으로 불가능하지 않다

이전 버전은 "발급측은 매번 새 nonce를 생성하므로 DENY가 구조적으로
발생할 수 없다"고 기록했으나 **부정확했다.** `prepare_dispatch`가
쓰는 `nonce_store.generate_nonce()`/`evaluate_and_register_nonce()`는
발급측·수신측에 동일하게 재사용되는 함수이므로, 발급측도 DENY
경로를 그대로 갖고 있다 — 단지 정상 경로에서 "우연히" 발생할
확률이 낮을 뿐이다. 정정된 테스트
`test_issuer_secondary_deny_zero_execution_primary_preserved`는
`unittest.mock.patch.object`로 `nonce_store.generate_nonce()`를
고정값으로 바꾸고 발급측 Secondary를 그 값으로 미리 오염시켜, 실제
DENY 경로가 업무 실행 0회·발급측 Primary 보존으로 이어짐을 실측
확인했다(가드·서명·nonce 검증 로직 자체는 건드리지 않음).

### 3-3. nonce_store.py 단위 레벨에서 이미 충족된 것(재사용만 함, 재검증 아님)

- `tests/test_nonce_store.py::test_secondary_existing_blocks_but_preserves_primary_and_blocks_reuse`
  (DENY 메커니즘 자체)
- `tests/test_nonce_store.py::test_secondary_error_blocks_but_preserves_primary_and_blocks_reuse`
  (ERROR 메커니즘 자체)

`FakeReceiver.receive()`는 이 두 테스트가 이미 검증한
`nonce_store.evaluate_and_register_nonce()`를 그대로 호출할 뿐이므로,
§3-1의 신규 통합테스트는 "같은 메커니즘이 통합 흐름 전체(서명 검증 +
FakeReceiver 래핑)를 통해서도 동일하게 작동하는가"를 확인하는 것이지,
저장소 자체의 동작을 처음부터 다시 증명하는 것이 아니다.

---

## 4. 검증 범위 밖(명시)

- **인증·권한검사(RBAC)**: 이 흐름 호출의 **전제조건**일 뿐이다 —
  `handle_request()`가 호출되기 전에 이미 끝났다고 가정하며, 이
  흐름 자체가 인증·권한을 검증했다고 표현하지 않는다.
- **실제 GAS Apps Script 수신부**: 작성·배포되지 않았다. 전부
  `FakeReceiver`(Fake)다.
- **실제 CacheService**: 연결되지 않았다. 전부
  `FakeSecondaryNonceStore`(Fake)다. §2-2에서 명시했듯 이 Fake의
  SQLite 기반 구현은 실제 CacheService 전용 환경으로 그대로 옮길 수
  없다.
- **실제 HTTP 요청/응답 계약**: 확정하지 않았다. `handle_request()`는
  내부 전용 타입 `gas_orchestration.OrchestrationResult`를 그대로
  반환한다.
- **오류 분류·retryable 판단**: 내부 참고용이며 운영 오류코드·정책으로
  확정된 것이 아니다(§2-4 재확인).

## 5. 남은 운영 과제

1. §2-1의 "양쪽 이중저장 실험안"을 ADR-017 §13 개정안으로 제출할지,
   더 단순한 구조로 축소할지 PM/아키텍처 결정.
2. §2-3의 실제 운영 구조 이관 고려사항 검토(SQLite 제거, 수신측
   저장소 후보안 비교·선정, 실제 GAS 핸들러 작성 등) — 전부 별도
   PM 승인 필요.
3. `retryable` 분류·오류 코드 체계의 운영 정책 확정.
4. 재시도 횟수 상한(ADR-017 §16 "최대 3회")·간격 집행 책임 소재 —
   이 실험안도 여전히 다루지 않는다(기존 Open Question 재확인).
5. 실제 공유 Secret 프로비저닝·키 로테이션 운영 절차 확정.

---

**완료 조건 재확인**: 합성 데이터·합성 키·로컬 SQLite·Fake Secondary·
Fake GAS만 사용했다. 운영 라우트·실제 GAS/Sheets/CacheService에
연결하지 않았다. 인증·권한·실제 GAS·CacheService 검증은 이번 범위
밖이다. commit/push·배포를 하지 않았다. **OFFICIAL PHASE 1 GATE는
BLOCKED INPUT으로 유지된다.**
