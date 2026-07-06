# -*- coding: utf-8 -*-
"""
CSHSP Slot Generator — Sprint B
영업일 × 시간대 × 정원 기준으로 Slot을 생성한다.

규칙:
- 주말(토/일) 제외
- schedules.json의 HOLIDAY(BLOCKED) 날짜 제외 (공휴일·병원 휴진일)
- 기존 Slot id는 절대 덮어쓰지 않음 (중복 생성 방지)
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

import core_data_loader as loader  # noqa: E402
from json_store import now_iso, read_doc, write_doc  # noqa: E402

# 기존 플랫폼 TIME_SLOTS(programs_data_new.js)와 동일 체계
DEFAULT_TIMES = ["08:00", "08:30", "09:00", "09:30", "10:00",
                 "10:30", "11:00", "13:00", "13:30", "14:00"]
DEFAULT_CAPACITY = 6
DEFAULT_ROOM_ID = "ROOM-0001"  # 접수


def _closed_dates(data_dir: Path | None) -> set[str]:
    """공휴일·병원 휴진일 (HOLIDAY + BLOCKED)"""
    return {
        s.get("date")
        for s in loader.load_entity("Schedule", data_dir)
        if s.get("type") == "HOLIDAY" and s.get("status") == "BLOCKED"
    }


def generate_slots(
    start_date: str,
    end_date: str,
    data_dir: Path | str | None = None,
    room_id: str = DEFAULT_ROOM_ID,
    capacity: int = DEFAULT_CAPACITY,
    times: list[str] | None = None,
    skip_weekends: bool = True,
) -> list[dict[str, Any]]:
    """기간 내 Slot 생성 후 slots.json에 저장. 생성된 레코드 목록 반환."""
    data_dir = Path(data_dir) if data_dir else loader.DATA_DIR
    times = times or DEFAULT_TIMES

    d0 = datetime.strptime(start_date, "%Y-%m-%d").date()
    d1 = datetime.strptime(end_date, "%Y-%m-%d").date()
    if d1 < d0:
        raise ValueError(f"종료일이 시작일보다 빠름: {start_date} ~ {end_date}")

    closed = _closed_dates(data_dir)
    path = data_dir / "slots.json"
    doc = read_doc(path)
    existing_ids = {r.get("id") for r in doc["records"]}

    created: list[dict[str, Any]] = []
    day = d0
    while day <= d1:
        ds = day.isoformat()
        if (skip_weekends and day.weekday() >= 5) or ds in closed:
            day += timedelta(days=1)
            continue
        for t in times:
            slot_id = f"SLOT-{ds.replace('-', '')}-{t.replace(':', '')}-A"
            if slot_id in existing_ids:
                continue
            rec = {
                "id": slot_id,
                "date": ds,
                "time": t,
                "capacity": capacity,
                "reservedCount": 0,
                "waitingCount": 0,
                "status": "AVAILABLE",
                "roomId": room_id,
                "programRestriction": None,
                "createdAt": now_iso(),
                "updatedAt": now_iso(),
            }
            doc["records"].append(rec)
            existing_ids.add(slot_id)
            created.append(rec)
        day += timedelta(days=1)

    if created:
        write_doc(path, doc)
    return created
