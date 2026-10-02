# -*- coding: utf-8 -*-
"""
CSHSP Sprint8 Commit8-3b — src/idempotency/signing_v2.py 단위 테스트

모든 키·Secret·nonce·timestamp·payload는 합성(synthetic) 값이다. 실제
운영 Secret을 생성·조회하지 않는다. 실제 네트워크·GAS 접근 없음.
"""
from __future__ import annotations

import hashlib
import hmac as hmac_lib
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src" / "idempotency"))

import signing_v2 as sv2  # noqa: E402

SYNTHETIC_SECRET_ACTIVE = "synthetic-test-secret-active-0001"
SYNTHETIC_SECRET_GRACE = "synthetic-test-secret-grace-0002"
SYNTHETIC_SECRET_REVOKED = "synthetic-test-secret-revoked-0003"

FIXED_METHOD = "POST"
FIXED_OPERATION = "approve"
FIXED_TIMESTAMP = "1700000000.0"
FIXED_NONCE = "synthetic-nonce-fixed-0001"
FIXED_IDEMPOTENCY_KEY = "synthetic-idem-fixed-0001"
FIXED_PAYLOAD = {"reservationNo": "SYN-0001", "action": "approve"}


def _fresh_registry() -> sv2.KeyRegistry:
    reg = sv2.KeyRegistry()
    reg.register(sv2.KeyRecord(key_id="key-active", secret=SYNTHETIC_SECRET_ACTIVE, state="ACTIVE"))
    reg.register(
        sv2.KeyRecord(
            key_id="key-grace", secret=SYNTHETIC_SECRET_GRACE, state="GRACE",
            grace_expires_at=1700000000.0 + 48 * 3600,
        )
    )
    reg.register(sv2.KeyRecord(key_id="key-revoked", secret=SYNTHETIC_SECRET_REVOKED, state="REVOKED"))
    return reg


