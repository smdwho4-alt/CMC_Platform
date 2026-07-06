# -*- coding: utf-8 -*-
"""
CSHSP Reservation Agent — AI 예약비서 (Sprint E)
예약 '신청'까지만 수행한다. 확정 권한 없음 (API 403 + 도구 미제공 이중 차단).
"""
from __future__ import annotations

from function_tools import FunctionTools
from safety_guard import STAFF_CONFIRM_NOTICE, ensure_staff_notice


class ReservationAgent:
    name = "reservation_agent"

    def __init__(self, tools: FunctionTools):
        self.tools = tools

    def request_reservation(self, patient_id: str, program_id: str, date: str, time: str,
                            slot_id: str | None = None, memo: str = "",
                            allow_waiting: bool = False) -> dict:
        """슬롯 확인 → 신청 → 불가 시 대체 추천. 응답에 확정 절차 안내 고정."""
        slot_id = slot_id or f"SLOT-{date.replace('-', '')}-{time.replace(':', '')}-A"
        result = self.tools.create_reservation_request(
            patient_id, program_id, date, time, slot_id, memo, allow_waiting)

        if result["ok"]:
            return {"agent": self.name, "success": True,
                    "reservation": result["reservation"],
                    "message": ensure_staff_notice(result["message"])}

        # 불가 → 사유 + 대체 슬롯 안내
        alts = result.get("alternatives") or self.tools.recommend_alternative_slots(
            date, time, program_id)["alternatives"]
        alt_text = "\n".join(f"  · {a['date']} {a['time']} (잔여 {a['capacity'] - a['reservedCount']}석)"
                             for a in alts[:5]) or "  · 현재 안내 가능한 대체 시간이 없습니다. 검진센터로 문의해 주세요."
        verdict_msg = {
            "FULL": "요청하신 시간은 정원이 마감되었습니다.",
            "DUPLICATED": "같은 날짜에 이미 접수된 예약이 있습니다. 기존 예약 변경을 원하시면 상담을 접수해 드리겠습니다.",
            "BLOCKED": "요청하신 날짜는 휴진 또는 검사 불가일입니다.",
            "HOLD": "요청하신 시간은 현재 다른 처리로 보류 중입니다.",
        }.get(result.get("verdict"), "요청하신 시간은 예약이 어렵습니다.")
        return {"agent": self.name, "success": False,
                "verdict": result.get("verdict"), "alternatives": alts[:5],
                "message": f"{verdict_msg}\n가까운 대체 시간을 추천드립니다:\n{alt_text}\n\n{STAFF_CONFIRM_NOTICE}"}

    def available_slots(self, date_from: str, date_to: str) -> dict:
        r = self.tools.list_available_slots(date_from, date_to)
        return {"agent": self.name, "success": r["ok"], "slots": r["slots"]}
