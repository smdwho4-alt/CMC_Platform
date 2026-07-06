# -*- coding: utf-8 -*-
"""
CSHSP CRM Agent — AI CRM (Sprint E)
상담 접수(CRM OPEN)와 발송 대기 알림(Notification PENDING) 생성을 담당한다.
실제 발송·상담 처리는 직원/발송 워커가 수행한다.
"""
from __future__ import annotations

from function_tools import FunctionTools


class CrmAgent:
    name = "crm_agent"

    def __init__(self, tools: FunctionTools):
        self.tools = tools

    def open_ticket(self, patient_id: str, summary: str,
                    reservation_id: str | None = None,
                    notify_content: str | None = None) -> dict:
        """상담 접수 + 안내 알림 PENDING 생성."""
        r = self.tools.create_crm_notification(
            patient_id,
            content=notify_content or f"[천안의료원] 상담이 접수되었습니다: {summary} — 담당자가 확인 후 연락드립니다.",
            reservationId=reservation_id, summary=summary)
        if not r["ok"]:
            return {"agent": self.name, "success": False,
                    "message": f"상담 접수에 실패했습니다: {r.get('error')}"}
        return {"agent": self.name, "success": True,
                "notification": r.get("notification"), "crm": r.get("crm"),
                "message": "상담이 접수되었습니다. 검진센터 담당자가 확인 후 연락드리겠습니다. (문의 041-570-7333)"}

    def escalate_medical(self, patient_id: str, topic: str) -> dict:
        """의료 판단 필요 문의를 의료진 상담으로 에스컬레이션."""
        return self.open_ticket(
            patient_id, summary=f"[의료진 상담 필요] {topic}",
            notify_content="[천안의료원] 의료진 상담이 필요한 문의가 접수되었습니다. 담당 간호사가 연락드립니다.")
