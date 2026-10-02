# -*- coding: utf-8 -*-
"""
CSHSP HMAC Canonical String v2(keyId 포함) — Sprint8 Commit8-3b (격리 개발, 로컬 전용)

**이 모듈은 ADR-017을 개정하지 않는다.** ADR-017 §12는 `protocolVersion="1"`
(8필드, keyId 없음)만 확정했다. 이 모듈의 `protocolVersion="2"`는
`docs/Commit8_3b_HMAC_Nonce_V2_Contract_Draft.md`에 정리한 **격리 개발용
제안 계약**이며, PM/아키텍처가 ADR-017을 실제로 개정하기 전까지는 운영
계약이 아니다. 운영 라우트는 이 모듈을 아직 import하지 않는다.

**기존 `src/auth/service_hmac.py`(5필드, Commit8-2 산출물)는 이 모듈에서
import하지 않으며 수정하지도 않는다** — 두 모듈은 완전히 독립적이다.

## Canonical String v2(9필드)
```
CMC-HMAC-SHA256
2
<HTTP Method>
<operation>
<timestamp>
<nonce>
<idempotencyKey>
<keyId>
<payloadHash>
```
LF 구분, 트레일링 개행 없음, UTF-8 인코딩. `keyId`는 **서명 대상에 포함**된다
(계약 초안 §1). 각 필드는 join 전에 엄격한 형식 검증을 거친다(§FIELD_PATTERNS)
— 구분자(`\n`)를 비롯한 제어문자를 원천적으로 허용하지 않아, 필드 값으로
Canonical String의 줄 경계를 조작할 수 없다(계약 초안 §2).

## 오류 분류는 내부용이다
이 모듈의 `VerificationResult.classification` 값은 **내부 구현 참고용**이며
HTTP 오류 응답 스키마로 확정된 것이 아니다. `UNKNOWN_KEY_ID`/
`SIGNATURE_MISMATCH`/`TIMESTAMP_EXPIRED`/`TIMESTAMP_FUTURE`/
`PROTOCOL_VERSION_MISMATCH`는 API Contract §12가 이미 제안한 19종 오류코드
이름을 재사용했다. `KEY_REVOKED`/`KEY_GRACE_EXPIRED`/`FIELD_FORMAT_INVALID`는
그 19종에 없는 **이번 격리 구현의 임시 내부 분류**다(Open Question).

## 로깅 원칙
이 모듈 자체는 로깅을 수행하지 않는다(순수 함수 위주) — 호출부가 계측을
추가할 경우 **secret·서명 원문(signature hex)·원문 payload를 로그에
남기지 않을 책임**은 호출부에 있다. `keyId`는 비밀이 아니므로(식별자일
뿐) 로깅해도 무방하다.

## 이전 형식 자동 fallback 금지
`verify_v2()`는 `protocol_version != "2"`이면 **즉시 거부**하며, v1(8필드)
이나 기존 5필드 레거시 형식으로 재시도하지 않는다.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

ALGORITHM_LITERAL = "CMC-HMAC-SHA256"
SUPPORTED_PROTOCOL_VERSION = "2"

_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.\-:]{1,200}$")
_TIMESTAMP_RE = re.compile(r"^\d+(\.\d+)?$")
_PAYLOAD_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_VALID_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})

FIELD_PATTERNS = {
    "method": _VALID_METHODS,  # 집합 멤버십 검사(정규식이 아님)
    "operation": _SAFE_TOKEN_RE,
    "timestamp": _TIMESTAMP_RE,
    "nonce": _SAFE_TOKEN_RE,
    "idempotency_key": _SAFE_TOKEN_RE,
    "key_id": _SAFE_TOKEN_RE,
    "payload_hash": _PAYLOAD_HASH_RE,
}


class FieldFormatError(ValueError):
    """Canonical String 필드 형식 검증 실패(계약 초안 §2) — 구분자 삽입 등
    모호성을 유발할 수 있는 값을 원천 차단한다."""


def _validate_field(name: str, value: Optional[str]) -> str:
    if value is None:
        raise FieldFormatError(f"필수 필드 누락: {name}")
    if not isinstance(value, str):
        raise FieldFormatError(f"{name}은 문자열이어야 함")
    pattern = FIELD_PATTERNS[name]
    if name == "method":
        if value not in pattern:
            raise FieldFormatError(f"허용되지 않는 method: {value!r}")
    else:
        if not pattern.match(value):
            raise FieldFormatError(f"허용되지 않는 {name} 형식")
    return value


def compute_payload_hash(payload: dict) -> str:
    """payload(JSON 객체)를 키 유니코드 코드포인트순 정렬 + compact 직렬화 +
    Unicode NFC 정규화 + UTF-8 인코딩 후 SHA-256 소문자 hex로 반환한다
    (계약 초안 §3). `payload` 원문 자체는 이 함수가 로깅하지 않는다."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    normalized = unicodedata.normalize("NFC", serialized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_canonical_string_v2(
    *,
    method: str,
    operation: str,
    timestamp: str,
    nonce: str,
    idempotency_key: str,
    key_id: str,
    payload_hash: str,
) -> str:
    """9필드 Canonical String v2를 생성한다. 각 필드는 join 전에 형식
    검증을 거치며, 실패 시 `FieldFormatError`를 낸다(모호성 방지, 계약
    초안 §2)."""
    method = _validate_field("method", method.upper() if isinstance(method, str) else method)
    operation = _validate_field("operation", operation)
    timestamp = _validate_field("timestamp", timestamp)
    nonce = _validate_field("nonce", nonce)
    idempotency_key = _validate_field("idempotency_key", idempotency_key)
    key_id = _validate_field("key_id", key_id)
    payload_hash = _validate_field("payload_hash", payload_hash)
    return "\n".join(
        [
            ALGORITHM_LITERAL,
            SUPPORTED_PROTOCOL_VERSION,
            method,
            operation,
            timestamp,
            nonce,
            idempotency_key,
            key_id,
            payload_hash,
        ]
    )


