# -*- coding: utf-8 -*-
"""
CSHSP Function Tools — Sprint E
AI Agent가 사용하는 Function Calling 도구 계층.

- 모든 병원 데이터 접근은 Sprint D REST API를 경유한다 (AI 신원: X-User-Id=USR-9000).
  · 기본: in-process ASGI 클라이언트(TestClient) — 실서비스에서는 base_url로 원격 API 지정
- TOOL_SCHEMAS: Claude API tool-use 형식 스키마 (MCP/Function Calling 등록용)
- 예약 확정 도구는 존재하지 않는다 — AI는 신청까지만 가능 (API도 403으로 이중 차단)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src" / "api"))
sys.path.insert(0, str(_ROOT / "src" / "core"))

from safety_guard import STAFF_CONFIRM_NOTICE  # noqa: E402

AI_USER_ID = "USR-9000"  # AI 예약비서 (ROLE-AI-AGENT: reservation:request 등 제한 권한)
KB_PATH = _ROOT / "data" / "knowledge_base.json"


class ApiClient:
    """Sprint D REST API 클라이언트. base_url 지정 시 원격, 미지정 시 in-process."""

    def __init__(self, base_url: str | None = None, data_dir: str | Path | None = None,
                 user_id: str = AI_USER_ID):
        self.user_id = user_id
        if base_url:
            import httpx
            self._c = httpx.Client(base_url=base_url, timeout=15)
        else:
            from fastapi.testclient import TestClient
            from api_server import create_app
            # include_agents=False: 에이전트 내부 클라이언트는 agents 라우터 불필요 (순환 생성 방지)
            self._c = TestClient(create_app(data_dir, include_agents=False))

    def _headers(self, user_id: str | None = None) -> dict:
        return {"X-User-Id": user_id or self.user_id}

    def get(self, path: str, user_id: str | None = None):
        r = self._c.get(path, headers=self._headers(user_id))
        return r.status_code, (r.json() if r.content else {})

    def post(self, path: str, body: dict | None = None, user_id: str | None = None):
        r = self._c.post(path, json=body or {}, headers=self._headers(user_id))
        return r.status_code, (r.json() if r.content else {})


# ── Claude Function Calling 스키마 (MCP 등록용) ──
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_available_slots",
        "description": "예약 가능한(AVAILABLE) 검진 슬롯을 기간으로 조회한다.",
        "input_schema": {"type": "object", "properties": {
            "date_from": {"type": "string", "description": "YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["date_from", "date_to"]},
    },
    {
        "name": "recommend_alternative_slots",
        "description": "요청 일시가 불가할 때 가까운 대체 슬롯을 최대 5개 추천한다.",
        "input_schema": {"type": "object", "properties": {
            "date": {"type": "string"}, "time": {"type": "string"},
            "programId": {"type": "string"}}, "required": ["date"]},
    },
    {
        "name": "create_reservation_request",
        "description": "예약을 '신청'한다. 확정이 아니라 직원 승인 대기(PENDING_APPROVAL)로 접수되며, 응답에 반드시 직원 확인 후 확정 안내를 포함해야 한다.",
        "input_schema": {"type": "object", "properties": {
            "patientId": {"type": "string"}, "programId": {"type": "string"},
            "date": {"type": "string"}, "time": {"type": "string"},
            "slotId": {"type": "string"}, "memo": {"type": "string"},
            "allowWaiting": {"type": "boolean", "description": "정원 마감 시 대기예약 접수 여부"}},
            "required": ["patientId", "programId", "date", "time", "slotId"]},
    },
    {
        "name": "recommend_program",
        "description": "나이·성별·예산·관심 키워드 기반으로 종합검진 프로그램을 안내한다. 의료 판단이 아닌 가격·구성 기준 안내.",
        "input_schema": {"type": "object", "properties": {
            "age": {"type": "integer"}, "gender": {"type": "string", "enum": ["M", "F"]},
            "budget": {"type": "integer", "description": "예산(원)"},
            "keywords": {"type": "array", "items": {"type": "string"}}}, "required": []},
    },
    {
        "name": "recommend_optional_tests",
        "description": "관심 부위·키워드 기반 선택검사 '안내'. 검사 필요 여부 판단은 의료진 상담으로 연결한다.",
        "input_schema": {"type": "object", "properties": {
            "keywords": {"type": "array", "items": {"type": "string"}},
            "gender": {"type": "string", "enum": ["M", "F"]}}, "required": ["keywords"]},
    },
    {
        "name": "start_questionnaire",
        "description": "예약 건에 대한 사전문진을 시작한다(응답 수집만, 의료 판단 없음).",
        "input_schema": {"type": "object", "properties": {
            "patientId": {"type": "string"}, "reservationId": {"type": "string"}},
            "required": ["patientId", "reservationId"]},
    },
    {
        "name": "create_crm_notification",
        "description": "상담 접수(CRM) 및 발송 대기(PENDING) 알림을 생성한다. 실제 발송은 직원/워커가 수행.",
        "input_schema": {"type": "object", "properties": {
            "patientId": {"type": "string"}, "reservationId": {"type": "string"},
            "content": {"type": "string"}, "summary": {"type": "string"}},
            "required": ["patientId", "content"]},
    },
    {
        "name": "search_knowledge",
        "description": "검진 프로그램·선택검사·FAQ·정책 지식베이스(RAG 초안)를 키워드로 검색한다.",
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]},
    },
]

# 사전문진 기본 템플릿 (응답 수집 전용 — 판단 없음)
QUESTIONNAIRE_TEMPLATE = [
    {"code": "Q01", "question": "현재 복용 중인 약이 있습니까?", "answer": None},
    {"code": "Q02", "question": "약물·음식·조영제 알레르기가 있습니까?", "answer": None},
    {"code": "Q03", "question": "수면내시경 경험이 있습니까?", "answer": None},
    {"code": "Q04", "question": "임신 가능성이 있습니까? (여성)", "answer": None},
    {"code": "Q05", "question": "최근 6개월 내 수술 이력이 있습니까?", "answer": None},
]


class FunctionTools:
    """도구 실행기 — execute(name, args)로 단일 진입."""

    def __init__(self, api: ApiClient | None = None, data_dir: str | Path | None = None,
                 kb_path: str | Path | None = None):
        self.api = api or ApiClient(data_dir=data_dir)
        kb_doc = json.loads(Path(kb_path or KB_PATH).read_text(encoding="utf-8"))
        self.kb: list[dict] = kb_doc.get("records", [])

    # ── 개별 도구 ──
    def list_available_slots(self, date_from: str, date_to: str) -> dict:
        code, data = self.api.get(f"/api/slots?status=AVAILABLE&from={date_from}&to={date_to}")
        return {"ok": code == 200, "slots": data.get("records", [])}

    def recommend_alternative_slots(self, date: str, time: str = "", programId: str = "") -> dict:
        code, data = self.api.get(f"/api/slots/recommend?date={date}&time={time}&programId={programId}")
        return {"ok": code == 200, "alternatives": data.get("records", [])}

    def create_reservation_request(self, patientId: str, programId: str, date: str, time: str,
                                   slotId: str, memo: str = "", allowWaiting: bool = False) -> dict:
        code, data = self.api.post("/api/reservations", {
            "patientId": patientId, "programId": programId, "requestedDate": date,
            "requestedTime": time, "slotId": slotId, "channel": "AI_ASSISTANT",
            "memo": memo or None, "allowWaiting": allowWaiting})
        if code == 201:
            rec = data["reservation"]
            return {"ok": True, "reservation": rec,
                    "message": f"예약 신청이 접수되었습니다 (신청번호 {rec['reservationNo']}, "
                               f"{rec['reservationDate']} {rec['wishTime']}). {STAFF_CONFIRM_NOTICE}"}
        detail = data.get("detail", {})
        return {"ok": False, "verdict": detail.get("verdict") if isinstance(detail, dict) else None,
                "reasons": detail.get("reasons", [str(detail)]) if isinstance(detail, dict) else [str(detail)],
                "alternatives": detail.get("alternatives", []) if isinstance(detail, dict) else []}

    def recommend_program(self, age: int | None = None, gender: str | None = None,
                          budget: int | None = None, keywords: list[str] | None = None) -> dict:
        kws = [k.lower() for k in (keywords or [])]
        picks: list[str] = []
        if age is not None and 19 <= age <= 38:
            picks.append("KB-PRG-0005")  # YOUNG
        if any(k in kws for k in ("mri", "정밀", "프리미엄")):
            picks += ["KB-PRG-0004", "KB-PRG-0003"]
        if any(k in kws for k in ("고혈압", "당뇨", "흡연", "가족력", "고위험")):
            picks.append("KB-PRG-0003")  # VIP
        if any(k in kws for k in ("국가검진", "공단", "온김에")):
            picks.append("KB-PRG-0006")
        if budget is not None:
            if budget < 400000:
                picks.append("KB-PRG-0005")
            elif budget < 700000:
                picks.append("KB-PRG-0001")
            elif budget < 1000000:
                picks.append("KB-PRG-0002")
            else:
                picks.append("KB-PRG-0003")
        if not picks:
            picks = ["KB-PRG-0002", "KB-PRG-0001"]  # 기본: SMART/BASIC 안내
        seen, out = set(), []
        for pid in picks:
            if pid not in seen:
                seen.add(pid)
                out.append(next(r for r in self.kb if r["id"] == pid))
        return {"ok": True, "recommendations": out[:3],
                "disclaimer": "가격·구성 기준 안내입니다. 개인 건강상태에 따른 검사 선택은 의료진 상담이 필요합니다."}

    def recommend_optional_tests(self, keywords: list[str], gender: str | None = None) -> dict:
        entry = next(r for r in self.kb if r["id"] == "KB-OPT-0001")
        return {"ok": True, "guide": entry["content"],
                "priceNotice": "선택검사 개별 수가는 미등록 상태로, 금액은 검진센터(041-570-7333) 확인이 필요합니다.",
                "disclaimer": "검사 필요 여부 판단은 의료진 상담으로 결정합니다."}

    def start_questionnaire(self, patientId: str, reservationId: str) -> dict:
        code, data = self.api.post("/api/questionnaires/start", {
            "patientId": patientId, "reservationId": reservationId,
            "items": QUESTIONNAIRE_TEMPLATE})
        return {"ok": code == 201, **({"questionnaire": data.get("questionnaire")} if code == 201 else {"error": data.get("detail")})}

    def create_crm_notification(self, patientId: str, content: str,
                                reservationId: str | None = None, summary: str | None = None) -> dict:
        code, data = self.api.post("/api/crm/notifications", {
            "patientId": patientId, "reservationId": reservationId,
            "content": content, "crmSummary": summary})
        return {"ok": code == 201, **({k: data.get(k) for k in ("notification", "crm")} if code == 201 else {"error": data.get("detail")})}

    def search_knowledge(self, query: str) -> dict:
        q = query.lower()
        terms = [t for t in q.replace(",", " ").split() if t]
        scored = []
        for r in self.kb:
            hay = (r["title"] + " " + r["content"] + " " + " ".join(r.get("keywords", []))).lower()
            score = sum(2 for k in r.get("keywords", []) if k.lower() in q) \
                + sum(1 for t in terms if t in hay)
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return {"ok": True, "results": [r for _, r in scored[:3]]}

    # ── 단일 진입 ──
    def execute(self, name: str, args: dict[str, Any]) -> dict:
        allowed = {s["name"] for s in TOOL_SCHEMAS}
        if name not in allowed:
            return {"ok": False, "error": f"등록되지 않은 도구: {name} (예약 확정 도구는 제공되지 않습니다)"}
        return getattr(self, name)(**args)
