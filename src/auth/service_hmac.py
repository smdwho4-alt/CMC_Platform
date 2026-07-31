# -*- coding: utf-8 -*-
"""
CSHSP FastAPI-GAS 서비스 인증 — HMAC 서명 유틸리티 (Sprint8 Commit8-2, 설계·인터페이스만)

Sprint8 Commit8-1 §35에서 권장한 대안(HMAC, GAS Script Properties에 Secret
분리 저장)의 FastAPI 측 서명 생성·검증 로직만 순수 함수로 구현한다.

**중요**: 이 모듈은 아직 `sheets_readonly_service.py`/`sheets_write_service.py`의
실제 GAS 호출부에 연결(wiring)되지 않았다 — GAS(`sheets_api_v3_final.gs`)가
이 서명을 검증하는 코드가 없는 이상, FastAPI가 서명 헤더를 보내도 GAS는 이를
무시할 뿐이며 보호 효과가 없다. GAS 측 서명 검증 로직 추가와 배포는 Commit8-2
승인 범위(운영 GAS 코드 변경·배포 금지)를 벗어나므로 여기서는 구현하지 않았고,
Commit8-3에서 GAS 코드 변경안과 함께 별도로 다룬다(Sprint8 Security Plan §21,
Threat Model §35 참조).

이 모듈의 함수는 로컬 단위테스트만으로 검증 가능하며(실제 네트워크 호출 없음),
실제 서명 Secret 값을 생성·출력·저장하지 않는다 — 테스트에서도 합성 테스트용
Secret 문자열만 사용한다.
"""
from __future__ import annotations

import hashlib
import hmac
import time


class SignatureError(Exception):
    """서명 검증 실패 — 사유(reason)만 보존, 원문 Secret/서명 값은 포함하지 않는다."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def canonical_string(*, method: str, action: str, timestamp: str, nonce: str, body_hash: str) -> str:
    """서명 대상 정규 문자열. 필드 순서를 고정해 서명자·검증자가 동일한 문자열을
    계산하도록 한다."""
    return "\n".join([method.upper(), action, timestamp, nonce, body_hash])


def hash_body(body_bytes: bytes) -> str:
    return hashlib.sha256(body_bytes).hexdigest()


def sign_request(
    *, secret: str, method: str, action: str, timestamp: str, nonce: str, body_bytes: bytes
) -> str:
    """HMAC-SHA256 서명을 16진 문자열로 반환한다. secret은 호출부가 서버
    환경변수(FastAPI)에서만 읽어와야 하며, 이 함수는 secret을 저장하지 않는다."""
    msg = canonical_string(
        method=method, action=action, timestamp=timestamp, nonce=nonce,
        body_hash=hash_body(body_bytes),
    )
    return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(
    *, secret: str, method: str, action: str, timestamp: str, nonce: str,
    body_bytes: bytes, signature: str, max_skew_seconds: int = 300,
) -> None:
    """서명·Timestamp 허용오차를 검증한다. 실패 시 SignatureError를 발생시킨다.
    Nonce 재사용(Replay) 방지는 이 함수 범위 밖이다 — 호출부가 별도의 Nonce
    저장소(예: 짧은 TTL 캐시)로 이미 사용된 Nonce인지 확인해야 한다(Commit8-3
    설계 대상, 이번 Commit에서는 저장소를 구현하지 않는다)."""
    try:
        ts = float(timestamp)
    except ValueError:
        raise SignatureError("INVALID_TIMESTAMP")
    if abs(time.time() - ts) > max_skew_seconds:
        raise SignatureError("TIMESTAMP_OUT_OF_RANGE")

    expected = sign_request(
        secret=secret, method=method, action=action, timestamp=timestamp,
        nonce=nonce, body_bytes=body_bytes,
    )
    if not hmac.compare_digest(expected, signature):
        raise SignatureError("SIGNATURE_MISMATCH")