def sign_v2(
    *,
    secret: str,
    method: str,
    operation: str,
    timestamp: str,
    nonce: str,
    idempotency_key: str,
    key_id: str,
    payload: dict,
) -> str:
    """HMAC-SHA256 서명을 16진 소문자 문자열로 반환한다. `secret`은 호출부가
    관리하며 이 함수는 저장·로깅하지 않는다. 합성 테스트 Secret만 사용할 것
    (이 모듈은 운영 Secret을 생성·조회하지 않는다)."""
    payload_hash = compute_payload_hash(payload)
    canonical = build_canonical_string_v2(
        method=method, operation=operation, timestamp=timestamp, nonce=nonce,
        idempotency_key=idempotency_key, key_id=key_id, payload_hash=payload_hash,
    )
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------
# 키 레지스트리 — ACTIVE/GRACE/REVOKED, 미등록·폐기·Grace 종료 키 차단
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class KeyRecord:
    """등록된 키 1건. `state`는 ADR-017 §15가 확정한 `ACTIVE`/`GRACE` 외에
    이번 격리 구현이 추가로 도입한 `REVOKED`(긴급 폐기, ADR-017 범위 밖 —
    계약 정합성 보완안 §3-3 재확인)를 포함한다. `grace_expires_at`은
    `state=="GRACE"`일 때만 의미가 있다(Unix epoch 초)."""

    key_id: str
    secret: str
    state: str  # "ACTIVE" | "GRACE" | "REVOKED"
    grace_expires_at: Optional[float] = None


