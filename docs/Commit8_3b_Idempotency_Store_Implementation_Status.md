# Commit8-3b Idempotency Store + GAS Orchestration — 구현 현황(격리 개발, 로컬 전용)

> **상태**: 격리 개발 worktree에서 작성한 저장 계층 + 격리 통합(orchestration) 계층의
> 최소 구현 현황이다. **Commit8-3b 전체 완료가 아니다.** 운영 라우트 연결·GAS/Sheets
> 접근·Push·배포는 수행하지 않았다.
> **OFFICIAL PHASE 1 GATE = BLOCKED INPUT 유지**(이 구현과 무관하게 고정, DR-B-02
> Phase 1 실행계획서 §4/§9.2).
> **작성일**: 2026-10-03(최초), 2026-10-03(갱신 — orchestration 계층 반영)
> **대상 코드**: `src/idempotency/idempotency_store.py`, `src/idempotency/gas_orchestration.py`,
> `tests/test_idempotency_store.py`, `tests/test_gas_orchestration.py`
> **기준 commit**: `07af44282344a79fcde00f406d4cd67fdb18a078`(개발 브랜치
> `worktree-commit8-3b-idempotency-store`, origin에 push 완료)

---

## 1. 모듈 API와 반환 분류

### 1-1. `idempotency_store.py`(저장 계층)

| 함수 | 역할 |
|---|---|
| `init_schema(data_dir)` | 스키마 생성(idempotent) |
| `connect(data_dir)` | 컨텍스트매니저 커넥션(WAL, `src/auth/auth_store.py`와 동일 house 컨벤션) |
| `try_create(conn, *, key, fingerprint, now=None, correlation_id=None)` | 생성/재시도 시도. 유일하게 쓰기 락(BEGIN IMMEDIATE)으로 원자성을 보장하는 핵심 함수 |
| `get_effective_state(conn, *, key, now=None, correlation_id=None)` | 순수 읽기 조회(부작용 없음) |
| `get_completed_result(conn, *, key, fingerprint, now=None, correlation_id=None)` | 완료 결과 재조회(순수 읽기, fingerprint 일치 확인 포함) |
| `record_outcome(conn, *, key, outcome_state, result=None, now=None, correlation_id=None)` | IN_PROGRESS → SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL 전이 + 결과 기록(단일 트랜잭션) |
| `mark_unknown(conn, *, key, now=None, correlation_id=None)` | **(이번 갱신 반영)** IN_PROGRESS를 **TTL 경과 여부와 무관하게 즉시** UNKNOWN으로 전이(§3) |
| `reconcile_expired_in_progress(conn, *, key, now=None, correlation_id=None)` | IN_PROGRESS 만료의 시간 기반 명시적 전이(배치 미연결) |
| `reconcile_unknown(conn, *, key, resolved_state, performed_by, result=None, now=None, correlation_id=None)` | ADR-017 §23 수동 조정(운영자 식별자 필수). **(이번 갱신 반영)** `result` 파라미터 추가 — 수동 조정 후에도 `get_completed_result()`로 재조회 가능 |

**저장 계층 반환 classification**: `CREATED` / `RETRY_ACCEPTED` / `DUPLICATE_LIVE` / `IDEMPOTENCY_CONFLICT` / `RECONCILIATION_REQUIRED` / `POLICY_UNDETERMINED` / `ABSENT` / `RECORDED` / `CACHED_RESULT` / `RECONCILED` / `MARKED_UNKNOWN` / `NO_ACTION`.

### 1-2. `gas_orchestration.py`(격리 통합 계층, 신규)

| 함수/타입 | 역할 |
|---|---|
| `execute_with_idempotency(conn, *, key, fingerprint, gas_adapter, prepare_dispatch=None, now=None, correlation_id=None)` | 실행권 판정 → (선택) 전송 준비 → GAS 호출 → 결과 기록을 한 흐름으로 엮는 오케스트레이션. 1회 호출=1회 시도(재시도 루프 없음) |
| `GasResponse(success, retryable=False, result=None)` | `gas_adapter`가 예외 없이 반환해야 하는 확정 응답 |
| `OrchestrationResult(outcome, gas_called, record_write_ok, store_result=None, detail=None)` | 반환 타입 |

**orchestration outcome 전체 목록**: `NOT_SENT_BLOCKED` / `NOT_SENT_CACHED` / `NOT_SENT_PREP_FAILED` / `SENT_SUCCESS` / `SENT_FAILED_RETRYABLE` / `SENT_FAILED_FINAL` / `SENT_UNCERTAIN`.

## 2. fingerprint — 생성 책임과 정규화 규칙(변경 없음, 재확인)

- **이 모듈은 fingerprint를 계산하지 않는다.** 호출부(HMAC 서명 계층)가 계산해 문자열로 전달하면, 저장·형식검증·비교만 수행한다.
- ADR-017 §12 Canonical String은 이미 `<payloadHash>`(SHA-256)를 포함한다 — 이 값을 fingerprint로 재사용하자는 **제안**이며, ADR이 확정한 사실은 아니다(Open Question).
- **payload 정규화 규칙 자체는 미확정이다.** 모든 테스트는 합성(synthetic) fingerprint 문자열만 사용했다.
- 비교 범위: 기존 행이 **살아있는 경우에만** fingerprint를 비교한다. 다르면 `IDEMPOTENCY_CONFLICT` + 기존 행 완전 불변. 로그에는 원문 fingerprint/payload를 남기지 않고 SHA-256 앞 8자 지문만 기록한다(ADR-017 §19 관행 재사용).

