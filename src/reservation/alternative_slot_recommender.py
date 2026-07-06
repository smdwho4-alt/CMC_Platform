# -*- coding: utf-8 -*-
"""
CSHSP Alternative Slot Recommender — Sprint B
요청 슬롯이 불가할 때 대체 Slot을 추천한다.

기준:
- AVAILABLE 상태 + 정원 여유 슬롯만
- 프로그램 제한(programRestriction) 충족
- 동일 검사실(room_id 지정 시) 우선
- 요청일 기준 가까운 날짜 우선, 동일 날짜면 요청시간에 가까운 순
- 최대 5개 추천
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

import core_data_loader as loader  # noqa: E402

MAX_RECOMMENDATIONS = 5


def _minutes(hhmm: str) -> int:
    h, m = str(hhmm).split(":")
    return int(h) * 60 + int(m)


def recommend_alternative_slots(
    requested_date: str,
    requested_time: str | None = None,
    program_id: str | None = None,
    room_id: str | None = None,
    data_dir: Path | str | None = None,
    max_results: int = MAX_RECOMMENDATIONS,
    exclude_slot_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """대체 Slot 후보를 우선순위 순으로 최대 max_results개 반환."""
    data_dir = Path(data_dir) if data_dir else loader.DATA_DIR
    req_date = datetime.strptime(requested_date, "%Y-%m-%d").date()
    req_min = _minutes(requested_time) if requested_time else None
    exclude = exclude_slot_ids or set()

    candidates: list[dict[str, Any]] = []
    for s in loader.load_entity("Slot", data_dir):
        if s.get("id") in exclude:
            continue
        if s.get("status") != "AVAILABLE":
            continue
        if int(s.get("reservedCount", 0)) >= int(s.get("capacity", 0)):
            continue
        if room_id and s.get("roomId") != room_id:
            continue
        if (s.get("programRestriction") and program_id
                and s["programRestriction"] != program_id):
            continue
        candidates.append(s)

    def sort_key(s: dict[str, Any]):
        d = datetime.strptime(s["date"], "%Y-%m-%d").date()
        day_dist = abs((d - req_date).days)
        time_dist = abs(_minutes(s["time"]) - req_min) if req_min is not None else 0
        return (day_dist, d, time_dist, s["time"])

    return sorted(candidates, key=sort_key)[: max(0, max_results)]
