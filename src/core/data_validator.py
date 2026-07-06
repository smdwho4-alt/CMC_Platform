# -*- coding: utf-8 -*-
"""
CSHSP Data Validator — Sprint A
Core Data Layer 기본 검증 모듈

검증 항목:
- 예약/환자/Slot id 중복
- 예약 상태값 / Slot 상태값 유효성
- 예약일자·일시 형식 (YYYY-MM-DD / ISO 8601)
- Entity별 필수 필드 누락
- 참조 무결성 (예약 → 환자/프로그램/슬롯)
"""
from __future__ import annotations

import re
from typing import Any

from core_data_loader import (
    ENTITY_FILES,
    RESERVATION_STATUSES,
    SLOT_STATUSES,
    load_all,
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

# Entity별 필수 필드 (id는 전 Entity 공통)
REQUIRED_FIELDS: dict[str, list[str]] = {
    "Patient": ["id", "name", "gender", "status", "createdAt", "updatedAt"],
    "Reservation": ["id", "patientId", "programId", "reservationDate", "status", "createdAt", "updatedAt"],
    "Program": ["id", "code", "name", "status"],
    "OptionalTest": ["id", "name", "category", "status"],
    "Business": ["id", "name", "type", "status"],
    "Doctor": ["id", "name", "status"],
    "Nurse": ["id", "name", "status"],
    "Equipment": ["id", "name", "roomId", "status"],
    "Room": ["id", "name", "status"],
    "Schedule": ["id", "type", "date", "status"],
    "Slot": ["id", "date", "time", "capacity", "status"],
    "Consent": ["id", "patientId", "type", "status"],
    "Questionnaire": ["id", "patientId", "reservationId", "status"],
    "CRM": ["id", "patientId", "channel", "category", "status"],
    "Dashboard": ["id", "date", "kpi"],
    "Statistics": ["id", "period", "periodType", "totalExaminees", "totalRevenue"],
    "AuditLog": ["id", "timestamp", "actorUserId", "action", "entityType"],
    "User": ["id", "username", "roleId", "status"],
    "Role": ["id", "name", "permissions"],
    "Notification": ["id", "type", "templateCode", "status"],
}


def _dup_ids(records: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    dups: list[str] = []
    for rec in records:
        rid = rec.get("id")
        if rid in seen:
            dups.append(str(rid))
        elif rid is not None:
            seen.add(rid)
    return dups


def validate_all(data: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, list[str]]:
    """전체 검증 실행. {'errors': [...], 'warnings': [...]} 반환."""
    if data is None:
        data = load_all()

    errors: list[str] = []
    warnings: list[str] = []

    # 1) 전 Entity 공통: id 중복 + 필수 필드
    for entity in ENTITY_FILES:
        records = data.get(entity, [])
        for dup in _dup_ids(records):
            errors.append(f"[{entity}] id 중복: {dup}")
        required = REQUIRED_FIELDS.get(entity, ["id"])
        for rec in records:
            missing = [f for f in required if rec.get(f) in (None, "") and f not in ("businessId",)]
            # null 허용 필드 예외 처리: Reservation.slotId 등은 필수 아님
            if missing:
                errors.append(f"[{entity}] {rec.get('id', '(id없음)')} 필수 필드 누락: {', '.join(missing)}")

    # 2) 예약 상태값 + 날짜 형식 + 참조 무결성
    patient_ids = {r.get("id") for r in data.get("Patient", [])}
    program_ids = {r.get("id") for r in data.get("Program", [])}
    slot_ids = {r.get("id") for r in data.get("Slot", [])}

    for rec in data.get("Reservation", []):
        rid = rec.get("id", "(id없음)")
        if rec.get("status") not in RESERVATION_STATUSES:
            errors.append(f"[Reservation] {rid} 잘못된 상태값: {rec.get('status')}")
        if rec.get("reservationDate") and not DATE_RE.match(str(rec["reservationDate"])):
            errors.append(f"[Reservation] {rid} 예약일자 형식 오류: {rec['reservationDate']}")
        for ts_field in ("createdAt", "updatedAt"):
            if rec.get(ts_field) and not DATETIME_RE.match(str(rec[ts_field])):
                errors.append(f"[Reservation] {rid} {ts_field} ISO 형식 오류: {rec[ts_field]}")
        if rec.get("patientId") not in patient_ids:
            errors.append(f"[Reservation] {rid} 존재하지 않는 patientId: {rec.get('patientId')}")
        if rec.get("programId") not in program_ids:
            errors.append(f"[Reservation] {rid} 존재하지 않는 programId: {rec.get('programId')}")
        if rec.get("slotId") and rec.get("slotId") not in slot_ids:
            warnings.append(f"[Reservation] {rid} slotId가 slots.json에 없음: {rec.get('slotId')}")

    # 3) Slot 상태값 + 정원 정합성
    for rec in data.get("Slot", []):
        sid = rec.get("id", "(id없음)")
        if rec.get("status") not in SLOT_STATUSES:
            errors.append(f"[Slot] {sid} 잘못된 상태값: {rec.get('status')}")
        if rec.get("date") and not DATE_RE.match(str(rec["date"])):
            errors.append(f"[Slot] {sid} 날짜 형식 오류: {rec['date']}")
        cap, reserved = rec.get("capacity"), rec.get("reservedCount")
        if isinstance(cap, int) and isinstance(reserved, int):
            if reserved > cap:
                errors.append(f"[Slot] {sid} 정원 초과: {reserved}/{cap}")
            if reserved >= cap and rec.get("status") == "AVAILABLE":
                warnings.append(f"[Slot] {sid} 정원 마감인데 상태가 AVAILABLE")

    return {"errors": errors, "warnings": warnings}


def print_report(result: dict[str, list[str]]) -> bool:
    """검증 결과를 출력하고 통과 여부(bool)를 반환한다."""
    ok = not result["errors"]
    print(f"검증 결과: {'PASS' if ok else 'FAIL'}  (오류 {len(result['errors'])}건, 경고 {len(result['warnings'])}건)")
    for e in result["errors"]:
        print(f"  [오류] {e}")
    for w in result["warnings"]:
        print(f"  [경고] {w}")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if print_report(validate_all()) else 1)
