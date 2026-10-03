# -*- coding: utf-8 -*-
"""
CSHSP Sprint8 Commit8-3b — src/idempotency/signing_v2_guarded.py 단위 테스트

서명 전 개발용 검증 wrapper(raw JSON 경로 → 공통 타입 가드 → 요청별
스키마 가드 → signing_v2.py 기존 함수 호출)를 검증한다. signing_v2.py
자체는 수정하지 않았음을 전제로, "미검증 객체를 직접 서명하는 기존
함수의 한계"도 이 파일에서 실측으로 확인한다.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src" / "idempotency"))

import signing_v2 as sv2  # noqa: E402
import signing_v2_guarded as guarded  # noqa: E402

SYNTHETIC_SECRET = "synthetic-test-secret-guarded-0001"


class HappyPathTestCase(unittest.TestCase):
    def test_valid_raw_json_hash_matches_direct_call(self):
        raw = '{"patientId":"P-0001","programId":"PRG-01","requestedDate":"2026-10-10","requestedTime":"09:00","slotId":"SLOT-01"}'
        hash_via_wrapper = guarded.compute_payload_hash_guarded(raw, operation="reservation_create")
        # 동일한(파싱된) payload를 signing_v2.py 기존 함수에 직접 넘긴 결과와 일치해야 한다.
        parsed = {
            "patientId": "P-0001", "programId": "PRG-01", "requestedDate": "2026-10-10",
            "requestedTime": "09:00", "slotId": "SLOT-01",
        }
        self.assertEqual(hash_via_wrapper, sv2.compute_payload_hash(parsed))

    def test_valid_raw_json_sign_v2_guarded_matches_direct_sign(self):
        raw = '{"status":"IN_PROGRESS"}'
        sig_via_wrapper = guarded.sign_v2_guarded(
            raw_json_text=raw, operation="consultation_status_update", secret=SYNTHETIC_SECRET,
            method="POST", timestamp="1700000000.0", nonce="nonce-guarded-0001",
            idempotency_key="idem-guarded-0001", key_id="key-active",
        )
        expected = sv2.sign_v2(
            secret=SYNTHETIC_SECRET, method="POST", operation="consultation_status_update",
            timestamp="1700000000.0", nonce="nonce-guarded-0001", idempotency_key="idem-guarded-0001",
            key_id="key-active", payload={"status": "IN_PROGRESS"},
        )
        self.assertEqual(sig_via_wrapper, expected)


class StageFailureTestCase(unittest.TestCase):
    def test_raw_json_duplicate_key_blocked(self):
        with self.assertRaises(guarded.GuardedSigningError) as ctx:
            guarded.compute_payload_hash_guarded('{"status":"A","status":"B"}', operation="consultation_status_update")
        self.assertEqual(ctx.exception.stage, "RAW_JSON")
        self.assertEqual(ctx.exception.reason, "DUPLICATE_KEY")

    def test_raw_json_float_blocked(self):
        with self.assertRaises(guarded.GuardedSigningError) as ctx:
            guarded.compute_payload_hash_guarded('{"startDate":"2026-10-01","endDate":"2026-10-31","capacity":6.0}', operation="slot_generate")
        self.assertEqual(ctx.exception.stage, "RAW_JSON")
        self.assertEqual(ctx.exception.reason, "FLOAT_OR_EXPONENT_NOT_ALLOWED")

    def test_common_type_guard_unicode_key_blocked(self):
        with self.assertRaises(guarded.GuardedSigningError) as ctx:
            guarded.compute_payload_hash_guarded('{"환자명":"홍길동"}', operation="reservation_create")
        self.assertEqual(ctx.exception.stage, "COMMON_TYPE_GUARD")
        self.assertEqual(ctx.exception.reason, "UNICODE_OR_INVALID_OBJECT_KEY")

    def test_common_type_guard_integer_out_of_range_blocked(self):
        with self.assertRaises(guarded.GuardedSigningError) as ctx:
            guarded.compute_payload_hash_guarded(
                '{"startDate":"a","endDate":"b","capacity":9007199254740992}', operation="slot_generate"
            )
        self.assertEqual(ctx.exception.stage, "COMMON_TYPE_GUARD")
        self.assertEqual(ctx.exception.reason, "INTEGER_OUT_OF_SAFE_RANGE")

    def test_request_schema_unregistered_field_blocked(self):
        with self.assertRaises(guarded.GuardedSigningError) as ctx:
            guarded.compute_payload_hash_guarded('{"status":"A","extra":"nope"}', operation="consultation_status_update")
        self.assertEqual(ctx.exception.stage, "REQUEST_SCHEMA")
        self.assertEqual(ctx.exception.reason, "UNREGISTERED_FIELD")

    def test_request_schema_required_field_missing_blocked(self):
        with self.assertRaises(guarded.GuardedSigningError) as ctx:
            guarded.compute_payload_hash_guarded('{"handledBy":"user1"}', operation="consultation_status_update")
        self.assertEqual(ctx.exception.stage, "REQUEST_SCHEMA")
        self.assertEqual(ctx.exception.reason, "REQUIRED_FIELD_MISSING")

    def test_request_schema_unknown_operation_blocked(self):
        with self.assertRaises(guarded.GuardedSigningError) as ctx:
            guarded.compute_payload_hash_guarded('{"x":1}', operation="not_a_real_operation")
        self.assertEqual(ctx.exception.stage, "REQUEST_SCHEMA")
        self.assertEqual(ctx.exception.reason, "UNKNOWN_OPERATION")


class ExistingFunctionLimitationTestCase(unittest.TestCase):
    """작업지시 3번 "미검증 객체를 직접 서명하는 기존 함수의 한계"를
    실측으로 확인한다 — signing_v2.py 자체는 수정하지 않았으므로,
    wrapper를 거치지 않고 직접 호출하면 아무 보호도 받지 못한다."""

    def test_direct_compute_payload_hash_accepts_float_without_warning(self):
        # wrapper(raw JSON 경로)를 거쳤다면 거절됐을 입력이지만, signing_v2.py를
        # 직접 호출하면 아무 예외 없이 그대로 해시가 계산된다.
        result = sv2.compute_payload_hash({"count": 1.0})
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 64)

    def test_direct_compute_payload_hash_accepts_unicode_key_without_warning(self):
        result = sv2.compute_payload_hash({"환자명": "홍길동"})
        self.assertIsInstance(result, str)

    def test_direct_compute_payload_hash_accepts_unregistered_shape_without_warning(self):
        result = sv2.compute_payload_hash({"totallyUnregisteredField": "x", "another": 1})
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