## 3. 결과 불확실 시 처리 — 즉시 UNKNOWN 기록(이번 갱신 핵심)

- **세 가지 불확실성 구분**: 전송 전 실패(`NOT_SENT_*`, GAS 미호출) / 전송 후 결과 불확실(`SENT_UNCERTAIN`) / 확정 성공·실패(`SENT_SUCCESS`/`SENT_FAILED_*`).
- `gas_adapter` 호출이 **어떤 예외든** 던지면, **예외 타입으로 "미전송"을 추정하지 않고** 전부 동일하게 "결과 불확실"로 취급한다(`RequestException`만으로 미전송을 단정하지 않음 — ADR-017 §7-5 "완전한 트랜잭션 불가능" 전제).
- 불확실성을 감지한 **즉시** `store.mark_unknown()` 호출을 시도한다 — 기존 `IN_PROGRESS` TTL(60초)이 자연 경과하기를 기다리지 않는다. `mark_unknown()`은 이번 갱신에서 신규 추가한 함수로, `reconcile_expired_in_progress()`(TTL 경과 시에만 동작하는 시간 기반 함수)와 달리 **TTL 경과 여부와 무관하게** 즉시 전이시킨다.
- **GAS 성공 후 로컬 결과 저장 실패도 같은 원칙**: `record_outcome()` 자체가 실패하면 GAS를 재호출하지 않고 `mark_unknown()`으로 폴백한다.

## 4. 결과·UNKNOWN 기록이 모두 실패해도 TTL 전후 재호출 차단(실측 확인)

| 시점 | Fake GAS 누적 호출 | 레코드 상태 | 행 수 |
|---|---|---|---|
| 이중 실패(`record_outcome`+`mark_unknown` 둘 다 COMMIT 실패) 직후 | 1회 | `IN_PROGRESS`(두 UPDATE 모두 rollback) | 1 |
| 〃 + TTL 이내 재요청(안전망 1차 확인) | 1회(증가 없음) | `IN_PROGRESS`, `DUPLICATE_LIVE`로 차단 | 1 |
| 〃 + **가상시계로 IN_PROGRESS TTL 경과 후** 재요청(실제 대기 없음) | **1회(증가 없음)** | `UNKNOWN`(기존 lazy 전이로 자연 수렴) | 1 |

즉, 명시적 기록 시도가 이중으로 실패해도 **TTL 이내·이후 어느 시점에 재요청이 와도 Fake GAS는 다시 호출되지 않는다** — 기존 `IN_PROGRESS`+TTL 안전망이 "최후의 방어선"으로 실제 작동함을 가상시계만으로(실제 대기 없이) 확인했다.

## 5. 준비 단계 실패(`NOT_SENT_PREP_FAILED`, 이번 갱신 신규)

- 실행권(`CREATED`/`RETRY_ACCEPTED`) 획득과 `gas_adapter` 호출 사이에, 이전 STEP까지는 별도 "전송 준비" 단계가 전혀 없었다. 이번 갱신에서 선택적 콜러블 `prepare_dispatch`를 신설해 그 지점(HMAC 서명 생성·Nonce 발급 등, 아직 네트워크로 나가지 않은 작업)을 명시적으로 주입 가능하게 했다.
- `prepare_dispatch`가 예외를 던지면: **GAS 호출 0회**, 실행권을 얻지 못해 차단되는 `NOT_SENT_BLOCKED`와 구분되는 **별도 outcome `NOT_SENT_PREP_FAILED`**를 반환, `try_create()`가 만든/재오픈한 행을 **그대로 보존**(`IN_PROGRESS`, 추가 조치 없음).
- **후속 처리 정책은 미확정이다** — 이 실패가 "확정 미전송"임이 구조적으로 보장됨에도, 레코드를 즉시 삭제하거나 재사용 가능하게 만들지 않고 기존 `IN_PROGRESS`+TTL 규칙을 그대로 따르게 했다(보수적 기본값일 뿐, "이것이 올바른 정책"이라고 확정한 것은 아님 — Open Question).
- 인증·권한검사(RBAC)는 여전히 이 함수 호출 **이전**(라우트 계층)에서 수행한다는 기존 설계를 그대로 유지했다 — `prepare_dispatch`로 옮기지 않았다.

## 6. adapter 주입 구조와 테스트 범위(명시)

