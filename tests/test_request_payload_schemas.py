# -*- coding: utf-8 -*-
"""
CSHSP Sprint8 Commit8-3b — src/idempotency/request_payload_schemas.py 단위 테스트
(요청별 payload 스키마 가드, Option B 2단계)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src" / "idempotency"))

import request_payload_schemas as rs  # noqa: E402


class KnownOperationTestCase(unittest.TestCase):
    def test_valid_reservation_create_accepted(self):
        rs.validate_request_schema(
            "reservation_create",
            {
                "patientId": "P-0001", "programId": "PRG-01", "requestedDate": "2026-10-10",
                "requestedTime": "09:00", "slotId": "SLOT-01",
            },
        )  # 예외 없으면 통과(선택 필드 생략 가능)

    def test_valid_reservation_create_with_optional_fields_accepted(self):
        rs.validate_request_schema(
            "reservation_create",
            {
                "patientId": "P-0001", "programId": "PRG-01", "requestedDate": "2026-10-10",
                "requestedTime": "09:00", "slotId": "SLOT-01", "channel": "ADMIN",
                "allowWaiting": True, "memo": None,
            },
        )

    def test_unregistered_field_rejected(self):
        with self.assertRaises(rs.RequestSchemaError) as ctx:
            rs.validate_request_schema(
                "reservation_create",
                {
                    "patientId": "P-0001", "programId": "PRG-01", "requestedDate": "2026-10-10",
                    "requestedTime": "09:00", "slotId": "SLOT-01", "unexpectedField": "x",
                },
            )
        self.assertEqual(ctx.exception.reason, "UNREGISTERED_FIELD")
        self.assertEqual(ctx.exception.field, "unexpectedField")

    def test_required_field_missing_rejected(self):
        with self.assertRaises(rs.RequestSchemaError) as ctx:
            rs.validate_request_schema(
                "reservation_create",
                {"patientId": "P-0001", "programId": "PRG-01", "requestedDate": "2026-10-10"},
            )
        self.assertEqual(ctx.exception.reason, "REQUIRED_FIELD_MISSING")

    def test_field_type_mismatch_rejected(self):
        with self.assertRaises(rs.RequestSchemaError) as ctx:
            rs.validate_request_schema(
                "reservation_create",
                {
                    "patientId": "P-0001", "programId": "PRG-01", "requestedDate": "2026-10-10",
                    "requestedTime": "09:00", "slotId": "SLOT-01", "allowWaiting": "true",  # bool이어야 함
                },
            )
        self.assertEqual(ctx.exception.reason, "FIELD_TYPE_MISMATCH")
        self.assertEqual(ctx.exception.field, "allowWaiting")

    def test_bool_not_accepted_as_int_field(self):
        """bool은 int의 서브클래스이므로 capacity(int) 필드에 bool이
        오면 거절해야 한다(payload_schema_guard.py와 동일 원칙)."""
        with self.assertRaises(rs.RequestSchemaError) as ctx:
            rs.validate_request_schema(
                "slot_generate",
                {"startDate": "2026-10-01", "endDate": "2026-10-31", "capacity": True},
            )
        self.assertEqual(ctx.exception.reason, "FIELD_TYPE_MISMATCH")

    def test_null_not_allowed_rejected(self):
        with self.assertRaises(rs.RequestSchemaError) as ctx:
            rs.validate_request_schema(
                "reservation_create",
                {
                    "patientId": None, "programId": "PRG-01", "requestedDate": "2026-10-10",
                    "requestedTime": "09:00", "slotId": "SLOT-01",
                },
            )
        self.assertEqual(ctx.exception.reason, "NULL_NOT_ALLOWED")

    def test_null_allowed_field_accepted(self):
        rs.validate_request_schema(
            "consultation_status_update", {"status": "IN_PROGRESS", "handledBy": None}
        )

    def test_unknown_operation_rejected(self):
        with self.assertRaises(rs.RequestSchemaError) as ctx:
            rs.validate_request_schema("some_unregistered_operation", {"x": 1})
        self.assertEqual(ctx.exception.reason, "UNKNOWN_OPERATION")

    def test_free_form_dict_operations_not_registered(self):
        """ChatBody.context/QSubmitBody.answers는 이번 서명 대상에서
        제외됐다 — 레지스트리에 operation 자체가 없어야 한다."""
        self.assertNotIn("chat", rs.list_known_operations())
        self.assertNotIn("questionnaire_submit", rs.list_known_operations())


class RejectReservationLengthTestCase(unittest.TestCase):
    """RejectReservationBody의 실제 길이 검증(2~200자, routes_admin_portal.py
    재확인)을 그대로 재사용하는지 확인."""

    def test_reason_too_short_rejected(self):
        with self.assertRaises(rs.RequestSchemaError) as ctx:
            rs.validate_request_schema("reservation_reject", {"reason": "a"})
        self.assertEqual(ctx.exception.reason, "FIELD_TOO_SHORT")

    def test_reason_too_long_rejected(self):
        with self.assertRaises(rs.RequestSchemaError) as ctx:
            rs.validate_request_schema("reservation_reject", {"reason": "a" * 201})
        self.assertEqual(ctx.exception.reason, "FIELD_TOO_LONG")

    def test_reason_valid_length_accepted(self):
        rs.validate_request_schema("reservation_reject", {"reason": "검진 일정 중복으로 거절"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
