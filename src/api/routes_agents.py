# -*- coding: utf-8 -*-
"""
CSHSP Agent Routes — Sprint F
수검자 대면 채팅/본인확인/문진 제출 엔드포인트 (공개 — 세션 기반).

본인확인 상태:
  UNVERIFIED      → 개인 데이터 접근 불가, 예약 신청 불가
  VERIFIED_BASIC  → 이름+전화 일치 확인. 예약 신청 가능, 개인정보는 마스킹 표시
  VERIFIED_PHONE  → 인증번호(Mock) 확인 완료. 기본정보 전체 표시

원칙: 클라이언트가 보낸 patientId는 신뢰하지 않는다 — 세션의 검증된 patientId만 사용.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for p in ("core", "reservation", "agents", "questionnaire", "security", "dashboard"):
    sys.path.insert(0, str(_ROOT / "src" / p))

from fastapi import APIRouter, HTTPException  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import core_data_loader as loader  # noqa: E402
import questionnaire_service  # noqa: E402
import reservation_audit as audit  # noqa: E402
import safety_guard  # noqa: E402
import slot_extractor  # noqa: E402
from agent_orchestrator import AgentOrchestrator  # noqa: E402
from conversation_manager import ConversationManager  # noqa: E402
from tool_loop import run_tool_loop  # noqa: E402
from ai_metrics import record_event  # noqa: E402
from file_lock import DataLock  # noqa: E402
from privacy_logger import mask_pii  # noqa: E402
from rate_limit import SlidingWindowRateLimiter, rate_from_env  # noqa: E402
from session_store import FileSessionStore  # noqa: E402

MOCK_VERIFY_CODE = "123456"  # Mock 인증번호 — 실서비스에서 SMS 발급으로 교체
_MY_RSV_RE = re.compile(r"(내|나의|제)\s*예약.{0,8}(확인|조회|보여|알려)")


def _mask_birth(b): return (str(b)[:4] + "****") if b else "-"
def _mask_phone(p):
    m = re.match(r"^(\d{2,3})-?(\d{3,4})-?(\d{4})$", str(p or ""))
    return f"{m.group(1)}-****-{m.group(3)}" if m else "-"


class ChatBody(BaseModel):
    sessionId: str
    message: str
    context: dict[str, Any] = {}


class VerifyBody(BaseModel):
    sessionId: str
    name: str | None = None
    phone: str | None = None
    code: str | None = None


class QSubmitBody(BaseModel):
    sessionId: str
    answers: list[dict[str, Any]]


def create_agents_router(data_dir: Path, llm_client=None) -> APIRouter:
    """llm_client: claude_client.ClaudeClient — 지정 시 채팅 기본 경로가 Claude tool_loop로 전환.
    None이면 기존 규칙 기반 경로 유지 (Sprint H: ANTHROPIC_API_KEY 감지로 api_server가 자동 주입)."""
    router = APIRouter(prefix="/api/agents", tags=["agents"])
    orch = AgentOrchestrator(data_dir=data_dir)
    conv = ConversationManager(data_dir)  # Sprint H: 멀티턴 히스토리 영속화
    # Sprint G: 파일 기반 세션 영속화 (Redis 교체 지점 — session_store.SessionStore 인터페이스)
    store = FileSessionStore(Path(data_dir) / "sessions.json")
    # Sprint G: 채팅 요청 제한 (환경변수 CSHSP_CHAT_RATE="30/60")
    _rate_n, _rate_w = rate_from_env()
    limiter = SlidingWindowRateLimiter(_rate_n, _rate_w)

    def session(sid: str) -> dict[str, Any]:
        return store.get(sid)

    def save_session(sid: str, s: dict[str, Any]) -> None:
        store.set(sid, s)

    def audit_safety_block(sid: str, message: str, category: str | None) -> None:
        # 개인정보 원문 저장 금지 — note는 마스킹 후 기록
        with DataLock(data_dir):
            audit.append_audit(data_dir, "SAFETY_BLOCKED", "ChatSession", sid, "USR-9000",
                               after={"category": category}, channel="AI_CHAT",
                               note=mask_pii(str(message))[:100])

    def my_reservations(s: dict[str, Any]) -> dict[str, Any]:
        """본인확인 상태별 예약 조회 (마스킹 정책 적용)"""
        patient = loader.get_by_id("Patient", s["patientId"], data_dir)
        rows = [r for r in loader.load_entity("Reservation", data_dir)
                if r.get("patientId") == s["patientId"]]
        programs = {p["id"]: p for p in loader.load_entity("Program", data_dir)}
        items = [{"reservationNo": r.get("reservationNo") or r.get("id"),
                  "date": r.get("reservationDate"), "time": r.get("wishTime"),
                  "program": (programs.get(r.get("programId")) or {}).get("code"),
                  "status": r.get("status")} for r in rows]
        if s["verifyState"] == "VERIFIED_PHONE":
            who = {"name": patient.get("name"), "birthDate": patient.get("birthDate"),
                   "phone": patient.get("phone")}
        else:  # VERIFIED_BASIC — 마스킹 표시
            who = {"name": patient.get("name"), "birthDate": _mask_birth(patient.get("birthDate")),
                   "phone": _mask_phone(patient.get("phone"))}
        lines = "\n".join(f"  · {i['reservationNo']} {i['date']} {i['time'] or ''} {i['program']} [{i['status']}]"
                          for i in items) or "  · 접수된 예약이 없습니다."
        return {"agent": "reservation_agent", "success": True, "blocked": False,
                "patient": who, "reservations": items,
                "message": f"{who['name']}님({who['birthDate']} / {who['phone']})의 예약 내역입니다:\n{lines}"}

    # ── Sprint H: Claude tool_loop 턴 처리 (llm_client 주입 시 기본 경로) ──
    def _llm_turn(sid: str, message: str, s: dict, ctx: dict) -> dict:
        guard = safety_guard.check(message)  # LLM 호출 전 Safety Guard 선차단
        if not guard["allowed"]:
            return {"agent": "safety_guard", "blocked": True,
                    "category": guard["category"], "message": guard["message"]}
        prefix = (guard["message"] + "\n\n") if guard["category"] == "CONFIRM_REDIRECT" else ""
        # 세션 상태를 컨텍스트로 주입 (개인정보 최소 — 식별자만, 이름/전화 미포함)
        session_note = (f"[세션정보] 본인확인={s['verifyState']}, "
                        f"patientId={s['patientId'] or '미확인(예약 신청 불가, 본인확인 안내)'}"
                        + (f", 추출된 예약조건={ctx}" if ctx else ""))
        out = run_tool_loop(llm_client, orch.tools, f"{session_note}\n사용자: {message}",
                            history=conv.get_history(sid))
        conv.save_history(sid, out["history"])
        if any(tc.get("name") == "create_reservation_request" and tc.get("ok")
               for tc in out["toolCalls"]):
            record_event(data_dir, "RESERVATION_CREATED", sid)
        return {"agent": "claude_tool_loop", "blocked": False,
                "message": prefix + out["message"],
                "toolCalls": out["toolCalls"], "iterations": out["iterations"]}

    # ── 채팅 단일 진입 (일반/스트리밍 공용 코어) ──
    def process_chat(body: ChatBody):
        # Rate Limit (세션 단위)
        if not limiter.allow(body.sessionId):
            record_event(data_dir, "RATE_LIMITED", body.sessionId)
            raise HTTPException(429, f"요청이 너무 잦습니다. 잠시 후 다시 시도해 주세요. "
                                     f"(제한: {_rate_n}회/{_rate_w}초)")

        s = session(body.sessionId)
        ctx = dict(body.context or {})
        ctx.pop("patientId", None)                     # 클라이언트 patientId 불신
        if s["patientId"]:
            ctx["patientId"] = s["patientId"]          # 검증된 세션 patientId만 사용

        # Sprint G: 자연어 슬롯 추출 — 문맥에 없는 프로그램/날짜/시간을 메시지에서 보충
        extracted = slot_extractor.extract(body.message)["extracted"]
        for field in ("programId", "date", "time"):
            if field not in ctx and field in extracted:
                ctx[field] = extracted[field]

        record_event(data_dir, "CHAT", body.sessionId)

        # 내 예약 조회 — 본인확인 게이트
        if _MY_RSV_RE.search(body.message):
            if s["verifyState"] == "UNVERIFIED" or not s["patientId"]:
                result = {"agent": "verify_gate", "blocked": False, "needVerification": True,
                          "message": "예약 내역 확인을 위해 본인확인이 필요합니다. 성함과 전화번호를 입력해 주세요."}
            else:
                result = my_reservations(s)
        else:
            # Sprint H: Key(클라이언트) 존재 시 Claude tool_loop, 없으면 규칙 기반 유지
            if llm_client is not None:
                result = _llm_turn(body.sessionId, body.message, s, ctx)
            else:
                result = orch.handle_message(body.message, ctx)
            if result.get("blocked"):
                audit_safety_block(body.sessionId, body.message, result.get("category"))
                record_event(data_dir, "SAFETY_BLOCKED", body.sessionId,
                             detail=result.get("category"))
            if result.get("success") and result.get("reservation"):
                record_event(data_dir, "RESERVATION_CREATED", body.sessionId)
            if result.get("agent") == "crm_agent" and result.get("success"):
                record_event(data_dir, "CRM_ESCALATION", body.sessionId)
            if result.get("agent") == "questionnaire_agent" and result.get("success"):
                pass  # 제출 시점(submit 엔드포인트)에서 집계
            # Sprint I: 메시지를 대체하는 분기에서도 즉시확정 절차 안내는 반드시 유지
            g = safety_guard.check(body.message)
            notice = (g["message"] + "\n") if g.get("category") == "CONFIRM_REDIRECT" else ""
            # 예약/문진에 본인확인이 필요한 경우 → 인증 안내로 전환
            if "patientId" in (result.get("needInput") or []):
                result["needVerification"] = True
                result["message"] = notice + "본인확인 후 진행할 수 있습니다. 성함과 전화번호를 입력해 주세요."
            elif result.get("needInput"):
                # Sprint G: 부족한 정보만 골라 추가 질문
                result["message"] = notice + slot_extractor.ask_for_missing(result["needInput"])

        result["sessionId"] = body.sessionId
        result["verifyState"] = s["verifyState"]
        return result

    @router.post("/chat")
    def chat(body: ChatBody):
        return process_chat(body)

    @router.post("/chat/stream")
    def chat_stream(body: ChatBody):
        """스트리밍 구조 (Sprint H 준비 단계).
        현재: 완성 응답을 SSE 청크로 분할 전송 — 위젯이 스트리밍 프로토콜로 수신 가능.
        실연동: claude_client에 messages.stream 어댑터 추가 후 이 지점에서 토큰 단위로 교체."""
        result = process_chat(body)

        def gen():
            import json as _json
            text = str(result.get("message", ""))
            meta = {k: result.get(k) for k in ("sessionId", "verifyState", "agent", "blocked",
                                               "needVerification", "needInput", "success")}
            yield f"event: meta\ndata: {_json.dumps(meta, ensure_ascii=False)}\n\n"
            for i in range(0, len(text), 40):
                yield f"data: {_json.dumps(text[i:i + 40], ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    # ── 본인확인 ──
    @router.post("/verify")
    def verify(body: VerifyBody):
        s = session(body.sessionId)

        if body.code is not None:  # 2단계: 인증번호 확인 → VERIFIED_PHONE
            if s["verifyState"] == "UNVERIFIED":
                raise HTTPException(400, "기본 확인(이름+전화번호)을 먼저 진행하세요.")
            if body.code != s.get("pendingCode"):
                return {"success": False, "verifyState": s["verifyState"], "message": "인증번호가 일치하지 않습니다."}
            s["verifyState"], s["pendingCode"] = "VERIFIED_PHONE", None
            save_session(body.sessionId, s)
            record_event(data_dir, "VERIFIED_PHONE", body.sessionId)
            return {"success": True, "verifyState": "VERIFIED_PHONE",
                    "message": "휴대폰 본인확인이 완료되었습니다."}

        if not (body.name and body.phone):  # 1단계 입력 검증
            raise HTTPException(400, "name+phone 또는 code가 필요합니다.")
        patient = next((p for p in loader.load_entity("Patient", data_dir)
                        if p.get("status") == "ACTIVE" and p.get("name") == body.name
                        and str(p.get("phone")) == body.phone), None)
        if patient is None:
            return {"success": False, "verifyState": s["verifyState"],
                    "message": "입력하신 정보와 일치하는 수검자를 찾을 수 없습니다."}
        # 실발송 교체 지점: MOCK_VERIFY_CODE 발급 → SMS 발급 API 호출로 교체
        # (notification_worker.default_mock_sender와 동일하게 sender 함수만 교체하는 구조)
        s.update({"patientId": patient["id"], "verifyState": "VERIFIED_BASIC",
                  "pendingCode": MOCK_VERIFY_CODE})
        save_session(body.sessionId, s)
        record_event(data_dir, "VERIFIED_BASIC", body.sessionId)
        return {"success": True, "verifyState": "VERIFIED_BASIC",
                "message": "기본 확인이 완료되었습니다. 휴대폰으로 발송된(Mock) 인증번호를 입력하시면 상세정보 확인이 가능합니다."}

    @router.get("/session/{sid}")
    def session_state(sid: str):
        s = session(sid)
        return {"sessionId": sid, "verifyState": s["verifyState"],
                "verified": s["patientId"] is not None}

    # ── 문진 응답 제출 (수검자 — 세션 소유자 검증) ──
    @router.post("/questionnaires/{qid}/submit")
    def submit_questionnaire(qid: str, body: QSubmitBody):
        s = session(body.sessionId)
        if s["verifyState"] == "UNVERIFIED" or not s["patientId"]:
            raise HTTPException(403, "본인확인 후 문진을 제출할 수 있습니다.")
        try:
            with DataLock(data_dir):
                rec = questionnaire_service.submit_answers(qid, body.answers, data_dir,
                                                           patient_id=s["patientId"])
        except questionnaire_service.QuestionnaireError as e:
            raise HTTPException(400, str(e))
        record_event(data_dir, "QUESTIONNAIRE_SUBMITTED", body.sessionId)
        return {"success": True, "questionnaire": rec,
                "message": "문진이 제출되었습니다. 검진 당일 의료진이 확인합니다."}

    return router