- `gas_adapter`·`prepare_dispatch`는 **호출부가 주입하는 임의의 콜러블**이다. 이 모듈은 그 구현을 제공하지 않는다.
- **테스트는 전부 `FakeGasAdapter`(`tests/test_gas_orchestration.py` 전용 더블)만 사용했다.** 운영 GAS 연동 adapter는 **작성·연결되지 않았다(미구현)**.
- 이 파일에 `requests`/`httpx` 등 네트워크 라이브러리가 없다는 사실 자체가 "이 구조가 네트워크 호출을 할 수 없다"는 것을 증명하지는 않는다 — adapter는 의존성 주입 지점이므로, 실제 네트워크를 호출하는 adapter가 주입되면 이 계층을 통해 네트워크 호출이 발생할 수 있는 구조다. 이번 STEP에서는 그런 adapter를 작성·연결하지 않았을 뿐이다.
- `routes_admin_portal.py` 등 운영 라우트 어디에서도 `idempotency_store`·`gas_orchestration`을 import하지 않는다(grep 재확인, 0건) — HMAC·Nonce 실제 구현도 전혀 없다(여전히 NOT IMPLEMENTED).

## 7. 재시도 실행권 획득 방식(이전 STEP 확인, 변경 없음)

- 살아있는 `FAILED_RETRYABLE`(terminal 아님, ADR-017 §16 재시도 대상)에 **동일 key·동일 fingerprint**로 요청이 오면 `try_create()`가 같은 트랜잭션 안에서 `IN_PROGRESS`로 재오픈하고 `RETRY_ACCEPTED`를 반환한다.
- 동시 8건 요청 중 정확히 1건만 `RETRY_ACCEPTED`, 나머지는 `DUPLICATE_LIVE`임을 동시성 테스트로 확인(구현 변경 없음).
- **재시도 상한(§16 "최대 3회")·간격 집행은 이 계층의 책임이 아니다** — `gas_orchestration.py`도 1회 호출당 1회 시도만 수행하며 횟수를 세지 않는다(Open Question).

## 8. 남은 과제(payload·재시도·HTTP 응답·만료 후 정책)

| 영역 | 남은 과제 |
|---|---|
| payload | 정규화 규칙(어떤 JSON 직렬화를 해시하는지) 미확정 |
| 재시도 | 상한(3회)·간격(백오프) 집행 책임 소재 미확정, 이 계층은 횟수 집계 없음 |
| HTTP 응답 | `result`(자유 문자열)를 실제 응답 JSON/상태코드로 변환하는 계층 없음 |
| 만료 후 정책 | `SUCCEEDED`/`FAILED_RETRYABLE`/`FAILED_FINAL` TTL 경과 후 전이 대상, `UNKNOWN` 48h 경과 후 처리 — 전부 ADR-017에 명시 없음(`POLICY_UNDETERMINED`만 반환, 삭제·재생성 없음) |
| 준비 단계 실패 | `NOT_SENT_PREP_FAILED` 발생 시 레코드 후속 처리(즉시 정리 허용 여부) 미확정(§5) |
| 통합 | HMAC 서명 생성·검증, Nonce 이중구조(GAS CacheService 연동, 별도 PM 승인 필요), Grace 기간 적용, 감사로그 신규 이벤트 연계, 운영 adapter 작성, 라우트 배선 |
| key 관리 | "같은 작업 재시도 vs 새 작업"을 위한 idempotency key 생성 규칙(클라이언트/UX 설계) 미정 |

## 9. 테스트 수·명령·결과

```
명령: python3 -m unittest tests.test_idempotency_store tests.test_gas_orchestration
결과: Ran 38 tests in 1.493s — OK (38/38 PASS, 0 FAIL, 0 ERROR)
```

- **저장 모듈(`test_idempotency_store.py`) 28개**: 동일 key 동시생성, 서로 다른 key 독립성, 상태전이 허용/거절, TTL 경계(5상태), 두 호출경로 동일결과, UNKNOWN 차단+행보존, 정책미확정 차단, 수동조정, 형식검증, OperationalError rollback, cleanup, fingerprint 충돌/중복(단독·동시성), 완료결과 재조회 3종, 결과기록 rollback, FAILED_RETRYABLE 허용/충돌/만료 구분, 전경로 일관 차단, 명시적 만료전이, 동시 재시도 실행권 단일성.
- **orchestration 계층(`test_gas_orchestration.py`) 10개**: 최초 성공+결과 재사용, 다른 fingerprint 충돌(GAS 0회), 동시 요청 GAS 정확히 1회, 전송 전 확정 실패(실행권 미획득) 2종, timeout 후 즉시 UNKNOWN+재요청 차단, 성공 후 로컬 기록 실패(폴백 성공), 이중 기록 실패 직후 안전망, **이중 기록 실패 + TTL 경과 후 수렴**(신규), **준비 단계 실패**(신규), 수동 조정 후 결과 조회.
- 임시 리소스 사후 확인 0건.

---

**완료 조건 재확인**: 이 문서와 코드는 **Commit8-3b 전체 완료를 의미하지 않는다.** 운영 GAS·Google Sheets에 접근하지 않았고, 예약 생성·변경 API를 호출하지 않았으며, 어떤 운영 라우트에도 배선되지 않았다. HMAC·Nonce는 구현되지 않았으며, 운영 adapter도 작성·연결되지 않았다(테스트는 Fake adapter만 사용). **OFFICIAL PHASE 1 GATE는 이 구현과 무관하게 BLOCKED INPUT으로 유지된다.**
