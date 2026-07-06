# -*- coding: utf-8 -*-
"""
CSHSP Recommendation Agent — AI 검진 코디네이터 (Sprint E)
프로그램·선택검사 '안내'만 수행한다 (가격·구성 기준). 의료 판단 없음.
"""
from __future__ import annotations

from function_tools import FunctionTools


class RecommendationAgent:
    name = "recommendation_agent"

    def __init__(self, tools: FunctionTools):
        self.tools = tools

    def recommend_program(self, age: int | None = None, gender: str | None = None,
                          budget: int | None = None, keywords: list[str] | None = None) -> dict:
        r = self.tools.recommend_program(age=age, gender=gender, budget=budget, keywords=keywords)
        lines = [f"  · {x['title']} — {x['content'].split('.')[1].strip() if '.' in x['content'] else ''}"
                 for x in r["recommendations"]]
        return {"agent": self.name, "success": True, "recommendations": r["recommendations"],
                "message": "조건에 맞는 프로그램을 안내드립니다:\n" + "\n".join(lines)
                           + f"\n\n{r['disclaimer']}"}

    def recommend_optional_tests(self, keywords: list[str], gender: str | None = None) -> dict:
        r = self.tools.recommend_optional_tests(keywords, gender)
        return {"agent": self.name, "success": True,
                "message": f"{r['guide']}\n\n{r['priceNotice']}\n{r['disclaimer']}"}

    def answer_faq(self, query: str) -> dict:
        r = self.tools.search_knowledge(query)
        if not r["results"]:
            return {"agent": self.name, "success": False,
                    "message": "해당 내용은 지식베이스에 없어 검진센터(041-570-7333) 확인이 필요합니다."}
        top = r["results"][0]
        return {"agent": self.name, "success": True, "source": top["id"],
                "message": f"{top['title']}\n{top['content']}"}
