# -*- coding: utf-8 -*-
"""
Commit8-3b payload 정규화 계약 — 서명 전 개발용 검증 wrapper(격리, 비배선)

이 모듈은 `signing_v2.py`의 공개 API(`compute_payload_hash`/`sign_v2`/
`verify_v2`)를 **전혀 수정하지 않는다**. 대신 다음 순서로 검증을
체이닝하는 **별도 wrapper 함수**를 제공한다:

    원시 JSON 텍스트
      → (1) raw JSON 경로: 중복 키 + 숫자 토큰 형식 검증
          (`payload_schema_guard.parse_json_strict`)
      → (2) 공통 타입 가드: ASCII-only object key, 안전정수범위 등
          (`payload_schema_guard.validate_payload_schema_interim`)
      → (3) 요청별 스키마 가드: operation에 등록된 필드만 허용
          (`request_payload_schemas.validate_request_schema`)
      → (4) 전부 통과한 payload만 `signing_v2.compute_payload_hash()`/
          `sign_v2()`(기존 함수, 미수정)로 전달

운영 라우트에 배선되지 않았다 — 호출부가 명시적으로 원해야 쓸 수
있는 **선택적** 경로다. 운영 수신 계층(FastAPI 요청 바디 파싱 등)을
바꾸지 않는다.

## `signing_v2.py`를 직접 호출하는 기존 경로의 한계(이 wrapper가
## 메우려는 공백 — 수정이 아니라 "메움")
`signing_v2.compute_payload_hash()`/`sign_v2()`는 **이미 파싱된 Python
dict**를 받는다. 그 dict가 어떻게 만들어졌는지(원시 JSON 텍스트에
중복 키가 있었는지, `1.0`처럼 소수점 붙은 리터럴이었는지, 등록되지
않은 필드가 섞여 있었는지)는 **전혀 검사하지 않는다**. 즉
`signing_v2.sign_v2(payload={"count": 1.0}, ...)`처럼 직접 호출하면
아무 경고 없이 그대로 서명한다 — 이것이 과거 V04 교차검증 불일치의
근본 원인이었다. **이 wrapper를 거치지 않고 `signing_v2.py`를 직접
호출하는 기존/향후 모든 호출부는 이 한계를 그대로 안고 있다** — 이
한계는 코드로 "고쳐서" 없앨 수 있는 것이 아니라, 호출 경로를
`signing_v2_guarded`로 바꿔야만 메워진다(선택 사항, 강제 배선 아님).
"""
from __future__ import annotations

from typing import Optional

import payload_schema_guard as guard
import request_payload_schemas as req_schemas
import signing_v2 as sv2


class GuardedSigningError(ValueError):
    """wrapper의 3단계 검증(raw JSON/공통 타입/요청별 스키마) 중 어디서
    실패했는지를 `stage`로, 그 사유를 `reason`으로 구분해 알려준다.
    세 단계 모두 내부 참고용 분류이며 운영 오류코드로 확정된 것은
    아니다(signing_v2.py와 동일 원칙)."""

    def __init__(self, stage: str, reason: str, detail: str = ""):
        super().__init__(f"[{stage}] {reason}" + (f" — {detail}" if detail else ""))
        self.stage = stage
        self.reason = reason


def validate_and_normalize_payload(raw_json_text: str, *, operation: str) -> dict:
    """원시 JSON 텍스트를 받아 3단계 검증을 순서대로 수행한다. 전부
    통과하면 검증된 payload(dict)를 반환한다. 어느 단계든 실패하면
    `GuardedSigningError`를 낸다(원본 예외는 `__cause__`로 보존)."""
    # 1) raw JSON 경로 — 중복 키 + 숫자 토큰 형식(소수점·지수 금지, -0 정규화)
    try:
        payload = guard.parse_json_strict(raw_json_text)
    except guard.DuplicateKeyError as e:
        raise GuardedSigningError("RAW_JSON", "DUPLICATE_KEY", str(e)) from e
    except guard.RawNumberFormatError as e:
        raise GuardedSigningError("RAW_JSON", e.reason, str(e)) from e

    # 2) 공통 타입 가드 — ASCII-only object key, 안전정수범위 등
    try:
        guard.validate_payload_schema_interim(payload)
    except guard.PayloadSchemaUnresolvedError as e:
        raise GuardedSigningError("COMMON_TYPE_GUARD", e.reason, str(e)) from e

    # 3) 요청별 스키마 가드 — operation에 등록된 필드만 허용
    try:
        req_schemas.validate_request_schema(operation, payload)
    except req_schemas.RequestSchemaError as e:
        raise GuardedSigningError("REQUEST_SCHEMA", e.reason, str(e)) from e

    return payload


def compute_payload_hash_guarded(raw_json_text: str, *, operation: str) -> str:
    """검증·정규화를 통과한 payload만 `signing_v2.compute_payload_hash()`
    (기존 함수, 미수정)로 전달한다."""
    payload = validate_and_normalize_payload(raw_json_text, operation=operation)
    return sv2.compute_payload_hash(payload)


def sign_v2_guarded(
    *,
    raw_json_text: str,
    operation: str,
    secret: str,
    method: str,
    timestamp: str,
    nonce: str,
    idempotency_key: str,
    key_id: str,
) -> str:
    """검증·정규화를 통과한 payload만 `signing_v2.sign_v2()`(기존 함수,
    미수정)로 전달한다. `signing_v2.py`의 공개 API 시그니처는 그대로
    유지되며, 이 함수는 그 위에 얇게 쌓인 wrapper일 뿐이다."""
    payload = validate_and_normalize_payload(raw_json_text, operation=operation)
    return sv2.sign_v2(
        secret=secret, method=method, operation=operation, timestamp=timestamp,
        nonce=nonce, idempotency_key=idempotency_key, key_id=key_id, payload=payload,
    )