class SigningV2TestCase(unittest.TestCase):
    # 1. 정상 서명과 합성 고정 테스트 벡터 -------------------------------------------
    def test_fixed_vector_canonical_string_and_signature(self):
        """입력을 전부 고정한 뒤, canonical string 전체 텍스트와 서명값을
        이 테스트와 독립적으로(hmac_lib 직접 호출) 재계산해 교차 검증한다."""
        payload_hash = sv2.compute_payload_hash(FIXED_PAYLOAD)
        canonical = sv2.build_canonical_string_v2(
            method=FIXED_METHOD, operation=FIXED_OPERATION, timestamp=FIXED_TIMESTAMP,
            nonce=FIXED_NONCE, idempotency_key=FIXED_IDEMPOTENCY_KEY, key_id="key-active",
            payload_hash=payload_hash,
        )
        expected_canonical = "\n".join([
            "CMC-HMAC-SHA256", "2", FIXED_METHOD, FIXED_OPERATION, FIXED_TIMESTAMP,
            FIXED_NONCE, FIXED_IDEMPOTENCY_KEY, "key-active", payload_hash,
        ])
        self.assertEqual(canonical, expected_canonical)

        signature = sv2.sign_v2(
            secret=SYNTHETIC_SECRET_ACTIVE, method=FIXED_METHOD, operation=FIXED_OPERATION,
            timestamp=FIXED_TIMESTAMP, nonce=FIXED_NONCE, idempotency_key=FIXED_IDEMPOTENCY_KEY,
            key_id="key-active", payload=FIXED_PAYLOAD,
        )
        # 이 모듈과 독립적으로 hmac_lib를 직접 호출해 재계산(교차검증)
        independent_expected = hmac_lib.new(
            SYNTHETIC_SECRET_ACTIVE.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        self.assertEqual(signature, independent_expected)

        registry = _fresh_registry()
        result = sv2.verify_v2(
            registry=registry, protocol_version="2", method=FIXED_METHOD, operation=FIXED_OPERATION,
            timestamp=FIXED_TIMESTAMP, nonce=FIXED_NONCE, idempotency_key=FIXED_IDEMPOTENCY_KEY,
            key_id="key-active", payload=FIXED_PAYLOAD, signature=signature,
            now=1700000000.0, max_skew_seconds=sv2.TEST_DEFAULT_MAX_SKEW_SECONDS,
        )
        self.assertEqual(result.classification, "ACCEPTED")

    def test_payload_key_order_independent(self):
        h1 = sv2.compute_payload_hash({"a": 1, "b": 2})
        h2 = sv2.compute_payload_hash({"b": 2, "a": 1})
        self.assertEqual(h1, h2)

    # 2. 필드·payload·keyId 변조 -----------------------------------------------------
    def _sign_fixed(self, **overrides):
        kwargs = dict(
            secret=SYNTHETIC_SECRET_ACTIVE, method=FIXED_METHOD, operation=FIXED_OPERATION,
            timestamp=FIXED_TIMESTAMP, nonce=FIXED_NONCE, idempotency_key=FIXED_IDEMPOTENCY_KEY,
            key_id="key-active", payload=FIXED_PAYLOAD,
        )
        kwargs.update(overrides)
        return sv2.sign_v2(**kwargs)

    def _verify_fixed(self, registry, signature, **overrides):
        kwargs = dict(
            registry=registry, protocol_version="2", method=FIXED_METHOD, operation=FIXED_OPERATION,
            timestamp=FIXED_TIMESTAMP, nonce=FIXED_NONCE, idempotency_key=FIXED_IDEMPOTENCY_KEY,
            key_id="key-active", payload=FIXED_PAYLOAD, signature=signature,
            now=1700000000.0, max_skew_seconds=sv2.TEST_DEFAULT_MAX_SKEW_SECONDS,
        )
        kwargs.update(overrides)
        return sv2.verify_v2(**kwargs)

    def test_field_tampering_detected(self):
        registry = _fresh_registry()
        signature = self._sign_fixed()
        tampered = self._verify_fixed(registry, signature, timestamp="1700000001.0")
        self.assertEqual(tampered.classification, "SIGNATURE_MISMATCH")

    def test_payload_tampering_detected(self):
        registry = _fresh_registry()
        signature = self._sign_fixed()
        tampered = self._verify_fixed(registry, signature, payload={"reservationNo": "SYN-9999", "action": "approve"})
        self.assertEqual(tampered.classification, "SIGNATURE_MISMATCH")

    def test_keyid_tampering_detected_known_other_key(self):
        """서명은 key-active로 만들었으나 key_id를 key-grace라고 주장 —
        key-grace의 Secret으로 재계산한 서명과 불일치해야 한다."""
        registry = _fresh_registry()
        signature = self._sign_fixed()  # key-active Secret으로 서명
        tampered = self._verify_fixed(registry, signature, key_id="key-grace")
        self.assertEqual(tampered.classification, "SIGNATURE_MISMATCH")

    def test_unregistered_field_values_rejected_before_signature_check(self):
        registry = _fresh_registry()
        signature = self._sign_fixed()
        result = self._verify_fixed(registry, signature, method="TRACE")  # 허용 목록 밖 메서드
        self.assertEqual(result.classification, "FIELD_FORMAT_INVALID")

    # 3. timestamp 양쪽 경계 및 범위 초과 ---------------------------------------------
    def test_timestamp_boundary_both_sides_inclusive(self):
        registry = _fresh_registry()
        base_ts = 1700000000.0
        signature = self._sign_fixed(timestamp=str(base_ts))
        skew = sv2.TEST_DEFAULT_MAX_SKEW_SECONDS

        past_boundary = self._verify_fixed(
            registry, signature, timestamp=str(base_ts), now=base_ts + skew
        )
        self.assertEqual(past_boundary.classification, "ACCEPTED", "경계값(=허용범위)은 유효해야 함")

        future_boundary = self._verify_fixed(
            registry, signature, timestamp=str(base_ts), now=base_ts - skew
        )
        self.assertEqual(future_boundary.classification, "ACCEPTED", "경계값(=허용범위)은 유효해야 함")

    def test_timestamp_out_of_range_past_and_future(self):
        registry = _fresh_registry()
        base_ts = 1700000000.0
        signature = self._sign_fixed(timestamp=str(base_ts))
        skew = sv2.TEST_DEFAULT_MAX_SKEW_SECONDS

        too_old = self._verify_fixed(registry, signature, timestamp=str(base_ts), now=base_ts + skew + 1)
        self.assertEqual(too_old.classification, "TIMESTAMP_EXPIRED")

        too_future = self._verify_fixed(registry, signature, timestamp=str(base_ts), now=base_ts - skew - 1)
        self.assertEqual(too_future.classification, "TIMESTAMP_FUTURE")

    # 4. 미등록·폐기·Grace 종료 키 ------------------------------------------------------
    def test_unregistered_key_rejected(self):
        registry = _fresh_registry()
        signature = self._sign_fixed(secret="irrelevant-since-key-unknown", key_id="key-ghost")
        result = self._verify_fixed(registry, signature, key_id="key-ghost")
        self.assertEqual(result.classification, "UNKNOWN_KEY_ID")

    def test_revoked_key_rejected(self):
        registry = _fresh_registry()
        signature = self._sign_fixed(secret=SYNTHETIC_SECRET_REVOKED, key_id="key-revoked")
        result = self._verify_fixed(registry, signature, key_id="key-revoked")
        self.assertEqual(result.classification, "KEY_REVOKED")

    def test_grace_expired_key_rejected(self):
        registry = _fresh_registry()
        signature = self._sign_fixed(secret=SYNTHETIC_SECRET_GRACE, key_id="key-grace")
        grace_expiry = 1700000000.0 + 48 * 3600
        result = self._verify_fixed(
            registry, signature, key_id="key-grace", timestamp=str(grace_expiry + 1), now=grace_expiry + 1
        )
        self.assertEqual(result.classification, "KEY_GRACE_EXPIRED")

    def test_grace_key_still_valid_within_window(self):
        registry = _fresh_registry()
        signature = self._sign_fixed(secret=SYNTHETIC_SECRET_GRACE, key_id="key-grace")
        result = self._verify_fixed(registry, signature, key_id="key-grace")
        self.assertEqual(result.classification, "ACCEPTED")

    def test_key_resolution_does_not_fallback_to_other_key(self):
        """key-ghost(미등록)로 검증 요청 시, registry가 ACTIVE 키 등으로
        '대신' 시도하지 않고 정확히 UNKNOWN_KEY_ID만 반환해야 한다."""
        registry = _fresh_registry()
        with self.assertRaises(sv2.KeyResolutionError) as ctx:
            registry.resolve("key-ghost", now=1700000000.0)
        self.assertEqual(ctx.exception.reason, "UNKNOWN_KEY_ID")

    # 5. 버전 불일치 및 fallback 없음 --------------------------------------------------
    def test_protocol_version_mismatch_no_fallback(self):
        registry = _fresh_registry()
        signature = self._sign_fixed()
        result = self._verify_fixed(registry, signature, protocol_version="1")
        self.assertEqual(result.classification, "PROTOCOL_VERSION_MISMATCH")
        # v1(8필드) 형식으로 재해석을 시도하는 코드 경로 자체가 없음을
        # 구조적으로 보장한다 — verify_v2()는 protocol_version 검사에서
        # 즉시 반환하며 그 뒤의 서명 계산 로직에 도달하지 않는다(코드 순서로
        # 보장, 별도 try/except로 구버전을 시도하지 않음).

    def test_missing_required_field_rejected(self):
        with self.assertRaises(sv2.FieldFormatError):
            sv2.build_canonical_string_v2(
                method="POST", operation="approve", timestamp=FIXED_TIMESTAMP, nonce=FIXED_NONCE,
                idempotency_key=None, key_id="key-active", payload_hash="a" * 64,
            )

    def test_delimiter_injection_in_field_rejected(self):
        """필드 값에 개행을 삽입해 Canonical String 경계를 조작하려는
        시도를 형식 검증이 차단하는지 확인한다(계약 초안 §2)."""
        with self.assertRaises(sv2.FieldFormatError):
            sv2.build_canonical_string_v2(
                method="POST", operation="approve\nINJECTED", timestamp=FIXED_TIMESTAMP,
                nonce=FIXED_NONCE, idempotency_key=FIXED_IDEMPOTENCY_KEY, key_id="key-active",
                payload_hash="a" * 64,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
