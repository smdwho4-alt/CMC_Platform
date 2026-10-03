# -*- coding: utf-8 -*-
"""
CSHSP Sprint8 Commit8-3b — src/idempotency/payload_schema_guard.py 단위 테스트
(payload 정규화 계약 Option B 제안서의 개발용 입력 검증 가드)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src" / "idempotency"))

import payload_schema_guard as guard  # noqa: E402


class SupportedInputTestCase(unittest.TestCase):
    def test_ascii_keys_and_plain_values_accepted(self):
        guard.validate_payload_schema_interim(
            {"reservationNo": "R-0001", "qty": 2, "active": True, "memo": None}
        )  # 예외 없으면 통과

    def test_unicode_string_value_accepted_only_key_restricted(self):
        """값(value)에 오는 Unicode 문자열은 거절 대상이 아니다 — 거절
        대상은 object key뿐이다(모듈 docstring 재확인)."""
        guard.validate_payload_schema_interim({"patientName": "홍길동", "memo": "특이사항 없음"})

    def test_nested_object_and_array_accepted(self):
        guard.validate_payload_schema_interim(
            {"items": [{"price": 10, "qty": 1}, {"price": 20, "qty": 2}], "note": "ok"}
        )

    def test_safe_integer_boundary_accepted(self):
        guard.validate_payload_schema_interim({"big": guard.SAFE_INTEGER_MAX, "small": guard.SAFE_INTEGER_MIN})


class RejectedInputTestCase(unittest.TestCase):
    def test_float_rejected(self):
        with self.assertRaises(guard.PayloadSchemaUnresolvedError) as ctx:
            guard.validate_payload_schema_interim({"count": 1.0})
        self.assertEqual(ctx.exception.reason, "FLOAT_NOT_ALLOWED")

    def test_nan_rejected(self):
        with self.assertRaises(guard.PayloadSchemaUnresolvedError) as ctx:
            guard.validate_payload_schema_interim({"x": float("nan")})
        self.assertEqual(ctx.exception.reason, "FLOAT_NOT_ALLOWED")

    def test_infinity_rejected(self):
        with self.assertRaises(guard.PayloadSchemaUnresolvedError) as ctx:
            guard.validate_payload_schema_interim({"x": float("inf")})
        self.assertEqual(ctx.exception.reason, "FLOAT_NOT_ALLOWED")

    def test_integer_out_of_safe_range_rejected(self):
        with self.assertRaises(guard.PayloadSchemaUnresolvedError) as ctx:
            guard.validate_payload_schema_interim({"bigId": guard.SAFE_INTEGER_MAX + 1})
        self.assertEqual(ctx.exception.reason, "INTEGER_OUT_OF_SAFE_RANGE")

    def test_unicode_object_key_rejected(self):
        with self.assertRaises(guard.PayloadSchemaUnresolvedError) as ctx:
            guard.validate_payload_schema_interim({"환자명": "홍길동"})
        self.assertEqual(ctx.exception.reason, "UNICODE_OR_INVALID_OBJECT_KEY")

    def test_nested_float_rejected_with_path(self):
        with self.assertRaises(guard.PayloadSchemaUnresolvedError) as ctx:
            guard.validate_payload_schema_interim({"items": [{"price": 10}, {"price": 10.5}]})
        self.assertEqual(ctx.exception.reason, "FLOAT_NOT_ALLOWED")
        self.assertEqual(ctx.exception.path, "$.items[1].price")

    def test_nested_unicode_key_rejected_with_path(self):
        with self.assertRaises(guard.PayloadSchemaUnresolvedError) as ctx:
            guard.validate_payload_schema_interim({"meta": {"환자명": "홍길동"}})
        self.assertEqual(ctx.exception.reason, "UNICODE_OR_INVALID_OBJECT_KEY")
        self.assertEqual(ctx.exception.path, "$.meta.환자명")

    def test_top_level_not_object_rejected(self):
        with self.assertRaises(guard.PayloadSchemaUnresolvedError) as ctx:
            guard.validate_payload_schema_interim([1, 2, 3])
        self.assertEqual(ctx.exception.reason, "TOP_LEVEL_PAYLOAD_MUST_BE_OBJECT")

    def test_unsupported_type_rejected(self):
        """JSON으로는 구성할 수 없는 타입(Python 고유 객체)이 호출부
        실수로 섞여 들어오는 경우에 대한 방어선(JS 쪽은 JSON.parse
        결과물에 이런 타입이 나올 수 없어 대응 테스트가 없음)."""
        with self.assertRaises(guard.PayloadSchemaUnresolvedError) as ctx:
            guard.validate_payload_schema_interim({"x": {1, 2, 3}})  # set은 JSON에 없는 타입
        self.assertEqual(ctx.exception.reason, "UNSUPPORTED_TYPE")


class DuplicateKeyTestCase(unittest.TestCase):
    def test_duplicate_key_rejected(self):
        with self.assertRaises(guard.DuplicateKeyError):
            guard.parse_json_reject_duplicates('{"qty":1,"qty":2}')

    def test_nested_duplicate_key_rejected(self):
        with self.assertRaises(guard.DuplicateKeyError):
            guard.parse_json_reject_duplicates('{"a":{"x":1,"y":2,"x":3},"b":5}')

    def test_no_duplicate_key_accepted(self):
        result = guard.parse_json_reject_duplicates('{"a":1,"b":2}')
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_duplicate_key_in_sibling_objects_not_falsely_rejected(self):
        """서로 다른 객체(형제 범위)에 동일 키 이름이 쓰이는 것은 중복이
        아니다 — 같은 object 리터럴 내부에서만 중복을 검사해야 한다."""
        result = guard.parse_json_reject_duplicates('{"a":{"x":1},"b":{"x":2}}')
        self.assertEqual(result, {"a": {"x": 1}, "b": {"x": 2}})


class RawNumberTokenTestCase(unittest.TestCase):
    """raw JSON 경로(parse_json_strict) 숫자 토큰 검증 — V04(1.0 vs 1)
    해결 핵심. 작업지시 4번 "1 허용 / 1.0·1e0 거절 / -0→0 일치"를
    그대로 구현한다."""

    def test_plain_integer_accepted(self):
        self.assertEqual(guard.parse_json_strict('{"count":1}'), {"count": 1})

    def test_decimal_point_rejected(self):
        with self.assertRaises(guard.RawNumberFormatError) as ctx:
            guard.parse_json_strict('{"count":1.0}')
        self.assertEqual(ctx.exception.reason, "FLOAT_OR_EXPONENT_NOT_ALLOWED")

    def test_exponent_rejected(self):
        with self.assertRaises(guard.RawNumberFormatError) as ctx:
            guard.parse_json_strict('{"count":1e0}')
        self.assertEqual(ctx.exception.reason, "FLOAT_OR_EXPONENT_NOT_ALLOWED")

    def test_negative_exponent_rejected(self):
        with self.assertRaises(guard.RawNumberFormatError) as ctx:
            guard.parse_json_strict('{"count":2E-3}')
        self.assertEqual(ctx.exception.reason, "FLOAT_OR_EXPONENT_NOT_ALLOWED")

    def test_minus_zero_normalized_to_zero(self):
        result = guard.parse_json_strict('{"delta":-0}')
        self.assertEqual(result["delta"], 0)
        self.assertNotIsInstance(result["delta"], float)

    def test_negative_integer_accepted(self):
        self.assertEqual(guard.parse_json_strict('{"x":-5}'), {"x": -5})

    def test_nested_float_rejected_in_raw_path(self):
        with self.assertRaises(guard.RawNumberFormatError):
            guard.parse_json_strict('{"items":[{"price":10},{"price":10.5}]}')

    def test_raw_path_also_rejects_duplicate_keys(self):
        """parse_json_strict는 숫자 토큰 검증과 중복 키 검증을 모두
        수행한다(한 번의 파싱으로 두 역할을 겸함)."""
        with self.assertRaises(guard.DuplicateKeyError):
            guard.parse_json_strict('{"a":1,"a":2}')


if __name__ == "__main__":
    unittest.main(verbosity=2)