class KeyResolutionError(Exception):
    """키 조회 실패. `reason`은 내부 분류값(모듈 docstring 참조)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class KeyRegistry:
    """합성 테스트 키만 담는 간단한 레지스트리(dict 기반). 운영 Secret
    저장소(GAS `PropertiesService` 등)를 대체하지 않는다 — 이 클래스는
    격리 테스트 전용이다. **키 선택 실패 시 다른 키로 폴백하지 않는다**:
    `resolve()`는 정확히 요청된 `key_id` 하나만 조회하며, 실패하면 예외를
    낼 뿐 다른 키를 대신 시도하지 않는다."""

    def __init__(self):
        self._keys: dict[str, KeyRecord] = {}

    def register(self, record: KeyRecord) -> None:
        if record.state not in ("ACTIVE", "GRACE", "REVOKED"):
            raise ValueError(f"알 수 없는 key state: {record.state!r}")
        if record.state == "GRACE" and record.grace_expires_at is None:
            raise ValueError("GRACE 상태 키는 grace_expires_at이 필요함")
        self._keys[record.key_id] = record

    def resolve(self, key_id: str, now: float) -> KeyRecord:
        """정확히 `key_id` 하나만 조회한다(폴백 없음). 미등록/폐기/Grace
        종료는 각각 구분된 `KeyResolutionError`를 낸다."""
        record = self._keys.get(key_id)
        if record is None:
            raise KeyResolutionError("UNKNOWN_KEY_ID")
        if record.state == "REVOKED":
            raise KeyResolutionError("KEY_REVOKED")
        if record.state == "GRACE" and now > record.grace_expires_at:
            raise KeyResolutionError("KEY_GRACE_EXPIRED")
        return record


# --------------------------------------------------------------------------
# 검증
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationResult:
    """`verify_v2()`의 반환 타입. `classification`은 내부 분류값(모듈
    docstring "오류 분류는 내부용이다" 참조)."""

    classification: str
    key_id: Optional[str] = None


def verify_v2(
    *,
    registry: KeyRegistry,
    protocol_version: str,
    method: str,
    operation: str,
    timestamp: str,
    nonce: str,
    idempotency_key: str,
    key_id: str,
    payload: dict,
    signature: str,
    now: float,
    max_skew_seconds: int,
) -> VerificationResult:
    """v2 서명을 검증한다. `max_skew_seconds`는 **호출부가 설정값으로
    명시적으로 전달해야 한다**(내부 기본값을 두지 않음 — 운영 확정값이
    아직 없으므로 암묵적 기본값으로 조용히 채택하지 않기 위함, 계약
    정합성 보완안 §2-3 재확인). 테스트에서는 `TEST_DEFAULT_MAX_SKEW_SECONDS`
    (120초)를 명시적으로 넘겨 사용한다.

    검사 순서(문서화된 설계 선택 — 보안상 필수 순서는 아니나 일관성 위해
    고정): ① protocolVersion ② 필드 형식 ③ 키 조회(미등록/폐기/Grace종료)
    ④ 서명 일치(상수시간 비교) ⑤ timestamp 허용범위(경계 포함, 과거/미래
    구분). 서명이 틀린 요청에 대해 timestamp 세부사항까지 노출하지 않기
    위해 서명 검증을 timestamp 검사보다 먼저 수행한다."""
    if protocol_version != SUPPORTED_PROTOCOL_VERSION:
        return VerificationResult(classification="PROTOCOL_VERSION_MISMATCH")

    try:
        method_u = method.upper() if isinstance(method, str) else method
        _validate_field("method", method_u)
        _validate_field("operation", operation)
        _validate_field("timestamp", timestamp)
        _validate_field("nonce", nonce)
        _validate_field("idempotency_key", idempotency_key)
        _validate_field("key_id", key_id)
    except FieldFormatError:
        return VerificationResult(classification="FIELD_FORMAT_INVALID")

    try:
        key_record = registry.resolve(key_id, now)
    except KeyResolutionError as e:
        return VerificationResult(classification=e.reason, key_id=key_id)

    payload_hash = compute_payload_hash(payload)
    try:
        canonical = build_canonical_string_v2(
            method=method_u, operation=operation, timestamp=timestamp, nonce=nonce,
            idempotency_key=idempotency_key, key_id=key_id, payload_hash=payload_hash,
        )
    except FieldFormatError:
        return VerificationResult(classification="FIELD_FORMAT_INVALID", key_id=key_id)

    expected_signature = hmac.new(
        key_record.secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        return VerificationResult(classification="SIGNATURE_MISMATCH", key_id=key_id)

    ts = float(timestamp)
    delta = now - ts
    if delta > max_skew_seconds:
        return VerificationResult(classification="TIMESTAMP_EXPIRED", key_id=key_id)
    if delta < -max_skew_seconds:
        return VerificationResult(classification="TIMESTAMP_FUTURE", key_id=key_id)

    return VerificationResult(classification="ACCEPTED", key_id=key_id)


# 테스트 전용 기본값 — 운영 확정값이 아니다(계약 정합성 보완안 §2-3 재확인).
# production 코드는 이 상수를 import해 암묵적으로 쓰지 않는다(호출부가
# max_skew_seconds를 매번 명시적으로 지정해야 함).
TEST_DEFAULT_MAX_SKEW_SECONDS = 120
