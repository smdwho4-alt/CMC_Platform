# -*- coding: utf-8 -*-
"""
CSHSP Reservation Audit — Sprint B
모든 예약 이벤트를 audit_logs.json에 append-only로 기록한다.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

import core_data_loader as loader  # noqa: E402
from json_store import next_seq, now_iso, read_doc, today_ymd, write_doc  # noqa: E402

# Sprint B 표준 이벤트 10종 + 운영 확장 2종(NO_SHOW/COMPLETED)
AUDIT_EVENTS = [
    "RESERVATION_REQUESTED",
    "RESERVATION_APPROVED",
    "RESERVATION_CANCELLED",
    "RESERVATION_REJECTED",
    "RESERVATION_CHANGED",
    "SLOT_HELD",
    "SLOT_RELEASED",
    "SLOT_FULL",
    "INVALID_TRANSITION",
    "DUPLICATED_REJECTED",
    "RESERVATION_NO_SHOW",   # 확장
    "RESERVATION_COMPLETED", # 확장
    "SAFETY_BLOCKED",        # Sprint F: AI Safety Guard 차단 이력
]


def _actor_role(actor_user_id: str, data_dir: Path) -> str | None:
    """users.json에서 actor의 roleId 조회 (없으면 None)"""
    for u in loader.load_entity("User", data_dir):
        if u.get("id") == actor_user_id:
            return u.get("roleId")
    return None


def append_audit(
    data_dir: Path | str,
    action: str,
    entity_type: str,
    entity_id: str | None,
    actor_user_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    channel: str = "ENGINE",
    note: str | None = None,
) -> dict[str, Any]:
    """감사로그 1건 추가 후 해당 레코드 반환. 기존 로그는 수정하지 않는다."""
    if action not in AUDIT_EVENTS:
        raise ValueError(f"등록되지 않은 감사 이벤트: {action}")

    data_dir = Path(data_dir)
    path = data_dir / "audit_logs.json"
    doc = read_doc(path)

    ymd = today_ymd()
    seq = next_seq(doc["records"], rf"AUD-{ymd}-(\d{{4}})")

    record: dict[str, Any] = {
        "id": f"AUD-{ymd}-{seq:04d}",
        "timestamp": now_iso(),
        "actorUserId": actor_user_id,
        "actorRole": _actor_role(actor_user_id, data_dir),
        "action": action,
        "entityType": entity_type,
        "entityId": entity_id,
        "before": before,
        "after": after,
        "channel": channel,
    }
    if note:
        record["note"] = note

    doc["records"].append(record)
    write_doc(path, doc)
    return record
