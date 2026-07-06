# -*- coding: utf-8 -*-
"""
CSHSP Questionnaire Agent — AI 문진 (Sprint E)
사전문진 '응답 수집'만 담당한다. 응답에 대한 의학적 평가·판단은 하지 않으며,
수집된 문진은 검진 당일 의료진이 검토한다.
"""
from __future__ import annotations

from function_tools import FunctionTools


class QuestionnaireAgent:
    name = "questionnaire_agent"

    def __init__(self, tools: FunctionTools):
        self.tools = tools

    def start(self, patient_id: str, reservation_id: str) -> dict:
        r = self.tools.start_questionnaire(patient_id, reservation_id)
        if not r["ok"]:
            return {"agent": self.name, "success": False,
                    "message": f"문진을 시작할 수 없습니다: {r.get('error')}"}
        q = r["questionnaire"]
        questions = "\n".join(f"  {i['code']}. {i['question']}" for i in q["items"])
        return {"agent": self.name, "success": True, "questionnaire": q,
                "message": ("사전문진을 시작합니다. 아래 항목에 답해 주세요. "
                            "응답 내용은 검진 당일 의료진이 확인합니다.\n" + questions)}
