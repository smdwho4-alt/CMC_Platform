# -*- coding: utf-8 -*-
"""
CSHSP Notification Worker — Sprint F
notifications.json의 PENDING 알림을 처리한다.

원칙: 실제 SMS/카카오 발송은 하지 않는다 (Mock).
  - 성공 Mock → SENT + sentAt
  - 실패 Mock → FAILED + failReason + retryCount 증가 (재처리 대상)
운영 전환 시 sender 함수만 실제 발송 API(알림톡/SMS)로 교체한다.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src" / "reservation"))
sys.path.insert(0, str(_ROOT / "src" / "core"))
sys.path.insert(0, str(_ROOT / "src" / "api"))

import core_data_loader as loader  # noqa: E402
from file_lock import DataLock  # noqa: E402
from json_store import now_iso, read_doc, write_doc  # noqa: E402

MAX_RETRY = 3


def default_mock_sender(notification: dict[str, Any], patients: dict[str, dict]) -> tuple[bool, str]:
    """Mock 발송기: 수신처(환자 전화번호) 없으면 실패, 그 외 성공 처리."""
    if notification.get("type") == "SYSTEM":
        return True, "시스템 알림 (내부 표시)"
    pid = notification.get("patientId")
    patient = patients.get(pid) if pid else None
    if patient is None:
        return False, f"수신자 없음: {pid}"
    if not patient.get("phone"):
        return False, f"전화번호 없음: {pid}"
    return True, f"MOCK 발송 완료 → {patient['phone'][:8]}****"


def process_pending(data_dir: Path | str, sender: Callable | None = None,
                    limit: int | None = None) -> dict[str, Any]:
    """PENDING 알림 일괄 처리. 반환: {processed, sent, failed, skipped, details[]}"""
    data_dir = Path(data_dir)
    sender = sender or default_mock_sender
    patients = {p["id"]: p for p in loader.load_entity("Patient", data_dir)}

    sent = failed = skipped = 0
    details: list[dict] = []

    with DataLock(data_dir):
        path = data_dir / "notifications.json"
        doc = read_doc(path)
        pending = [r for r in doc["records"] if r.get("status") == "PENDING"]
        if limit:
            pending = pending[:limit]
        for rec in pending:
            if int(rec.get("retryCount", 0)) >= MAX_RETRY:
                skipped += 1
                details.append({"id": rec["id"], "result": "SKIPPED", "reason": "재시도 한도 초과"})
                continue
            ok, reason = sender(rec, patients)
            if ok:
                rec.update({"status": "SENT", "sentAt": now_iso(), "updatedAt": now_iso()})
                sent += 1
            else:
                rec.update({"status": "FAILED", "failReason": reason,
                            "retryCount": int(rec.get("retryCount", 0)) + 1, "updatedAt": now_iso()})
                failed += 1
            details.append({"id": rec["id"], "result": rec["status"], "reason": reason})
        if pending:
            write_doc(path, doc)

    return {"processed": len(pending), "sent": sent, "failed": failed,
            "skipped": skipped, "details": details}


def retry_failed(data_dir: Path | str) -> dict[str, Any]:
    """FAILED 알림을 PENDING으로 되돌려 재처리 대상으로 만든다 (한도 내)."""
    data_dir = Path(data_dir)
    restored = 0
    with DataLock(data_dir):
        path = data_dir / "notifications.json"
        doc = read_doc(path)
        for rec in doc["records"]:
            if rec.get("status") == "FAILED" and int(rec.get("retryCount", 0)) < MAX_RETRY:
                rec["status"] = "PENDING"
                rec["updatedAt"] = now_iso()
                restored += 1
        if restored:
            write_doc(path, doc)
    return {"restored": restored}


if __name__ == "__main__":
    import json
    result = process_pending(_ROOT / "data")
    print(json.dumps(result, ensure_ascii=False, indent=2))
