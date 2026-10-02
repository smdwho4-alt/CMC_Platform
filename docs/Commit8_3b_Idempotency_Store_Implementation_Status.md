# Commit8-3b Idempotency Store — 구현 현황(격리 개발, 로컬 전용)

> **상태**: 격리 개발 worktree에서 작성한 저장 계층 최소 구현 현황이다. **Commit8-3b
> 전체 완료가 아니다.** 운영 라우트 연결·GAS/Sheets 접근·Push·배포는 수행하지 않았다.
> **OFFICIAL PHASE 1 GATE = BLOCKED INPUT 유지**(이 구현과 무관하게 고정, DR-B-02
> Phase 1 실행계획서 §4/§9.2).
> **작성일**: 2026-10-03
> **대상 코드**: `src/idempotency/idempotency_store.py`, `tests/test_idempotency_store.py`
> **기준 commit**: `9104ec3e35eef556433eb25b0af8579e0531b65b`(origin/main)

---

## 1. 모듈 API와 반환 분류

| 함수 | 역할 |
|---|---|
| `init_schema(data_dir)` | 스키마 생성(idempotent) |
| `connect(data_dir)` | 컨텍스트매니저 커넥션(WAL, `src/auth/auth_store.py`와 동일 house 컨벤션) |
| `try_create(conn, *, key, fingerprint, now=None, correlation_id=None)` | 생성/재시도 시도. 유일하게 쓰기 락(BEGIN IMMEDIATE)으로 원자성을 보장하는 핵심 함수 |
| `get_effective_state(conn, *, key, now=None, correlation_id=None)` | 순수 읽기 조회(부작용 없음) |
| `get_completed_result(conn, *, key, fingerprint, now=None, correlation_id=None)` | 완료 결과 재조회(순수 읽기, fingerprint 일치 확인 포함) |
| `record_outcome(conn, *, key, outcome_state, result=None, now=None, correlation_id=None)` | IN_PROGRESS → SUCCEEDED/FAILED_RETRYABLE/FAILED_FINAL 전이 + 결과 기록(단일 트랜잭션) |
| `reconcile_expired_in_progress(conn, *, key, now=None, correlation_id=None)` | IN_PROGRESS 만료의 명시적 전이(배치 미연결, 아래 §5) |
| `reconcile_unknown(conn, *, key, resolved_state, performed_by, now=None, correlation_id=None)` | ADR-017 §23 수동 조정(운영자 식별자 필수) |

**반환 classification 전체 목록**: `CREATED` / `RETRY_ACCEPTED` / `DUPLICATE_LIVE` / `IDEMPOTENCY_CONFLICT` / `RECONCILIATION_REQUIRED` / `POLICY_UNDETERMINED` / `ABSENT` / `RECORDED` / `CACHED_RESULT` / `RECONCILED` / `NO_ACTION`. 각 함수가 어떤 값을 반환하는지는 모듈 docstring과 `IdempotencyResult` dataclass 주석에 전부 명시했다.

## 2. fingerprint — 생성 책임과 정규화 규칙

- **이 모듈은 fingerprint를 계산하지 않는다.** 호출부(HMAC 서명 계층)가 계산해 문자열로 전달하면, 저장·형식검증·비교만 수행한다.
- ADR-017 §12 Canonical String은 이미 `<payloadHash>`(SHA-256)를 포함한다 — 이 값을 fingerprint로 재사용하자는 **제안**이며, ADR이 확정한 사실은 아니다(Open Question).
- **payload 정규화 규칙 자체(어떤 JSON 직렬화를 해시하는지)는 미확정이다.** 이번 구현·테스트는 전부 합성(synthetic) fingerprint 문자열로만 검증했으며, 운영 연계 시 정규화 규칙은 별도로 확정해야 한다.
- 비교 범위: 기존 행이 **살아있는 경우에만** fingerprint를 비교한다. 다르면 `IDEMPOTENCY_CONFLICT` + 기존 행 완전 불변(ROLLBACK). 만료되어 재조정이 필요한 행(UNKNOWN/정책미확정)은 fingerprint와 무관하게 차단한다.
- 로그·결과 어디에도 원문 fingerprint/payload를 남기지 않는다 — key와 동일하게 SHA-256 앞 8자 지문(ADR-017 §19 Nonce 지문 관행 재사용)만 기록한다.

## 3. 결과 캐시 구현 범위

- `record_outcome()`이 상태 전이와 **같은 UPDATE문·같은 트랜잭션**으로 `result`(호출부가 만드는 비식별 요약 문자열, 500자 제한)를 기록한다.
- `get_completed_result()`가 `SUCCEEDED`/`FAILED_FINAL`(라이브 상태)일 때만 그 값을 반환한다(`CACHED_RESULT`).
- **HTTP 상태코드·응답 JSON 스키마·운영 보존기간은 이 모듈이 정의하지 않는다** — `result`는 자유 형식 문자열일 뿐이며, 실제 API 응답으로 어떻게 변환할지는 호출부/API 계약 단계의 몫이다(Open Question).

