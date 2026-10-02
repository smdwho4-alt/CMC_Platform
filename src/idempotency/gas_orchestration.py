# -*- coding: utf-8 -*-
"""
CSHSP Idempotency + GAS 호출 오케스트레이션 — Sprint8 Commit8-3b (격리 개발, 로컬 전용)

`idempotency_store.py`의 실행권 판정과, 실제(또는 Fake) GAS 호출, 그리고 결과
기록을 하나의 흐름으로 엮는 **격리 통합 계층**이다. **운영 라우트
(`src/api/routes_admin_portal.py`)는 이 모듈을 아직 import하지 않는다.**

**adapter 주입 구조에 대한 명시**: `gas_adapter`(및 아래 `prepare_dispatch`)는
호출부가 주입하는 **임의의 콜러블**이며, 이 파일 자체는 그 구현을 제공하지
않는다. 이번 STEP의 테스트(`tests/test_gas_orchestration.py`)는 전부 Fake
어댑터만 사용했고, **운영 GAS 연동 어댑터는 아직 작성·연결되지 않았다**
(미구현). 이 파일에 `requests`/`httpx` 등 네트워크 라이브러리가 없다는
사실 자체가 "이 구조가 네트워크 호출을 할 수 없다"는 것을 증명하지는
않는다 — adapter는 의존성 주입 지점이므로, 실제 네트워크를 호출하는
adapter가 주입되면 이 계층을 통해 네트워크 호출이 발생할 수 있는 구조다.
이번 STEP에서는 그런 adapter를 작성하거나 연결하지 않았을 뿐이다.

## 세 가지 불확실성 구분(scratchpad 설계 candidate §4 보완)

- **전송 전 실패(NOT_SENT_BLOCKED/NOT_SENT_CACHED)**: `try_create()`가
  `CREATED`/`RETRY_ACCEPTED` 외의 값을 반환하면 `gas_adapter`를 **호출조차
  하지 않는다.** `IDEMPOTENCY_CONFLICT`·살아있는 `IN_PROGRESS`·
  `RECONCILIATION_REQUIRED`·`POLICY_UNDETERMINED`는 전부 이 범주다. 살아있는
  `SUCCEEDED`/`FAILED_FINAL`(`DUPLICATE_LIVE` + 해당 state)은 캐시된 결과를
  그대로 반환한다(`NOT_SENT_CACHED`).
- **전송 후 결과 불확실(SENT_UNCERTAIN)**: `gas_adapter` 호출이 **어떤
  예외든** 던지면(`except Exception`), **그 예외의 타입을 보고 "미전송"을
  추정하지 않는다** — `requests.RequestException`(또는 Fake가 던지는 임의의
  예외)만으로는 요청이 실제로 GAS에 도달해 처리되었는지 아닌지 FastAPI가
  구분할 방법이 없다(ADR-017 §7-5 "완전한 트랜잭션 불가능" 전제). **전송
  여부를 증명할 수 없는 실패는 전부 동일하게 UNKNOWN(재조정 필요)으로
  취급한다** — 예외 타입별로 "이건 분명히 안 보내진 것" 같은 세부 분류를
  시도하지 않는다. 감지 즉시(`store.mark_unknown()`) 기록을 시도하며, 60초
  TTL이 자연 경과하기를 기다리지 않는다.
- **확정 성공·실패(SENT_SUCCESS/SENT_FAILED_RETRYABLE/SENT_FAILED_FINAL)**:
  `gas_adapter`가 예외 없이 응답 객체를 반환하면 그 결과는 확정이다.
  `record_outcome()`으로 즉시 기록한다.

## GAS 성공 후 로컬 기록 실패도 "같은 원칙"으로 처리

`gas_adapter`가 성공(또는 확정 실패)을 반환했더라도, 그 결과를
`record_outcome()`으로 저장하는 과정 자체가 실패하면(`IdempotencyError`),
**GAS를 다시 호출하지 않는다.** 대신 `store.mark_unknown()`으로 "지금 당장
불확실성을 기록"을 시도한다 — 이 함수가 아는 진실(성공/실패)을 저장할 수는
없었지만, 최소한 "이 레코드는 확인이 필요하다"는 신호는 남긴다. **그 시도
마저 실패하면 더 이상 아무것도 하지 않는다** — 기존 `IN_PROGRESS` + 60초
TTL 안전망(`try_create()`가 이미 만료된 `IN_PROGRESS`를 `RECONCILIATION_
REQUIRED`로 분류)이 최후의 방어선이 된다. 이 계층은 그 안전망을 우회하거나
대체하지 않는다.

## 실행권 획득 후 ~ 실제 전송 전 "준비 단계"(이번 보완)

v1(이전 STEP)에는 실행권(`CREATED`/`RETRY_ACCEPTED`) 획득과 `gas_adapter`
호출 사이에 **별도의 "전송 준비" 단계가 전혀 없었다** — try_create()가 끝나면
곧바로 gas_adapter를 호출했다. 실제 통합에서는 이 사이에 HMAC 서명 생성,
Nonce 발급, 요청 객체 구성 등(ADR-017 §12) "아직 네트워크로 나가지는 않은"
준비 작업이 있을 수 있고, 그 단계 자체가 실패할 수 있다(예: 서명 키 로드
실패). **이번 보완에서 그 지점을 선택적 콜러블 `prepare_dispatch`로
명시적으로 노출했다**:

- `prepare_dispatch`가 주어지고 예외를 던지면, `gas_adapter`는 **호출되지
  않는다**(0회) — 이것은 "요청이 확실히 전송되지 않았다"는 것을 코드 구조
  자체로 보장하는 경우이므로(네트워크 시도 자체가 없었음), `SENT_UNCERTAIN`
  (불확실)이 아니라 **`NOT_SENT_PREP_FAILED`라는 별도 outcome**으로
  분류한다 — 실행권을 얻지 못해 애초에 차단된 `NOT_SENT_BLOCKED`와도
  다르다(실행권은 얻었다는 점에서 구분됨).
- 이 경우 **try_create()가 만든/재오픈한 행을 그대로 둔다**(삭제·UNKNOWN
  전이 등 추가 조치 없음) — 기존 `IN_PROGRESS`+TTL 안전망에 그대로 맡긴다.
  준비 단계 실패를 "확정 실패"로 기록하지 않는 이유: 준비 단계 자체가
  side effect를 일으켰을 가능성을 완전히 배제할 수 없는 일반적인 경우까지
  고려해, 섣불리 레코드를 되돌리거나 재사용 가능하게 만들지 않는 보수적
  설계를 유지한다.
- **인증·권한검사(RBAC)는 여전히 이 함수가 호출되기 "이전"(라우트 계층)에서
  수행된다는 기존 설계를 그대로 유지한다** — `prepare_dispatch`는 그보다
  뒤, "실행권 획득 후 ~ GAS 호출 전" 사이에만 해당하는 전송 준비 작업만
  표현하기 위한 것이며, 인증·권한 로직을 이 계층으로 옮기는 것이 아니다.

## 이 계층이 하지 않는 것(명시)

- **자동 재시도를 구현하지 않는다.** `execute_with_idempotency()`는 1회
  호출당 1회의 실행 시도만 수행한다. 재시도는 호출부(별도의 새 HTTP 요청,
  새 nonce, 동일 key)가 담당한다 — 이 함수가 내부적으로 루프를 돌며 GAS를
  여러 번 부르지 않는다.
- **재시도 횟수 상한(ADR-017 §16 "최대 3회")·간격(지수 백오프)을 집행하지
  않는다.** 이 계층은 들어온 요청 하나하나에 대해 실행권만 판정할 뿐,
  "몇 번째 시도인지" 세지 않는다 — 후속 통합 과제(Open Question).
- **payload 정규화 규칙을 확정하지 않는다.** `fingerprint`는 호출부가
  계산해 주입하는 값을 그대로 쓴다(`idempotency_store.py`와 동일 원칙).
- **HMAC·Nonce가 구현되었다고 표현하지 않는다.** 이 모듈은 Idempotency
  실행권 판정과 결과 기록만 다루며, 서명 생성·검증, Nonce 이중저장은
  포함하지 않는다(여전히 NOT IMPLEMENTED, 별도 작업).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import idempotency_store as store  # noqa: E402


@dataclass(frozen=True)
class GasResponse:
    """`gas_adapter`가 예외 없이 반환해야 하는 확정 응답. 호출부(실제 GAS
    연동 시에는 `sheets_write.update_status()` 결과를 이 형태로 변환하는
    어댑터가 필요하다 — 이 모듈은 그 변환 로직을 포함하지 않는다)."""

    success: bool
    retryable: bool = False  # success=False일 때만 의미 있음(ADR-017 §16 "retryable 분류")
    result: Optional[str] = None  # 비식별 요약값. 원문 payload/PII를 넣지 않을 책임은 호출부에 있음


@dataclass(frozen=True)
class OrchestrationResult:
    """`execute_with_idempotency()`의 반환 타입.

    outcome 전체 목록:
      NOT_SENT_BLOCKED   — 실행권을 얻지 못해 GAS를 호출하지 않음(충돌/
                            처리중/재조정필요/정책미확정)
      NOT_SENT_CACHED    — 이미 완료된 동일 요청, 캐시된 결과 반환(GAS 미호출)
      NOT_SENT_PREP_FAILED — 실행권은 얻었으나 `prepare_dispatch`(전송 준비
                            단계)가 실패해 GAS를 호출하지 않음(기존 행 보존,
                            `NOT_SENT_BLOCKED`와 달리 실행권 자체는 획득했었음)
      SENT_SUCCESS       — GAS 호출 성공 + 로컬 기록 성공
      SENT_FAILED_RETRYABLE — GAS가 재시도 가능한 실패 반환 + 로컬 기록 성공
      SENT_FAILED_FINAL     — GAS가 최종 실패 반환 + 로컬 기록 성공
      SENT_UNCERTAIN     — GAS 호출 자체가 예외를 던졌거나, GAS 응답은
                            받았으나 그 결과를 로컬에 기록하는 데 실패함
                            (`record_write_ok`로 안전망(mark_unknown) 성공
                            여부를 구분)
    """

    outcome: str
    gas_called: bool
    record_write_ok: Optional[bool]  # None이면 애초에 기록 시도 자체가 없었음(NOT_SENT_*)
    store_result: Optional[store.IdempotencyResult] = None
    detail: Optional[str] = None  # 비식별 메모(예외 타입명 등). PII/payload 없음


def _try_mark_unknown(
    conn, *, key: str, now: Optional[datetime], correlation_id: Optional[str]
) -> bool:
    """`store.mark_unknown()`을 best-effort로 시도한다. 실패해도 예외를
    전파하지 않는다 — 호출부가 이 실패를 "GAS 재호출" 신호로 쓰지 않도록,
    이 함수 자체가 안전하게 True/False만 반환한다(기존 IN_PROGRESS+TTL
    안전망에 맡김)."""
    try:
        store.mark_unknown(conn, key=key, now=now, correlation_id=correlation_id)
        return True
    except (store.IdempotencyError, ValueError):
        return False


def execute_with_idempotency(
    conn,
    *,
    key: str,
    fingerprint: str,
    gas_adapter: Callable[..., GasResponse],
    prepare_dispatch: Optional[Callable[[], None]] = None,
    now: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
) -> OrchestrationResult:
    """Idempotency 실행권을 판정하고, 얻은 경우에만(선택적으로
    `prepare_dispatch()`를 먼저 실행한 뒤) `gas_adapter`를 호출하고 결과를
    기록한다. 재시도 루프 없음(1회 호출 = 1회 시도).

    `gas_adapter(key=key, fingerprint=fingerprint)` 형태로 호출한다 —
    키워드 인자이므로 Fake/실제 어댑터 모두 동일 시그니처를 따라야 한다.
    `prepare_dispatch`는 인자 없이 호출되며(`prepare_dispatch()`), 예외를
    던지면 `gas_adapter`는 전혀 호출되지 않는다(모듈 docstring "준비 단계"
    참조). 생략 시(기본값 None) 이전 동작과 동일하게 바로 `gas_adapter`를
    호출한다."""
    acquire = store.try_create(
        conn, key=key, fingerprint=fingerprint, now=now, correlation_id=correlation_id
    )

    if acquire.classification == "IDEMPOTENCY_CONFLICT":
        return OrchestrationResult(
            outcome="NOT_SENT_BLOCKED", gas_called=False, record_write_ok=None, store_result=acquire
        )

    if acquire.classification in ("RECONCILIATION_REQUIRED", "POLICY_UNDETERMINED"):
        return OrchestrationResult(
            outcome="NOT_SENT_BLOCKED", gas_called=False, record_write_ok=None, store_result=acquire
        )

    if acquire.classification == "DUPLICATE_LIVE":
        if acquire.state in ("SUCCEEDED", "FAILED_FINAL"):
            cached = store.get_completed_result(
                conn, key=key, fingerprint=fingerprint, now=now, correlation_id=correlation_id
            )
            return OrchestrationResult(
                outcome="NOT_SENT_CACHED", gas_called=False, record_write_ok=None, store_result=cached
            )
        # 살아있는 IN_PROGRESS — 다른 요청이 이미 처리 중(동시 요청에서 실행권을
        # 얻지 못한 경우). GAS를 호출하지 않는다.
        return OrchestrationResult(
            outcome="NOT_SENT_BLOCKED", gas_called=False, record_write_ok=None, store_result=acquire
        )

    # 여기 도달하면 acquire.classification은 "CREATED" 또는 "RETRY_ACCEPTED"뿐이다
    # (idempotency_store.try_create()의 반환값 집합이 그렇게 보장함).

    if prepare_dispatch is not None:
        try:
            prepare_dispatch()
        except Exception as exc:  # noqa: BLE001 - "확정 미전송": 네트워크 시도 자체가 없었음
            return OrchestrationResult(
                outcome="NOT_SENT_PREP_FAILED",
                gas_called=False,
                record_write_ok=None,
                store_result=acquire,
                detail=f"prepare_dispatch_exception:{type(exc).__name__}",
            )

    try:
        response = gas_adapter(key=key, fingerprint=fingerprint)
    except Exception as exc:  # noqa: BLE001 - 예외 타입으로 "미전송"을 추정하지 않음(모듈 docstring)
        write_ok = _try_mark_unknown(conn, key=key, now=now, correlation_id=correlation_id)
        return OrchestrationResult(
            outcome="SENT_UNCERTAIN",
            gas_called=True,
            record_write_ok=write_ok,
            detail=f"gas_call_exception:{type(exc).__name__}",
        )

    if response.success:
        try:
            recorded = store.record_outcome(
                conn, key=key, outcome_state="SUCCEEDED", result=response.result,
                now=now, correlation_id=correlation_id,
            )
            return OrchestrationResult(
                outcome="SENT_SUCCESS", gas_called=True, record_write_ok=True, store_result=recorded
            )
        except store.IdempotencyError:
            write_ok = _try_mark_unknown(conn, key=key, now=now, correlation_id=correlation_id)
            return OrchestrationResult(
                outcome="SENT_UNCERTAIN",
                gas_called=True,
                record_write_ok=write_ok,
                detail="record_outcome_failed_after_gas_success",
            )

    outcome_state = "FAILED_RETRYABLE" if response.retryable else "FAILED_FINAL"
    try:
        recorded = store.record_outcome(
            conn, key=key, outcome_state=outcome_state, result=response.result,
            now=now, correlation_id=correlation_id,
        )
        label = "SENT_FAILED_RETRYABLE" if response.retryable else "SENT_FAILED_FINAL"
        return OrchestrationResult(
            outcome=label, gas_called=True, record_write_ok=True, store_result=recorded
        )
    except store.IdempotencyError:
        write_ok = _try_mark_unknown(conn, key=key, now=now, correlation_id=correlation_id)
        return OrchestrationResult(
            outcome="SENT_UNCERTAIN",
            gas_called=True,
            record_write_ok=write_ok,
            detail="record_outcome_failed_after_gas_failure",
        )
