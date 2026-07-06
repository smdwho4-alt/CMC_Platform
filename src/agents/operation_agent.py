# -*- coding: utf-8 -*-
"""
CSHSP Operation Agent — AI 운영비서 (Sprint E)
직원용 운영 요약(승인 대기·KPI). 직원 계정(X-User-Id)으로 API를 호출하므로
AI 예약비서 계정과 권한이 분리된다.
"""
from __future__ import annotations

from function_tools import ApiClient


class OperationAgent:
    name = "operation_agent"

    def __init__(self, api: ApiClient, staff_user_id: str = "USR-0002"):
        self.api = api
        self.staff = staff_user_id

    def daily_brief(self) -> dict:
        code_k, kpi = self.api.get("/api/dashboard/kpi", user_id=self.staff)
        code_p, pending = self.api.get("/api/reservations/pending", user_id=self.staff)
        if code_k != 200 or code_p != 200:
            return {"agent": self.name, "success": False, "message": "운영 데이터 조회 실패 (권한/서버 확인)"}
        lines = [f"  · {r.get('reservationNo') or r.get('id')} {r.get('patientName')} — {r.get('reservationDate')} {r.get('wishTime')} ({r.get('channel')})"
                 for r in pending["records"][:5]]
        msg = (f"[운영 브리핑] 승인 대기 {kpi['pending']}건 / 확정 {kpi['confirmed']}건 / "
               f"취소 {kpi['cancelled']}건 / 노쇼 {kpi['noShow']}건 / Slot 가동률 {kpi['slotUtilization']}% / "
               f"온라인 비율 {kpi['onlineRatio']}%")
        if lines:
            msg += "\n승인 대기 목록:\n" + "\n".join(lines)
        return {"agent": self.name, "success": True, "kpi": kpi,
                "pendingCount": kpi["pending"], "message": msg}