## 4. 재시도 실행권 획득 방식(이번 STEP 확인)

- 살아있는 `FAILED_RETRYABLE`(terminal 아님, ADR-017 §16 재시도 대상)에 **동일 key·동일 fingerprint**로 요청이 오면, `try_create()`가 **같은 트랜잭션(BEGIN IMMEDIATE) 안에서** 행을 `IN_PROGRESS`로 재오픈하고 `RETRY_ACCEPTED`를 반환한다(새 행 생성 아님, 기존 행 재사용).
- **동시성 확인(신규 테스트 `test_concurrent_retry_on_live_failed_retryable_grants_single_execution_right`, 8-worker `ThreadPoolExecutor`+`Barrier`)**: 동일 key·동일 fingerprint로 동시에 들어온 8건 중 **정확히 1건만 `RETRY_ACCEPTED`**(실행권 획득), 나머지 7건은 `DUPLICATE_LIVE`(실행권 없음)였다 — `BEGIN IMMEDIATE`가 "최초 생성"과 동일한 직렬화 보장을 재오픈에도 적용하므로, **기존 구현을 수정하지 않고 테스트만 추가**해 확인했다(PASS, 구현 변경 없음).
- 다른 fingerprint의 동시 요청은 `IDEMPOTENCY_CONFLICT`로 차단되며 재오픈되지 않는다(기존 테스트로 이미 확인됨).
- **제한 명시**: 재시도 **상한(ADR-017 §16 "최대 3회") 및 간격(지수 백오프 1→2→4초+Jitter)의 집행(enforcement)은 이 저장 계층의 책임이 아니다.** `RETRY_ACCEPTED`는 몇 번째 재시도인지 세지 않는다 — 호출부(클라이언트/상위 서비스 계층)가 횟수·간격을 관리해야 한다(Open Question, 저장소 계층에서 강제할지는 미확정).

## 5. 만료 후 정책 미확정 사항(변경 없음, 재확인)

- `SUCCEEDED`/`FAILED_RETRYABLE`/`FAILED_FINAL`의 TTL 경과 후 전이 대상, `UNKNOWN` 자신의 48시간 경과 "이후" 처리 — ADR-017 어디에도 명시되어 있지 않다. `POLICY_UNDETERMINED`만 반환하고 삭제·재생성하지 않는다.
- `get_effective_state()`는 순수 읽기라 조회만으로는 물리적 전이가 일어나지 않는다(의도된 설계) — 그러나 **유효 상태가 UNKNOWN이면 물리적 상태가 아직 IN_PROGRESS여도 모든 경로(`get_effective_state`/`get_completed_result`/`try_create`)가 동일하게 자동 재실행을 차단**함을 전용 테스트로 확인했다.
- 실제 물리적 전이는 `try_create()` 또는 명시적 `reconcile_expired_in_progress()`(배치·스케줄러 미연결, 수동 호출 전제) 호출 시점에만 일어난다.
- "동일 key+동일 fingerprint=진짜 재시도" vs "우연한 fingerprint 충돌"의 완전한 구분은 여전히 이 모듈의 범위 밖이다.

## 6. 운영 라우트 미연결 및 남은 통합 과제

- `routes_admin_portal.py` 등 기존 쓰기 경로 어디에서도 이 모듈을 import하지 않는다(grep 재확인, 0건) — **완전히 격리된 상태**.
- 남은 과제: HMAC 실제 서명 검증 구현, Nonce 이중구조(GAS CacheService 연동, 별도 PM 승인 필요), Grace 기간 적용, 감사로그 신규 이벤트 연계, 라우트 배선, 재시도 횟수 상한 집행 책임 소재 확정, payload 정규화 규칙 확정, 응답 포맷/HTTP 코드 확정.

## 7. 테스트 수·명령·결과

```
명령: python3 -m unittest -v tests.test_idempotency_store   (worktree 루트에서)
결과: Ran 28 tests in 1.098s — OK (28/28 PASS, 0 FAIL, 0 ERROR)
```

28개 = 기존 27개(동일 key 동시생성, 서로 다른 key 독립성, 상태전이 허용/거절, TTL 경계, 두 호출경로 동일결과, UNKNOWN 차단+행보존, 정책미확정 차단, 수동조정, 형식검증, OperationalError rollback, cleanup, fingerprint 충돌/중복 단독·동시성, 완료결과 재조회 3종, 결과기록 rollback, FAILED_RETRYABLE 허용/충돌/만료 구분, 전경로 일관 차단, 명시적 만료전이) + 이번 STEP 신규 1개(동시 재시도 실행권 단일성). 임시 리소스 사후 확인 0건.

---

**완료 조건 재확인**: 이 문서와 코드는 **Commit8-3b 전체 완료를 의미하지 않는다.** 운영 GAS·Google Sheets에 접근하지 않았고, 예약 생성·변경 API를 호출하지 않았으며, 어떤 운영 라우트에도 배선되지 않았다. **OFFICIAL PHASE 1 GATE는 이 구현과 무관하게 BLOCKED INPUT으로 유지된다.**
