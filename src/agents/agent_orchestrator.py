# -*- coding: utf-8 -*-
"""
CSHSP Agent Orchestrator — Sprint E
모든 사용자 입력의 단일 진입점.

처리 순서 (고정):
  ① Safety Guard — 진단/처방/결과해석/응급 차단, 즉시확정 요청은 절차 안내로 전환
  ② 의도 분류 (키워드 규칙 — 향후 LLM 분류기로 교체 지점)
  ③ 담당 에이전트 위임 (예약/추천/문진/CRM/운영)

LLM 연동: TOOL_SCHEMAS(function_tools)를 Claude tool-use에 등록하고,
이 오케스트레이터의 handle_message를 대화 루프의 도구 실행기로 사용한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import safety_guard  # noqa: E402
from crm_agent import CrmAgent  # noqa: E402
from function_tools import ApiClient, FunctionTools  # noqa: E402
from operation_agent import OperationAgent  # noqa: E402
from questionnaire_agent import QuestionnaireAgent  # noqa: E402
from recommendation_agent import RecommendationAgent  # noqa: E402
from reservation_agent import ReservationAgent  # noqa: E402

_INTENTS: list[tuple[str, re.Pattern]] = [
    ("operation", re.compile(r"(운영\s*(브리핑|현황|요약)|승인\s*대기\s*(현황|목록|몇))")),
    ("questionnaire", re.compile(r"(문진|사전\s*설문)")),
    ("crm", re.compile(r"(상담원|상담\s*(접수|연결|원해)|불만|항의|민원|사람과)")),
    ("reservation", re.compile(r"(예약|신청|잡아|접수)")),
    ("recommendation", re.compile(r"(추천|어떤\s*(검진|프로그램)|프로그램|선택검사|가격|비용|금식|수면비|얼마)")),
]


class AgentOrchestrator:
    def __init__(self, base_url: str | None = None, data_dir: str | Path | None = None,
                 staff_user_id: str = "USR-0002"):
        api = ApiClient(base_url=base_url, data_dir=data_dir)
        self.tools = FunctionTools(api=api, data_dir=data_dir)
        self.reservation = ReservationAgent(self.tools)
        self.recommendation = RecommendationAgent(self.tools)
        self.questionnaire = QuestionnaireAgent(self.tools)
        self.crm = CrmAgent(self.tools)
        self.operation = OperationAgent(api, staff_user_id)

    # ── 의도 분류 (규칙 기반 초안) ──
    @staticmethod
    def classify(text: str) -> str:
        for intent, pattern in _INTENTS:
            if pattern.search(text):
                return intent
        return "recommendation"  # 기본: 지식 안내

    # ── 단일 진입 ──
    def handle_message(self, text: str, context: dict | None = None) -> dict:
        """context: {patientId, programId, date, time, slotId, reservationId, ...} (대화 상태)"""
        ctx = context or {}

        # ① Safety Guard
        guard = safety_guard.check(text)
        if not guard["allowed"]:
            response = {"agent": "safety_guard", "blocked": True,
                        "category": guard["category"], "message": guard["message"]}
            # 의료 문의는 CRM 에스컬레이션 제안 (환자 식별 시 자동 접수)
            if guard["category"] != "EMERGENCY" and ctx.get("patientId"):
                esc = self.crm.escalate_medical(ctx["patientId"], topic=text[:80])
                response["escalation"] = esc
            return response

        intent = self.classify(text)
        notice_prefix = (guard["message"] + "\n\n") if guard["category"] == "CONFIRM_REDIRECT" else ""

        # ② 에이전트 위임
        if intent == "reservation":
            required = ("patientId", "programId", "date", "time")
            missing = [k for k in required if not ctx.get(k)]
            if missing:
                return {"agent": "reservation_agent", "blocked": False, "needInput": missing,
                        "message": notice_prefix + "예약 신청을 도와드리겠습니다. "
                                   f"다음 정보가 필요합니다: {', '.join(missing)}"}
            result = self.reservation.request_reservation(
                ctx["patientId"], ctx["programId"], ctx["date"], ctx["time"],
                ctx.get("slotId"), ctx.get("memo", ""), ctx.get("allowWaiting", False))
        elif intent == "questionnaire":
            if not (ctx.get("patientId") and ctx.get("reservationId")):
                return {"agent": "questionnaire_agent", "blocked": False,
                        "needInput": ["patientId", "reservationId"],
                        "message": "문진을 시작하려면 예약 정보가 필요합니다."}
            result = self.questionnaire.start(ctx["patientId"], ctx["reservationId"])
        elif intent == "crm":
            if not ctx.get("patientId"):
                return {"agent": "crm_agent", "blocked": False, "needInput": ["patientId"],
                        "message": "상담 접수를 위해 본인 확인이 필요합니다."}
            result = self.crm.open_ticket(ctx["patientId"], summary=text[:120],
                                          reservation_id=ctx.get("reservationId"))
        elif intent == "operation":
            result = self.operation.daily_brief()
        else:
            result = self.recommendation.answer_faq(text) if not ctx.get("recommend") \
                else self.recommendation.recommend_program(**ctx["recommend"])

        result.setdefault("blocked", False)
        if notice_prefix:
            result["message"] = notice_prefix + result["message"]
        return result
