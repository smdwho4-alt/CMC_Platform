# -*- coding: utf-8 -*-
"""
CSHSP Sprint8 Commit8-3b — 서명·nonce·idempotency 격리 통합 흐름
(격리 개발, 로컬 전용. 합성 데이터·합성 키·로컬 SQLite·Fake Secondary·
Fake GAS만 사용한다. 운영 라우트·실제 GAS/Sheets·CacheService에
연결하지 않는다.)

이 모듈은 **접착(glue) 코드만** 제공한다 — 가드(`payload_schema_guard.py`/
`request_payload_schemas.py`), 서명(`signing_v2.py`/`signing_v2_guarded.py`),
nonce(`nonce_store.py`), idempotency 실행권·결과기록
(`idempotency_store.py`/`gas_orchestration.py`)은 **전혀 재작성하지
않고 그대로 호출만 한다.**

## 처리 순서(이번 통합이 정의하는 전체 흐름)

```
1. raw JSON 검증 + operation별 스키마 검증
   -> signing_v2_guarded.validate_and_normalize_payload()
      (내부적으로 payload_schema_guard.parse_json_strict() ->
       payload_schema_guard.validate_payload_schema_interim() ->
       request_payload_schemas.validate_request_schema() 순서로 체이닝됨,
       이미 구현되어 있음 — 이 모듈은 호출만 한다)
2. payload 정규화 + fingerprint 계산
   -> signing_v2.compute_payload_hash(payload) 결과를 그대로
      idempotency fingerprint로 재사용(fingerprint 재계산 로직 신규
      작성 없음 — gas_orchestration.py가 이미 "fingerprint는 호출부가
      계산해 주입"한다는 전제를 그대로 따른다)
3. idempotency 실행권 획득
   -> gas_orchestration.execute_with_idempotency()의 내부
      idempotency_store.try_create() 호출이 그대로 수행(이 모듈은
      execute_with_idempotency()를 호출할 뿐, try_create을 직접
      호출하지 않는다)
4. 실행권(CREATED/RETRY_ACCEPTED)을 얻은 요청만 nonce 발급 + v2 서명
   -> execute_with_idempotency()의 `prepare_dispatch` 콜백 안에서:
      nonce_store.generate_nonce() -> (발급 측 자체 nonce 기록, 아래
      "nonce 이중 역할" 참조) -> signing_v2.sign_v2()
5. Fake 수신부(FakeReceiver)에서 서명·timestamp·payloadHash 검증
   -> `gas_adapter` 콜백 안에서 FakeReceiver.receive() 호출 ->
      signing_v2.verify_v2()
6. 수신부 replay 차단 후 Fake 업무 실행
   -> FakeReceiver.receive() 내부: nonce_store.evaluate_and_register_nonce()
      (수신측 자체 Primary+Secondary, 발급측과 물리적으로 분리된 저장소)
      -> 통과 시에만 business_adapter(payload) 호출(Fake 업무)
7. 결과 기록 또는 UNKNOWN 처리
   -> execute_with_idempotency()가 돌아오는 즉시
      idempotency_store.record_outcome()/mark_unknown()을 내부적으로
      호출(이 모듈이 직접 호출하지 않음 — 기존 gas_orchestration.py가
      이미 담당)
```

## nonce 이중 역할 — 발급 측 vs 수신 측(ADR-017 §13과의 차이, 명시)

이 통합 흐름은 **서로 물리적으로 분리된 두 개의 nonce 저장소**를 쓴다:

- **발급 측(issuer) nonce 저장소**: `IssuerConfig.issuer_nonce_data_dir`
  (전용 SQLite 파일) + `IssuerConfig.issuer_secondary_store`(전용
  `FakeSecondaryNonceStore` 인스턴스). `prepare_dispatch()`가 nonce를
  생성한 직후 **자기 자신의 기록으로서** 이 저장소에 등록한다
  (`nonce_store.evaluate_and_register_nonce()` 재사용). 이 호출이
  `ACCEPTED`가 아니면(예: 발급 측 자체 2차 저장소 장애를 시뮬레이션)
  `PrepareDispatchError`를 던져 `prepare_dispatch` 실패로 처리된다
  (`NOT_SENT_PREP_FAILED`).
- **수신 측(receiver) nonce 저장소**: `FakeReceiver`가 생성 시 받는
  별도의 `receiver_data_dir` + 별도의 `FakeSecondaryNonceStore`
  인스턴스. `FakeReceiver.receive()`가 서명 검증 통과 직후 **이
  저장소에** nonce를 등록·검사한다 — **이것이 이 통합 흐름에서 실제
  replay를 차단하는 유일한 지점**이다.

**두 저장소는 절대 공유되지 않는다**(서로 다른 디렉터리의 서로 다른
SQLite 파일, 서로 다른 Python `FakeSecondaryNonceStore` 객체). 이는
다음 두 가지를 보장하기 위함이다:
1. 발급 때 자기 저장소에 등록한 nonce를, **수신부가 "이미 본
   nonce"라고 곧바로(오탐으로) 거절하지 않는다** — 네임스페이스가
   겹치지 않으므로 수신부 입장에서는 항상 처음 보는 nonce다
   (통합테스트 "정상 요청" 시나리오가 이를 실측 확인한다).
2. **진짜 replay(동일 signed envelope의 재전송)는 수신부 자신의
   저장소가 독자적으로 차단한다** — 발급 측 idempotency 계층을
   완전히 우회해 탈취한 envelope를 수신부에 직접 재전송하는 공격
   시나리오까지 막아야 하므로, 수신부가 발급 측의 판단에 의존하지
   않고 스스로 다시 검사해야 한다(통합테스트 "같은 signed envelope
   재전송" 시나리오가 이를 실측 확인한다).

### 기존 ADR-017 §13과 다른 점 — 임의 확정 아님, Open Question으로 보고

ADR-017 §13("Nonce 영속화 구조")이 확정한 것은 "FastAPI SQLite 1차
방어 + GAS CacheService 2차 방어"라는 **하나의 이중 판정**이며,
`nonce_store.py`의 기존 docstring은 이를 "발급 측(FastAPI)이 전송
전에 둘 다 확인"하는 단일 호출로 구현했다(이 모듈이 그 구현을
그대로 재사용한다 — 수신 측 nonce 저장소도 코드 수준에서는 동일한
`nonce_store.py` 함수를 재사용할 뿐, **새 로직을 추가하지 않았다**).

**그러나 "발급 측이 자기 nonce를 이중저장소에 또 기록한다"는 것과
"수신 측이 별도로 독자적인 이중저장소를 또 갖는다"는 것은 ADR-017
§13 원문이 명시적으로 요구한 것이 아니다** — ADR-017 §13은 단일
이중 판정만 설명했지, 그 판정을 "발급 측 1회 + 수신 측 1회"로
나누어 두 번 수행하라고 명시하지 않았다. **이번 "발급측 감사 기록
+ 수신측 독자적 replay 차단"이라는 양쪽 이중저장 구조 전체는
ADR-017이 확정한 구조가 아니라, 이 통합 흐름 범위 안에서 도입한
실험안(experimental proposal)이다** — 운영 ADR 개정 없이 이 해석을
운영 계약으로 확정하지 않는다(Open Question — PM/아키텍처 검토
필요). 아래 두 역할을 다시 한번 명확히 구분한다:

- **발급측 저장소의 역할 = 감사 기록(audit trail)**. 발급측
  Secondary가 DENY를 반환하는 경우는 **정상 경로에서는 드물다**
  (매번 새로 생성하는 랜덤 nonce가 우연히 이전 값과 같아야 하므로) —
  **그러나 "구조적으로 불가능"한 것은 아니다.** 이 모듈은
  `nonce_store.evaluate_and_register_nonce()`를 발급측·수신측
  양쪽에 동일하게 재사용하므로, 발급측도 DENY 경로를 그대로 가지고
  있다(테스트에서 `nonce_store.generate_nonce()`를 고정값으로
  패치하고 발급측 Secondary를 미리 오염시키는 방식으로 실제
  동작까지 확인했다 — 아래 `tests/test_signed_gas_integration.py`의
  발급측 DENY 테스트 참조). DENY든 ERROR든, 발급측에서 거절되면
  `prepare_dispatch`가 실패로 처리된다(§2 "서명 준비 실패" 재확인).
  **이 저장소는 replay를 막는 보안 경계가 아니다** — 그 역할은
  수신측 저장소가 맡는다.
- **수신측 저장소의 역할 = replay 차단(보안 경계)**. 이 통합 흐름에서
  실제로 "이 요청을 다시 처리해도 되는가"를 최종 결정하는 지점은
  오직 여기뿐이다.

## `FakeReceiver`의 SQLite는 실제 GAS 수신부 구현의 청사진이 아니다

`FakeReceiver`는 `nonce_store.py`(Primary SQLite + Secondary)를
**재사용하기 위한 테스트 편의**로 SQLite를 쓴다. **실제 GAS Apps
Script 런타임에는 로컬 파일시스템도 SQLite도 없다** — 이 점은
확실하다. 다만 **"그러므로 쓸 수 있는 저장 수단은
`PropertiesService`/`CacheService`뿐이다"라고 단정하지 않는다** —
Apps Script에는 예컨대 `JDBC` 서비스로 외부 데이터베이스(Cloud SQL
등)에 연결하는 방법도 있는 등, 이 작업이 모든 대안을 전수 조사하지
않았기 때문이다. 확실히 말할 수 있는 것은 "로컬 SQLite 같은
파일시스템 기반 저장소는 없다"는 사실뿐이다. 따라서 **`FakeReceiver`의
"Primary(SQLite)+Secondary" 이중구조를 실제 GAS 수신부가 그대로 가질
것처럼 표현하지 않는다** — 이것은 순전히 "기존 `nonce_store.py`
함수를 재작성 없이 재사용하기 위한 테스트 전용 선택"이며, 실제
수신측 구현의 설계도가 아니다.

### 실제 운영 구조로 옮길 때 고려할 사항(목록, 미확정 — 결정된 방향 아님)

1. **수신측에서 SQLite Primary는 그대로 쓸 수 없다**(위 사실 재확인).
   `CacheService` 단독 구조는 **하나의 미확정 후보안**일 뿐이며,
   이 작업이 그것을 운영 설계로 확정하지 않는다. 다른 대안(예: 외부
   DB 연결, Sheets 자체를 저장소로 쓰는 방법 등)도 함께 검토 대상이다.
2. `CacheService` 단독 구조를 채택한다면 **아래 항목들이 운영
   설계에서 반드시 해결돼야 한다**(이 실험안은 해결하지 않았다):
   - **캐시 유실·조기 제거(eviction) 후 replay 차단 한계** —
     CacheService 항목이 TTL 만료나 1,000항목 LRU eviction으로
     사라진 뒤 같은 nonce가 재전송되면, "이미 본 nonce"라는 기록
     자체가 없어 replay가 통과할 수 있다. 안전한 TTL 값과 "유실
     이후" 정책을 운영 설계에서 정해야 한다.
   - **동시 요청의 원자성** — CacheService의 조회+기록이 진짜
     원자적(atomic)인지, 아니면 `LockService` 같은 별도 잠금이
     필요한지 PoC#2가 이미 지적했고 아직 실측되지 않았다.
   - **저장소 장애 시 차단 방식** — CacheService 자체가 응답하지
     않거나 오류를 낼 때 fail-closed(차단)로 갈지, 다른 방식으로
     처리할지 운영 설계가 정해야 한다(이 실험안의 수신측은 ERROR를
     `retryable=True`로 분류했지만, 이는 잠정적 선택이다 — §4 재확인).
3. "발급측 감사 기록"을 운영에 유지할지 자체도 재검토 대상이다 —
   유지한다면 지금처럼 `nonce_store.py`의 "Primary+Secondary 판정
   함수"를 그대로 재사용할 필요는 없다(감사 기록은 replay 판정이
   아니므로 더 단순한 기록 방식으로 충분할 수 있음).
4. 실제 GAS `doPost` 핸들러 코드 작성·배포, `Utilities.computeHmacSha256Signature`
   기반 서명 검증 포팅(이미 `tests/cross_validation/gas/`에서 격리
   검증한 로직 재사용 가능), 실제 공유 Secret 프로비저닝 방법(PM 승인
   필요) 확정.
5. 이 실험안의 "발급측/수신측 양쪽 이중저장" 자체를 ADR-017 §13
   개정안으로 제출할지, 더 단순한 구조로 축소할지 PM/아키텍처
   결정이 필요하다.

## 이 모듈이 검증하지 않는 것(명시)

- **인증·권한검사(RBAC)는 이 모듈 호출의 전제조건일 뿐이다.** 이
  Fake 흐름은 `handle_request()`가 호출되기 전에 이미 인증·권한
  확인이 끝났다고 가정한다 — 이 흐름 자체가 인증·권한을 검증했다고
  표현하지 않는다(`gas_orchestration.py` 모듈 docstring의 기존 원칙
  재확인).
- **실제 HTTP 요청/응답 계약을 확정하지 않는다.** `handle_request()`는
  `gas_orchestration.OrchestrationResult`(내부 전용 타입)를 그대로
  반환한다 — 상태 코드·JSON 응답 스키마로의 매핑은 이 모듈의 책임이
  아니다.
- **오류 분류(`SIGNATURE_REJECTED:*`/`NONCE_REJECTED:*`)는 내부
  참고용**이며 운영 오류코드로 확정된 것이 아니다
  (`signing_v2.py`/`nonce_store.py`의 "오류 분류는 내부용이다" 원칙
  재확인). 각 분류의 `retryable` 판단(아래 `FakeReceiver.receive()`
  참조)도 이 통합 테스트가 내린 내부적 선택이며 운영 정책으로 확정된
  것이 아니다.
- **로깅**: 이 모듈 자체는 로깅을 수행하지 않는다(순수 함수/클래스
  위주). secret·서명 원문·원문 payload를 로깅하지 않을 책임은
  호출부에 있다(기존 원칙 재확인).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_ROOT / "src" / "reservation"))  # json_store.KST (house convention)

import idempotency_store as store  # noqa: E402
import gas_orchestration as orch  # noqa: E402
import nonce_store  # noqa: E402
import signing_v2  # noqa: E402
import signing_v2_guarded as guarded  # noqa: E402


@dataclass(frozen=True)
class SignedEnvelope:
    """발급 측이 만들어 "전송"(이 격리 흐름에서는 함수 호출)하는 서명된
    요청의 내부 표현. 실제 HTTP 바디 스키마를 확정하지 않는다."""

    method: str
    operation: str
    timestamp: str
    nonce: str
    idempotency_key: str
    key_id: str
    payload: dict
    signature: str


class PrepareDispatchError(RuntimeError):
    """발급 측 준비 단계(서명 생성·nonce 자체 기록 등) 실패.
    `gas_orchestration.execute_with_idempotency()`의 `prepare_dispatch`
    계약대로, 이 예외가 발생하면 수신측(`gas_adapter`)은 전혀 호출되지
    않는다(`NOT_SENT_PREP_FAILED`)."""


@dataclass(frozen=True)
class IssuerConfig:
    """발급 측 설정. `issuer_secondary_store`는 호출부(테스트)가 미리
    생성해 재사용하는 인스턴스를 넘겨야 한다(매 호출마다 새로 만들면
    "발급 측 자체 기록"이 누적되지 않아 의미가 없어진다)."""

    secret: str
    key_id: str
    issuer_nonce_data_dir: "str | Path"
    issuer_secondary_store: "nonce_store.FakeSecondaryNonceStore"


class FakeReceiver:
    """실제 GAS Apps Script 수신부(doPost 핸들러)를 대신하는 테스트
    전용 더블. 자체 nonce 저장소(발급 측과 물리적으로 분리)와 자체
    `KeyRegistry`를 가지며, `business_adapter`(Fake 업무 실행)를
    주입받는다. 이 클래스는 `signing_v2.verify_v2()`/
    `nonce_store.evaluate_and_register_nonce()`를 그대로 호출할 뿐,
    서명·nonce 검증 로직을 재작성하지 않는다."""

    def __init__(
        self,
        receiver_data_dir: "str | Path",
        *,
        key_registry: "signing_v2.KeyRegistry",
        business_adapter: Callable[[dict], str],
        max_skew_seconds: int,
        secondary_ttl_seconds: int = nonce_store.DEFAULT_SECONDARY_TTL_SECONDS,
    ):
        nonce_store.init_schema(receiver_data_dir)
        self._data_dir = receiver_data_dir
        self._secondary = nonce_store.FakeSecondaryNonceStore(ttl_seconds=secondary_ttl_seconds)
        self._registry = key_registry
        self._business_adapter = business_adapter
        self._max_skew_seconds = max_skew_seconds

    def force_secondary_error(self, times: int = 1) -> None:
        """테스트 전용 — 수신측 Secondary(의 다음 `times`회 호출)를
        강제로 실패시킨다(`nonce_store.FakeSecondaryNonceStore.force_error`
        재사용). ERROR 시나리오 재현용(DENY와 구분 — 아래 참조)."""
        self._secondary.force_error(times=times)

    def mark_secondary_seen_for_test(self, nonce: str, now: float) -> None:
        """테스트 전용 — 수신측 Secondary에만 이 nonce를 "이미 본 것"으로
        미리 등록한다(Primary는 건드리지 않음). Primary가 아직 모르는
        nonce를 Secondary가 먼저 거절(DENY)하는 드문 경우(예: 수신측
        프로세스 재시작으로 SQLite는 리셋됐지만 CacheService는 살아
        있는 상황)를 재현하기 위한 것이다 — `force_secondary_error`
        (ERROR)와는 다른 시나리오다."""
        self._secondary.check_and_mark(nonce, now)

    def raw_nonce_row_exists(self, nonce: str) -> bool:
        """테스트 검증용 — 수신측 Primary SQLite에 해당 nonce 행이
        남아 있는지(보존됐는지) 직접 조회한다."""
        with nonce_store.connect(self._data_dir) as conn:
            row = conn.execute(
                "SELECT nonce FROM nonce_store WHERE nonce = ?", (nonce,)
            ).fetchone()
        return row is not None

    def receive(self, envelope: SignedEnvelope, *, now: float, now_iso: str) -> "orch.GasResponse":
        """Step 5~6. 서명·timestamp·payloadHash 검증 후, 통과하면
        수신측 자체 nonce 저장소로 replay를 차단하고, 그마저 통과하면
        Fake 업무를 실행한다.

        **`GasResponse.retryable` 분류는 이 실험안의 잠정적 선택일 뿐,
        확정 운영 정책으로 기록하지 않는다**(모듈 docstring "Open
        Question" 재확인). 특히 `NONCE_STORE_FAILED` → `retryable=True`는
        "같은 nonce를 재사용해도 된다"는 뜻이 **전혀 아니다** — 동일
        nonce 재사용은 `nonce_eval.classification == "NONCE_REPLAYED"`
        분기(바로 아래, `retryable=False`)가 **Primary 레코드가 남아
        있는 한** 차단한다. 이 모듈·테스트는 Primary 레코드를 삭제·
        만료시키는 로직이 전혀 없어 테스트 실행 동안은 사실상
        무기한 차단되지만, 이것이 "운영에서도 영구히 차단된다"는
        보장은 아니다 — 실제 보존 기간은 운영 배치 정리 정책에
        달려 있다(`nonce_store.py` 모듈 docstring이 이미 "FastAPI DB는
        배치 작업(1시간 주기)으로 만료분 삭제"를 Open Question으로
        남겨 뒀고, 이 실험안도 그 정책을 확정하지 않는다).
        `retryable=True`가 의미하는 것은 오직 "이 idempotency key에
        대해 **새 nonce를 쓰는 새 시도**(= `prepare_dispatch`가 다시
        호출되는 `RETRY_ACCEPTED` 경로)가 나중에 성공할 수도 있다"는
        것뿐이다 — "동일 nonce 재사용"과 "신규 nonce로 같은 작업
        재시도"는 이 모듈에서 완전히 다른 두 가지이며 섞어서 다루지
        않는다(아래 "같은 nonce 재사용 vs 새 nonce 재시도" 테스트
        시나리오 참조). 서명/timestamp 계열 거절은 `retryable=False`로
        분류했다(재시도해도 같은 envelope로는 해결되지 않음).

        **자동 재시도는 이 모듈 어디에도 없다** — `retryable=True`를
        반환해도 이 모듈이나 `gas_orchestration.py`가 스스로 다시
        시도하지 않는다. 실제로 새 nonce로 다시 시도하려면 호출부가
        **새로운 `handle_request()` 호출**(= 새 HTTP 요청)을 수동으로
        만들어야 한다."""
        verify_result = signing_v2.verify_v2(
            registry=self._registry,
            protocol_version=signing_v2.SUPPORTED_PROTOCOL_VERSION,
            method=envelope.method,
            operation=envelope.operation,
            timestamp=envelope.timestamp,
            nonce=envelope.nonce,
            idempotency_key=envelope.idempotency_key,
            key_id=envelope.key_id,
            payload=envelope.payload,
            signature=envelope.signature,
            now=now,
            max_skew_seconds=self._max_skew_seconds,
        )
        if verify_result.classification != "ACCEPTED":
            return orch.GasResponse(
                success=False, retryable=False,
                result=f"SIGNATURE_REJECTED:{verify_result.classification}",
            )

        with nonce_store.connect(self._data_dir) as conn:
            nonce_eval = nonce_store.evaluate_and_register_nonce(
                conn, self._secondary, nonce=envelope.nonce, now=now, now_iso=now_iso,
            )
        if nonce_eval.classification == "NONCE_REPLAYED":
            return orch.GasResponse(
                success=False, retryable=False, result="NONCE_REJECTED:NONCE_REPLAYED"
            )
        if nonce_eval.classification == "NONCE_STORE_FAILED":
            return orch.GasResponse(
                success=False, retryable=True, result="NONCE_REJECTED:NONCE_STORE_FAILED"
            )

        business_result = self._business_adapter(envelope.payload)
        return orch.GasResponse(success=True, retryable=False, result=business_result)


def handle_request(
    idempotency_conn,
    *,
    raw_json_text: str,
    operation: str,
    idempotency_key: str,
    method: str,
    issuer_config: IssuerConfig,
    receiver: FakeReceiver,
    now: datetime,
    envelope_tamperer: Optional[Callable[[SignedEnvelope], SignedEnvelope]] = None,
    network_fault: Optional[BaseException] = None,
    correlation_id: Optional[str] = None,
) -> "orch.OrchestrationResult":
    """전체 7단계를 엮는 진입점(모듈 docstring "처리 순서" 재확인).

    `envelope_tamperer`/`network_fault`는 **테스트 전용 훅**이다 — 실제
    네트워크 계층이 없는 이 격리 흐름에서 "전송 중 변조"·"응답 유실"을
    시뮬레이션하기 위한 것이며, 운영 코드에는 존재하지 않는 개념이다."""
    # 1~2단계: raw JSON·스키마 검증(재작성 없이 signing_v2_guarded 재사용) + fingerprint
    payload = guarded.validate_and_normalize_payload(raw_json_text, operation=operation)
    fingerprint = signing_v2.compute_payload_hash(payload)

    now_epoch = now.timestamp()
    now_iso = now.isoformat(timespec="seconds")
    envelope_holder: dict = {}

    def prepare_dispatch() -> None:
        # 4단계: 실행권을 얻은 요청만 도달하는 지점(gas_orchestration.py가 보장)
        nonce = nonce_store.generate_nonce()

        nonce_store.init_schema(issuer_config.issuer_nonce_data_dir)
        with nonce_store.connect(issuer_config.issuer_nonce_data_dir) as conn:
            issuer_eval = nonce_store.evaluate_and_register_nonce(
                conn, issuer_config.issuer_secondary_store, nonce=nonce, now=now_epoch, now_iso=now_iso,
            )
        if issuer_eval.classification != "ACCEPTED":
            raise PrepareDispatchError(f"발급 측 자체 nonce 기록 실패: {issuer_eval.classification}")

        timestamp_str = str(now_epoch)
        signature = signing_v2.sign_v2(
            secret=issuer_config.secret,
            method=method,
            operation=operation,
            timestamp=timestamp_str,
            nonce=nonce,
            idempotency_key=idempotency_key,
            key_id=issuer_config.key_id,
            payload=payload,
        )
        envelope = SignedEnvelope(
            method=method.upper(), operation=operation, timestamp=timestamp_str, nonce=nonce,
            idempotency_key=idempotency_key, key_id=issuer_config.key_id, payload=payload,
            signature=signature,
        )
        if envelope_tamperer is not None:
            envelope = envelope_tamperer(envelope)
        envelope_holder["envelope"] = envelope

    def gas_adapter(*, key: str, fingerprint: str) -> "orch.GasResponse":
        envelope = envelope_holder["envelope"]
        if network_fault is not None:
            # 수신측은 실제로 처리(업무 실행 포함)하지만, 그 응답이
            # 발급측에 "유실"된 것으로 시뮬레이션 -> SENT_UNCERTAIN 유도.
            receiver.receive(envelope, now=now_epoch, now_iso=now_iso)
            raise network_fault
        return receiver.receive(envelope, now=now_epoch, now_iso=now_iso)

    # 3단계 + 7단계: idempotency_store.try_create()/record_outcome()/
    # mark_unknown() 전부 gas_orchestration.py가 이미 구현(재작성 없음).
    return orch.execute_with_idempotency(
        idempotency_conn,
        key=idempotency_key,
        fingerprint=fingerprint,
        gas_adapter=gas_adapter,
        prepare_dispatch=prepare_dispatch,
        now=now,
        correlation_id=correlation_id,
    )
