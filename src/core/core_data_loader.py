# -*- coding: utf-8 -*-
"""
CSHSP Core Data Loader — Sprint A
천안의료원 건강검진센터 AI 플랫폼 Core Data Layer

- data/*.json 20개 Entity 파일 로드
- 파일 없음 / 빈 파일 / JSON 파싱 오류 방어
- UTF-8 인코딩 보장
- Dashboard / KPI Engine / Reservation Engine(Sprint B)에서 재사용
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 프로젝트 루트 기준 data 폴더 (src/core/ 에서 두 단계 상위)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

# Entity명 → 파일명 매핑 (20개)
ENTITY_FILES: dict[str, str] = {
    "Patient": "patients.json",
    "Reservation": "reservations.json",
    "Program": "programs.json",
    "OptionalTest": "optional_tests.json",
    "Business": "businesses.json",
    "Doctor": "doctors.json",
    "Nurse": "nurses.json",
    "Equipment": "equipment.json",
    "Room": "rooms.json",
    "Schedule": "schedules.json",
    "Slot": "slots.json",
    "Consent": "consents.json",
    "Questionnaire": "questionnaires.json",
    "CRM": "crm.json",
    "Dashboard": "dashboard.json",
    "Statistics": "statistics.json",
    "AuditLog": "audit_logs.json",
    "User": "users.json",
    "Role": "roles.json",
    "Notification": "notifications.json",
}

# 예약 상태값 표준 (Sprint A 확정)
RESERVATION_STATUSES = [
    "REQUESTED",         # 예약 신청
    "PENDING_APPROVAL",  # 직원 승인 대기
    "CONFIRMED",         # 예약 확정
    "CANCELLED",         # 예약 취소
    "CHANGED",           # 예약 변경
    "COMPLETED",         # 검진 완료
    "NO_SHOW",           # 노쇼
    "WAITING",           # 대기예약
    "REJECTED",          # 예약 불가
]

# Slot 상태값 표준 (Sprint A 확정)
SLOT_STATUSES = ["AVAILABLE", "FULL", "WAITING", "DUPLICATED", "HOLD", "BLOCKED"]

# 기존(레거시) 한글 상태값 → 표준 상태값 매핑
LEGACY_STATUS_MAP = {
    "예약접수": "REQUESTED",
    "예약확정": "CONFIRMED",
    "검진완료": "COMPLETED",
    "일정변경": "CHANGED",
    "예약취소": "CANCELLED",
}


class CoreDataError(Exception):
    """Core Data Layer 공통 예외"""


def load_entity(entity: str, data_dir: Path | None = None, strict: bool = False) -> list[dict[str, Any]]:
    """Entity명으로 레코드 리스트를 반환한다.

    - 파일 없음 / 빈 파일 → strict=False면 빈 리스트, strict=True면 CoreDataError
    - 파일 형식은 {"entity", "records": [...]} 래퍼 또는 순수 배열 모두 지원
    """
    if entity not in ENTITY_FILES:
        raise CoreDataError(f"알 수 없는 Entity: {entity} (등록된 Entity: {len(ENTITY_FILES)}개)")

    path = (data_dir or DATA_DIR) / ENTITY_FILES[entity]

    if not path.exists():
        if strict:
            raise CoreDataError(f"데이터 파일 없음: {path}")
        return []

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        if strict:
            raise CoreDataError(f"빈 데이터 파일: {path}")
        return []

    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        raise CoreDataError(f"JSON 파싱 오류 ({path.name}): {e}") from e

    if isinstance(doc, list):          # 순수 배열 형식 호환
        return doc
    if isinstance(doc, dict):
        records = doc.get("records", [])
        if not isinstance(records, list):
            raise CoreDataError(f"records가 배열이 아님: {path.name}")
        return records
    raise CoreDataError(f"지원하지 않는 JSON 최상위 형식: {path.name}")


def load_meta(entity: str, data_dir: Path | None = None) -> dict[str, Any]:
    """Entity 파일의 meta 블록(개인정보 여부, 집계 가능 여부 등)을 반환한다."""
    path = (data_dir or DATA_DIR) / ENTITY_FILES[entity]
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}
    return doc.get("meta", {}) if isinstance(doc, dict) else {}


def load_all(data_dir: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """20개 Entity 전체를 {Entity명: 레코드리스트} 형태로 로드한다."""
    return {entity: load_entity(entity, data_dir) for entity in ENTITY_FILES}


def get_by_id(entity: str, record_id: str, data_dir: Path | None = None) -> dict[str, Any] | None:
    """id로 단일 레코드를 조회한다. 없으면 None."""
    for rec in load_entity(entity, data_dir):
        if rec.get("id") == record_id:
            return rec
    return None


def normalize_legacy_status(status: str) -> str:
    """레거시 한글 상태값을 표준 상태값으로 변환한다. 이미 표준이면 그대로 반환."""
    return LEGACY_STATUS_MAP.get(status, status)


def summary(data_dir: Path | None = None) -> dict[str, int]:
    """Entity별 레코드 수 요약 — Dashboard/KPI Engine 헬스체크용."""
    return {entity: len(records) for entity, records in load_all(data_dir).items()}


if __name__ == "__main__":
    for name, count in summary().items():
        print(f"{name:15s} {count:3d}건")
